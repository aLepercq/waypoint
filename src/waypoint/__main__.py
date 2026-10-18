"""Entry point: `waypoint` or `python -m waypoint`."""

import logging
import os

import uvicorn

from waypoint.app import create_app


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    # httpx logs every request URL at INFO, and the URL carries the API key
    # when one is configured.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    uvicorn.run(
        create_app(),
        host=os.environ.get("WAYPOINT_HOST", "0.0.0.0"),
        port=int(os.environ.get("WAYPOINT_PORT", "8503")),
        # Access logs off: a wall screen polling every 15 s is just noise.
        access_log=False,
    )


if __name__ == "__main__":
    main()
