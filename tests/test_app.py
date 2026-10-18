from fastapi.testclient import TestClient

from waypoint.app import create_app
from waypoint.config import Settings
from waypoint.gtfs import TravelTimes


def test_api_and_page(settings: Settings, sm_payload: bytes) -> None:
    async def fetcher() -> bytes:
        return sm_payload

    async def loader() -> TravelTimes:
        return TravelTimes(per_hour=dict.fromkeys(range(24), 18 * 60))

    with TestClient(create_app(settings, fetcher=fetcher, gtfs_loader=loader)) as client:
        r = client.get("/api/next")
        assert r.status_code == 200
        assert r.headers["cache-control"] == "no-store"
        body = r.json()
        assert body["stop"] == "La Close"
        assert body["walk_minutes"] == 3
        assert body["error"] is None
        assert isinstance(body["departures"], list)

        page = client.get("/")
        assert page.status_code == 200
        assert "default-src 'self'" in page.headers["content-security-policy"]
        assert client.get("/static/app.js").status_code == 200
        assert client.get("/healthz").json() == {"status": "ok"}


def test_no_public_docs(settings: Settings) -> None:
    async def fetcher() -> bytes:
        return b""

    with TestClient(create_app(settings, fetcher=fetcher)) as client:
        for path in ("/docs", "/redoc", "/openapi.json"):
            assert client.get(path).status_code == 404
