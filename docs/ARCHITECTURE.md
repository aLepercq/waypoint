# Architecture

```
screens (phone, living-room display)
   │  GET /api/next every 15 s, countdown redrawn every second client-side
   ▼
FastAPI (one container, NAS :8503)
   ├─ Board ── single-flight, ≤ 1 upstream call / 30 s ──► Okina SIRI (StopMonitoring)
   └─ TravelTimes ◄── daily download + streamed parse ──── Naolib GTFS (data.gouv.fr)
```

## Decisions

- **SIRI XML on the public plan, not SIRI Lite JSON.** SIRI Lite requires an
  API key with manual approval; the public plan covers StopMonitoring at one
  request every 30 s, which a server-side cache turns into "any number of
  screens". A key, when granted, is optional configuration.
- **Arrival = realtime departure + scheduled travel time of that trip.** The
  feed's `DatedVehicleJourneyRef` is the GTFS `trip_id` plus `:LOC`. A second
  StopMonitoring call at Gare Sud would double the upstream rate for little
  gain. Fallback: median travel time of the scheduled hour.
- **GTFS parse filtered by substring before CSV parsing.** `stop_times.txt` is
  ~500 MB; only rows mentioning the two quays are parsed. Runs in a thread, at
  start then every 24 h (retry after 1 h on failure, previous data kept).
- **Stale beats empty.** On upstream failure the board keeps the last visits
  and says how old they are; failures are rate limited like successes.
- **No database, no volume.** Everything is rebuilt from the two feeds.
