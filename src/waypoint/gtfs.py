"""Scheduled travel times from the stop to the destination, from the GTFS.

The realtime feed only gives the departure at our stop. The trip id it carries
is the GTFS trip_id, so the GTFS tells how long that very trip takes to reach
the destination. The per-hour median covers trips missing from the GTFS.
"""

from __future__ import annotations

import csv
import io
import logging
import statistics
import zipfile
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class TravelTimes:
    per_trip: dict[str, int] = field(default_factory=dict)  # trip_id -> seconds
    per_hour: dict[int, int] = field(default_factory=dict)  # departure hour -> median seconds
    loaded_at: datetime | None = None

    def lookup(self, trip_id: str, departure: datetime) -> int | None:
        if trip_id in self.per_trip:
            return self.per_trip[trip_id]
        return self.per_hour.get(departure.hour)


def _rows(archive: zipfile.ZipFile, name: str) -> Iterator[dict[str, str]]:
    with archive.open(name) as raw:
        # utf-8-sig: GTFS exports often start with a BOM.
        yield from csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))


def _seconds(hms: str) -> int:
    # GTFS times may exceed 24:00:00 for trips past midnight.
    h, m, s = (int(part) for part in hms.split(":"))
    return h * 3600 + m * 60 + s


def load_travel_times(path: Path, route_id: str, origin: str, destination: str) -> TravelTimes:
    with zipfile.ZipFile(path) as archive:
        trips = {r["trip_id"] for r in _rows(archive, "trips.txt") if r["route_id"] == route_id}

        # stop_times.txt is ~500 MB: a cheap substring test skips csv parsing
        # for the rows we do not need. Ids are unique, so a quoted match is safe.
        needles = (f'"{origin}"', f",{origin},", f'"{destination}"', f",{destination},")
        calls: dict[str, dict[str, tuple[int, int]]] = defaultdict(dict)
        with archive.open("stop_times.txt") as raw:
            text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
            header = next(csv.reader([text.readline()]))
            for line in text:
                if not any(n in line for n in needles):
                    continue
                row = dict(zip(header, next(csv.reader([line])), strict=False))
                if row["trip_id"] not in trips:
                    continue
                when = row["departure_time"] or row["arrival_time"]
                if row["stop_id"] == destination:
                    when = row["arrival_time"] or row["departure_time"]
                calls[row["trip_id"]][row["stop_id"]] = (int(row["stop_sequence"]), _seconds(when))

    per_trip: dict[str, int] = {}
    by_hour: dict[int, list[int]] = defaultdict(list)
    for trip_id, stops in calls.items():
        if origin not in stops or destination not in stops:
            continue
        (seq_o, t_o), (seq_d, t_d) = stops[origin], stops[destination]
        if seq_d <= seq_o:
            continue
        per_trip[trip_id] = t_d - t_o
        by_hour[(t_o // 3600) % 24].append(t_d - t_o)

    per_hour = {h: int(statistics.median(v)) for h, v in by_hour.items()}
    log.info("GTFS loaded: %d trips from %s to %s", len(per_trip), origin, destination)
    return TravelTimes(per_trip=per_trip, per_hour=per_hour, loaded_at=datetime.now().astimezone())
