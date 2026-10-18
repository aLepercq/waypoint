import asyncio
from datetime import datetime, timedelta

import httpx
import pytest

from waypoint.board import Board, build_departures
from waypoint.config import Settings
from waypoint.gtfs import TravelTimes
from waypoint.siri import Visit, parse_stop_monitoring

NOW = datetime.fromisoformat("2026-10-18T13:36:35+02:00")
TRIP_1415 = "FR_NAOLIB:VehicleJourney:49647381-CR_26_27-HS27BA17-Dimanche-01"


def test_departures_sorted_and_joined(settings: Settings, sm_payload: bytes) -> None:
    travel = TravelTimes(per_trip={TRIP_1415: 18 * 60}, per_hour={13: 20 * 60})
    deps = build_departures(parse_stop_monitoring(sm_payload), travel, settings, NOW)

    # The feed lists 13:50 last; the board shows it first.
    assert [d.departure.strftime("%H:%M:%S") for d in deps] == [
        "13:50:27",
        "14:15:51",
        "14:40:51",
        "15:05:51",
    ]
    first, second = deps[0], deps[1]
    assert first.delay_seconds == 27
    assert first.leave_at == first.departure - timedelta(minutes=3)
    # Trip known to the GTFS: its own travel time, shifted by the realtime delay.
    assert second.arrival == second.departure + timedelta(minutes=18)
    # Unknown trip: median of its scheduled hour (13h).
    assert first.arrival == first.departure + timedelta(minutes=20)


def _visit(minutes: int, **kw: object) -> Visit:
    base = {
        "journey_ref": "t",
        "line_ref": "FR_NAOLIB:Line:C2",
        "destination_ref": "FR_NAOLIB:Quay:1758",
        "aimed_departure": NOW + timedelta(minutes=minutes),
        "expected_departure": NOW + timedelta(minutes=minutes),
        "monitored": True,
    }
    base.update(kw)
    return Visit(**base)  # type: ignore[arg-type]


def test_filters_other_lines_past_buses_and_caps(settings: Settings) -> None:
    visits = [
        _visit(-5),  # already gone
        _visit(5, line_ref="FR_NAOLIB:Line:C1"),
        _visit(6, destination_ref="FR_NAOLIB:Quay:1"),
        *[_visit(m) for m in (10, 20, 30, 40, 50)],
    ]
    deps = build_departures(visits, TravelTimes(), settings, NOW)

    assert [int((d.departure - NOW).total_seconds() // 60) for d in deps] == [10, 20, 30, 40]
    assert all(d.arrival is None for d in deps)


def test_unmonitored_visit_is_not_realtime(settings: Settings) -> None:
    deps = build_departures([_visit(10, monitored=False)], TravelTimes(), settings, NOW)
    assert not deps[0].realtime


class FakeClock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def test_board_caches_and_keeps_stale_data(settings: Settings, sm_payload: bytes) -> None:
    calls = 0
    fail = False

    async def fetcher() -> bytes:
        nonlocal calls
        calls += 1
        if fail:
            raise httpx.ConnectTimeout("boom https://x/?api-key=SECRET")
        return sm_payload

    clock = FakeClock()
    board = Board(settings, fetcher, clock=clock)

    async def scenario() -> None:
        nonlocal fail
        await asyncio.gather(*(board.snapshot() for _ in range(5)))
        assert calls == 1  # concurrent screens share one upstream call

        clock.t += 10
        await board.snapshot()
        assert calls == 1  # within the public plan's 30 s

        clock.t += 30
        fail = True
        snap = await board.snapshot()
        assert calls == 2
        # Error reported by type only: the httpx message may carry the key.
        assert snap["error"] == "ConnectTimeout"
        assert "SECRET" not in str(snap)
        assert snap["fetched_at"] is not None  # previous data kept

        clock.t += 5
        await board.snapshot()
        assert calls == 2  # failures are rate limited too

    asyncio.run(scenario())


@pytest.mark.parametrize("walk", [0, 5])
def test_walk_time_is_configurable(sm_payload: bytes, walk: int) -> None:
    s = Settings(gtfs_url="", walk_minutes=walk)
    deps = build_departures(parse_stop_monitoring(sm_payload), TravelTimes(), s, NOW)
    assert deps[0].departure - deps[0].leave_at == timedelta(minutes=walk)
