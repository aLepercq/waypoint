"""Runtime settings, read from WAYPOINT_* environment variables."""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WAYPOINT_", frozen=True)

    # Identifiers shared by the GTFS and SIRI feeds (NeTEx ids).
    stop_ref: str = "FR_NAOLIB:Quay:2436"  # La Close, platform towards Gare Sud
    destination_ref: str = "FR_NAOLIB:Quay:1758"  # Gare Sud, C2 terminus
    line_ref: str = "FR_NAOLIB:Line:C2"

    # Display labels.
    stop_name: str = "La Close"
    destination_name: str = "Gare Sud"
    line_name: str = "C2"
    line_color: str = "#ee7402"  # route_color in the GTFS

    walk_minutes: int = 3
    max_departures: int = 4

    # Public plan: 1 request every 30 s, no key. With a key the limit is lifted,
    # but the cache keeps us at the same pace anyway.
    siri_public_url: str = "https://api.okina.fr/gateway/sem/realtime/anshar/services"
    siri_auth_url: str = "https://api.okina.fr/gateway/sem/realtime/anshar/siri"
    dataset_id: str = "NAOLIBORG"
    api_key: SecretStr | None = None
    min_fetch_interval_s: float = 30.0

    # Empty string disables the GTFS download (tests, offline runs).
    gtfs_url: str = "https://www.data.gouv.fr/api/1/datasets/r/65bdd7e4-a8e7-4a54-893a-808e71c34d68"
    gtfs_refresh_hours: float = 24.0
    gtfs_retry_minutes: float = 60.0

    timezone: str = "Europe/Paris"
