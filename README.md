# waypoint

Live departure board for one Naolib bus stop (Nantes): it tells you when to
leave home to catch the next bus, and when you will reach your destination.

Default setup: line C2, stop La Close, towards Gare Sud, 3 minutes' walk.

## How it works

- **Realtime**: SIRI StopMonitoring from the Naolib/Okina gateway, public plan
  (no key, 1 request every 30 s). The server caches it; screens poll the server.
- **Travel time**: the realtime feed carries the GTFS trip id, so the scheduled
  time from the stop to the destination is read from the Naolib GTFS for that
  very trip, and shifted by the delay measured at the stop.
- **"Leave in X min"** = realtime departure − walk time − now.

## Endpoints

| Path | |
|---|---|
| `/` | the board |
| `/api/next` | JSON: next departures, with `leave_at`, `arrival`, `delay_seconds` |
| `/healthz` | liveness |

## Run locally

```bash
docker compose up -d --build
```

Then open http://localhost:8503.

## Settings

Environment variables, all optional (see `src/waypoint/config.py`):

| Variable | Default | |
|---|---|---|
| `WAYPOINT_STOP_REF` | `FR_NAOLIB:Quay:2436` | La Close, platform towards Gare Sud |
| `WAYPOINT_DESTINATION_REF` | `FR_NAOLIB:Quay:1758` | Gare Sud |
| `WAYPOINT_LINE_REF` | `FR_NAOLIB:Line:C2` | |
| `WAYPOINT_WALK_MINUTES` | `3` | |
| `WAYPOINT_API_KEY` | unset | Okina key ("Accès authentifié"), lifts the rate limit |
| `WAYPOINT_GTFS_URL` | data.gouv.fr resource | empty disables travel times |

To find the ids of another stop: `stops.txt` of the Naolib GTFS, rows with
`location_type=0` (one quay per direction).

## Deployment

`deploy/truenas.yaml` (TrueNAS Custom App) and `deploy/nginx-vps.conf` (VPS
reverse proxy). Data: Naolib, Nantes Métropole, ODbL.

Font: Atkinson Hyperlegible Next, SIL Open Font License (`src/waypoint/static/fonts/OFL.txt`).
