from datetime import datetime
from pathlib import Path

from waypoint.gtfs import load_travel_times

ORIGIN, DEST = "FR_NAOLIB:Quay:2436", "FR_NAOLIB:Quay:1758"


def test_travel_times(gtfs_zip: Path) -> None:
    tt = load_travel_times(gtfs_zip, "FR_NAOLIB:Line:C2", ORIGIN, DEST)

    # Only C2 trips that reach the destination after the stop.
    assert tt.per_trip == {"T1": 22 * 60, "T2": 13 * 60}
    # Trips past midnight count in the 0h bucket.
    assert tt.per_hour == {8: 22 * 60, 0: 13 * 60}


def test_lookup_falls_back_to_the_hour(gtfs_zip: Path) -> None:
    tt = load_travel_times(gtfs_zip, "FR_NAOLIB:Line:C2", ORIGIN, DEST)

    eight = datetime(2026, 10, 19, 8, 40)
    assert tt.lookup("T1", eight) == 22 * 60
    assert tt.lookup("unknown-trip", eight) == 22 * 60
    assert tt.lookup("unknown-trip", datetime(2026, 10, 19, 15, 0)) is None
