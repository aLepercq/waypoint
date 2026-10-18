import csv
import io
import zipfile
from pathlib import Path

import pytest

from waypoint.config import Settings

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def settings() -> Settings:
    # No network in tests: GTFS download off, API key unset.
    return Settings(gtfs_url="", api_key=None)


@pytest.fixture
def sm_payload() -> bytes:
    return (FIXTURES / "stop_monitoring.xml").read_bytes()


def _csv(rows: list[list[str]]) -> str:
    buf = io.StringIO()
    # Unquoted ids here; the real Naolib export quotes them (covered by the live check).
    csv.writer(buf, quoting=csv.QUOTE_MINIMAL).writerows(rows)
    return buf.getvalue()


@pytest.fixture
def gtfs_zip(tmp_path: Path) -> Path:
    """Tiny GTFS: two C2 trips towards Gare Sud, one C2 trip the other way, one C1 trip."""
    o, d, x = "FR_NAOLIB:Quay:2436", "FR_NAOLIB:Quay:1758", "FR_NAOLIB:Quay:9"
    trips = [
        ["route_id", "service_id", "trip_id", "trip_headsign", "direction_id"],
        ["FR_NAOLIB:Line:C2", "s", "T1", "Gare Sud", "1"],
        ["FR_NAOLIB:Line:C2", "s", "T2", "Gare Sud", "1"],
        ["FR_NAOLIB:Line:C2", "s", "T3", "Le Cardo", "0"],
        ["FR_NAOLIB:Line:C1", "s", "T4", "Gare Sud", "1"],
    ]
    stop_times = [
        ["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"],
        ["T1", "08:00:00", "08:00:00", x, "1"],
        ["T1", "08:10:00", "08:10:00", o, "2"],
        ["T1", "08:32:00", "08:32:00", d, "3"],
        ["T2", "24:05:00", "24:05:00", o, "2"],  # past midnight
        ["T2", "24:18:00", "24:18:00", d, "3"],
        ["T3", "09:00:00", "09:00:00", d, "1"],  # reverse direction
        ["T3", "09:20:00", "09:20:00", o, "2"],
        ["T4", "10:00:00", "10:00:00", o, "1"],
        ["T4", "10:05:00", "10:05:00", d, "2"],
    ]
    path = tmp_path / "gtfs.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("trips.txt", "﻿" + _csv(trips))
        z.writestr("stop_times.txt", _csv(stop_times))
    return path
