"""The departure board: cached realtime visits joined with GTFS travel times."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from waypoint.config import Settings
from waypoint.gtfs import TravelTimes
from waypoint.siri import SiriError, Visit, parse_stop_monitoring

log = logging.getLogger(__name__)

Fetcher = Callable[[], Awaitable[bytes]]

# A bus that left less than this long ago may still be at the stop.
_GRACE = timedelta(seconds=30)


@dataclass(frozen=True, slots=True)
class Departure:
    departure: datetime
    aimed_departure: datetime
    realtime: bool
    arrival: datetime | None
    leave_at: datetime

    @property
    def delay_seconds(self) -> int:
        return int((self.departure - self.aimed_departure).total_seconds())

    def as_json(self) -> dict[str, Any]:
        return {
            "departure": self.departure.isoformat(),
            "aimed_departure": self.aimed_departure.isoformat(),
            "delay_seconds": self.delay_seconds,
            "realtime": self.realtime,
            "arrival": self.arrival.isoformat() if self.arrival else None,
            "travel_minutes": (
                round((self.arrival - self.departure).total_seconds() / 60)
                if self.arrival
                else None
            ),
            "leave_at": self.leave_at.isoformat(),
        }


def build_departures(
    visits: list[Visit], travel: TravelTimes, settings: Settings, now: datetime
) -> list[Departure]:
    tz = ZoneInfo(settings.timezone)
    walk = timedelta(minutes=settings.walk_minutes)
    out = []
    for v in visits:
        if v.line_ref != settings.line_ref or v.destination_ref != settings.destination_ref:
            continue
        aimed = v.aimed_departure.astimezone(tz)
        # An unmonitored visit only repeats the timetable.
        realtime = v.monitored and v.expected_departure is not None
        dep = v.expected_departure.astimezone(tz) if v.expected_departure else aimed
        if dep < now - _GRACE:
            continue
        # Scheduled travel time on top of the realtime departure: the delay
        # measured at our stop is carried to the destination.
        travel_s = travel.lookup(v.journey_ref, aimed)
        arrival = dep + timedelta(seconds=travel_s) if travel_s is not None else None
        out.append(Departure(dep, aimed, realtime, arrival, dep - walk))
    out.sort(key=lambda d: d.departure)
    return out[: settings.max_departures]


class Board:
    """Rate-limited, single-flight access to the feed.

    However many screens poll us, the upstream API sees at most one request per
    `min_fetch_interval_s`, which is the limit of its public plan.
    """

    def __init__(
        self, settings: Settings, fetcher: Fetcher, clock: Callable[[], float] = time.monotonic
    ):
        self._settings = settings
        self._fetch = fetcher
        self._clock = clock
        self._lock = asyncio.Lock()
        self._last_attempt: float | None = None
        self._visits: list[Visit] = []
        self._fetched_at: datetime | None = None
        self._error: str | None = None
        self.travel = TravelTimes()

    async def _refresh(self) -> None:
        async with self._lock:
            now = self._clock()
            if (
                self._last_attempt is not None
                and now - self._last_attempt < self._settings.min_fetch_interval_s
            ):
                return
            self._last_attempt = now
            try:
                visits = parse_stop_monitoring(await self._fetch())
            except (SiriError, httpx.HTTPError) as exc:
                # Keep the previous visits: a stale board beats an empty one.
                # httpx messages may embed the request URL, hence the API key:
                # only our own SiriError messages are shown.
                self._error = str(exc) if isinstance(exc, SiriError) else type(exc).__name__
                log.warning("SIRI fetch failed: %s", self._error)
                return
            self._visits = visits
            self._fetched_at = datetime.now(ZoneInfo(self._settings.timezone))
            self._error = None

    async def snapshot(self) -> dict[str, Any]:
        await self._refresh()
        s = self._settings
        now = datetime.now(ZoneInfo(s.timezone))
        departures = build_departures(self._visits, self.travel, s, now)
        return {
            "stop": s.stop_name,
            "destination": s.destination_name,
            "line": s.line_name,
            "line_color": s.line_color,
            "walk_minutes": s.walk_minutes,
            "now": now.isoformat(),
            "fetched_at": self._fetched_at.isoformat() if self._fetched_at else None,
            "error": self._error,
            "gtfs_loaded_at": self.travel.loaded_at.isoformat() if self.travel.loaded_at else None,
            "departures": [d.as_json() for d in departures],
        }
