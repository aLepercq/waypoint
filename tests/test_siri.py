from datetime import datetime

import pytest

from waypoint.siri import SiriError, build_request, parse_stop_monitoring


def test_parses_real_response(sm_payload: bytes) -> None:
    visits = parse_stop_monitoring(sm_payload)

    assert len(visits) == 4
    first = visits[0]
    # The ":LOC" suffix is dropped so the ids match the GTFS.
    assert first.journey_ref == "FR_NAOLIB:VehicleJourney:49647381-CR_26_27-HS27BA17-Dimanche-01"
    assert first.line_ref == "FR_NAOLIB:Line:C2"
    assert first.destination_ref == "FR_NAOLIB:Quay:1758"
    assert first.aimed_departure == datetime.fromisoformat("2026-10-18T14:16:00+02:00")
    assert first.expected_departure == datetime.fromisoformat("2026-10-18T14:15:51+02:00")
    assert first.monitored


def test_feed_error_is_raised() -> None:
    payload = b"""<Siri xmlns="http://www.siri.org.uk/siri"><ServiceDelivery>
    <StopMonitoringDelivery><Status>false</Status>
    <ErrorCondition><ErrorText>unknown stop</ErrorText></ErrorCondition>
    </StopMonitoringDelivery></ServiceDelivery></Siri>"""
    with pytest.raises(SiriError, match="unknown stop"):
        parse_stop_monitoring(payload)


@pytest.mark.parametrize(
    "payload",
    [
        b"not xml",
        b"<Siri xmlns='http://www.siri.org.uk/siri'/>",
        # Entity expansion must be refused, not evaluated.
        b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><x>&a;</x>',
    ],
)
def test_bad_payloads_raise(payload: bytes) -> None:
    with pytest.raises(SiriError):
        parse_stop_monitoring(payload)


def test_request_names_the_stop() -> None:
    body = build_request("FR_NAOLIB:Quay:2436").decode()
    assert "<MonitoringRef>FR_NAOLIB:Quay:2436</MonitoringRef>" in body
    assert "<StopMonitoringRequest" in body
