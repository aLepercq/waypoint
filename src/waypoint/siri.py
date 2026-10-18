"""SIRI StopMonitoring: request building, HTTP call and response parsing."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from xml.etree.ElementTree import Element

import httpx
from defusedxml import DefusedXmlException, ElementTree

from waypoint.config import Settings

NS = {"s": "http://www.siri.org.uk/siri"}
# Naolib appends a feed suffix to GTFS ids in the realtime feed.
_LOCAL_SUFFIX = ":LOC"


class SiriError(Exception):
    """The feed answered, but not with usable data."""


@dataclass(frozen=True, slots=True)
class Visit:
    journey_ref: str  # GTFS trip_id
    line_ref: str  # GTFS route_id
    destination_ref: str
    aimed_departure: datetime
    expected_departure: datetime | None
    monitored: bool


def strip_suffix(ref: str) -> str:
    return ref.removesuffix(_LOCAL_SUFFIX)


def build_request(stop_ref: str, now: datetime | None = None) -> bytes:
    ts = (now or datetime.now(UTC)).isoformat()
    return f"""<?xml version="1.0" encoding="utf-8"?>
<Siri xmlns="http://www.siri.org.uk/siri" version="2.0">
  <ServiceRequest>
    <RequestTimestamp>{ts}</RequestTimestamp>
    <RequestorRef>waypoint</RequestorRef>
    <StopMonitoringRequest version="2.0">
      <RequestTimestamp>{ts}</RequestTimestamp>
      <MessageIdentifier>{uuid.uuid4()}</MessageIdentifier>
      <MonitoringRef>{stop_ref}</MonitoringRef>
    </StopMonitoringRequest>
  </ServiceRequest>
</Siri>""".encode()


def _text(el: Element, path: str) -> str | None:
    value = el.findtext(path, namespaces=NS)
    return value.strip() if value else None


def _time(el: Element, path: str) -> datetime | None:
    value = _text(el, path)
    return datetime.fromisoformat(value) if value else None


def parse_stop_monitoring(payload: bytes) -> list[Visit]:
    try:
        root = ElementTree.fromstring(payload)
    except (ElementTree.ParseError, DefusedXmlException) as exc:
        raise SiriError(f"invalid XML: {exc}") from exc

    delivery = root.find(".//s:StopMonitoringDelivery", NS)
    if delivery is None:
        raise SiriError("no StopMonitoringDelivery in response")
    if _text(delivery, "s:Status") == "false":
        reason = _text(delivery, ".//s:ErrorText") or "unknown error"
        raise SiriError(f"feed error: {reason}")

    visits = []
    for mvj in delivery.iterfind("s:MonitoredStopVisit/s:MonitoredVehicleJourney", NS):
        call = mvj.find("s:MonitoredCall", NS)
        if call is None:
            continue
        # Departure is what matters at a stop; arrival is the fallback for
        # feeds that only fill one side.
        aimed = _time(call, "s:AimedDepartureTime") or _time(call, "s:AimedArrivalTime")
        if aimed is None:
            continue
        expected = _time(call, "s:ExpectedDepartureTime") or _time(call, "s:ExpectedArrivalTime")
        visits.append(
            Visit(
                journey_ref=strip_suffix(_text(mvj, ".//s:DatedVehicleJourneyRef") or ""),
                line_ref=strip_suffix(_text(mvj, "s:LineRef") or ""),
                destination_ref=_text(mvj, "s:DestinationRef") or "",
                aimed_departure=aimed,
                expected_departure=expected,
                monitored=_text(mvj, "s:Monitored") == "true",
            )
        )
    return visits


async def fetch_stop_monitoring(client: httpx.AsyncClient, settings: Settings) -> bytes:
    params = {}
    url = settings.siri_public_url
    # An empty WAYPOINT_API_KEY= line means "no key".
    if settings.api_key is not None and settings.api_key.get_secret_value():
        url = settings.siri_auth_url
        params["api-key"] = settings.api_key.get_secret_value()
    response = await client.post(
        url,
        params=params,
        content=build_request(settings.stop_ref),
        headers={"Content-Type": "application/xml", "datasetId": settings.dataset_id},
    )
    if response.status_code != 200:
        # Never echo the URL: it carries the API key when one is set.
        raise SiriError(f"HTTP {response.status_code}")
    return response.content
