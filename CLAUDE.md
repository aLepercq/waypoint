# Waypoint

@~/.claude/lepercloud.md

## Project sheet

| | |
|---|---|
| Purpose | Live board for bus C2 at La Close towards Gare Sud: when to leave home (walk 3 min), next buses, arrival time at Gare Sud. Shown on a phone and, later, on a living-room screen |
| Repo | `aLepercq/waypoint` |
| Stack | Python (uv), FastAPI, static HTML/CSS/JS (no build step) |
| Data sources | Naolib SIRI StopMonitoring (Okina gateway, public plan: 1 request / 30 s, no key) · Naolib GTFS from data.gouv.fr (travel times, refreshed daily) |
| Runtime | TrueNAS Custom App (`deploy/truenas.yaml`), single container, NAS port 8503 |
| Image | `ghcr.io/alepercq/waypoint`, published by CI on a `v*` tag |
| Access | public, no authentication: `waypoint.lepercloud.fr` |
| nginx | `deploy/nginx-vps.conf` · body size 1k · timeouts 5s / 15s / 15s |
| Data to back up | none (stateless) · optional API key in `/mnt/leperserver/waypoint/.env` |
| Wiki | Lepercloud › Applications › Waypoint (to create) |

Details: `README.md`, `docs/ARCHITECTURE.md`.

## Development

Run everything inside the devcontainer.

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest
```

## Release

1. `uv version --bump <patch|minor|major>`, commit, annotated tag `vX.Y.Z`, push: CI publishes the image.
2. TrueNAS → Apps → waypoint → Edit: set the new version in `image:`. Rollback: previous version.

## Project guardrails

- The upstream public plan allows 1 request every 30 s: every upstream call goes through `Board` (single-flight, rate-limited, failures included). Never add a code path that calls the feed per visitor.
- Tests never call the real Naolib API or download the GTFS.
- The API key, when set, travels in the query string: never log request URLs (httpx logger stays at WARNING) and never put httpx exception messages in API responses.
- Stop, line and destination ids are NeTEx ids shared by the GTFS and SIRI; the realtime feed appends `:LOC`, stripped in `siri.py`.
- Public page: no third-party resources (CSP `default-src 'self'`), fonts are self-hosted.
