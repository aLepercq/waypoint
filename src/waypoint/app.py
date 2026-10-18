"""HTTP layer: the display page and the JSON API it polls."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import tempfile
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from importlib import resources
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from waypoint import __version__
from waypoint.board import Board, Fetcher
from waypoint.config import Settings
from waypoint.gtfs import TravelTimes, load_travel_times
from waypoint.siri import fetch_stop_monitoring

log = logging.getLogger(__name__)

STATIC = Path(str(resources.files("waypoint") / "static"))

# Same-origin only: the page loads nothing from third parties.
_SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data:; object-src 'none'; "
        "base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
}


async def download_gtfs(client: httpx.AsyncClient, settings: Settings) -> TravelTimes:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "gtfs.zip"
        async with client.stream("GET", settings.gtfs_url, follow_redirects=True) as response:
            response.raise_for_status()
            with path.open("wb") as fh:
                async for chunk in response.aiter_bytes():
                    fh.write(chunk)
        # Parsing ~500 MB of CSV: keep it off the event loop.
        return await asyncio.to_thread(
            load_travel_times,
            path,
            settings.line_ref,
            settings.stop_ref,
            settings.destination_ref,
        )


GtfsLoader = Callable[[], Awaitable[TravelTimes]]


async def _gtfs_loop(board: Board, loader: GtfsLoader, settings: Settings) -> None:
    while True:
        try:
            board.travel = await loader()
            delay = settings.gtfs_refresh_hours * 3600
        except Exception:
            # Previous travel times stay in place; arrivals use them meanwhile.
            log.exception("GTFS refresh failed")
            delay = settings.gtfs_retry_minutes * 60
        await asyncio.sleep(delay)


def create_app(
    settings: Settings | None = None,
    fetcher: Fetcher | None = None,
    gtfs_loader: GtfsLoader | None = None,
) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, read=60.0),
            headers={"User-Agent": f"waypoint/{__version__} (+https://waypoint.lepercloud.fr)"},
        ) as client:
            board = Board(settings, fetcher or (lambda: fetch_stop_monitoring(client, settings)))
            app.state.board = board
            loader = gtfs_loader
            if loader is None and settings.gtfs_url:
                loader = lambda: download_gtfs(client, settings)  # noqa: E731
            task = asyncio.create_task(_gtfs_loop(board, loader, settings)) if loader else None
            try:
                yield
            finally:
                if task:
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task

    # Public app: no interactive docs or schema to advertise.
    app = FastAPI(
        title="waypoint", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None
    )

    @app.middleware("http")
    async def security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers.update(_SECURITY_HEADERS)
        return response

    @app.get("/api/next")
    async def next_departures(request: Request) -> JSONResponse:
        data: dict[str, Any] = await request.app.state.board.snapshot()
        return JSONResponse(data, headers={"Cache-Control": "no-store"})

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
