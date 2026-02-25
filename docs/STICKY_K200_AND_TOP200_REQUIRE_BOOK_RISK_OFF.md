# Sticky K=200 guarantee + Top 200 never hide events (missing Book Risk)

## A) VPS .env (sticky)

Ensure `/opt/netbet/.env` contains (add or update so these win):

```bash
BF_STICKY_PREMATCH=1
BF_STICKY_K=200
BF_STICKY_CATALOGUE_MAX=400
BF_MARKET_BOOK_BATCH_SIZE=50
BF_INTERVAL_SECONDS=900
BF_KICKOFF_BUFFER_SECONDS=60
BF_STICKY_NEAR_KICKOFF_HOURS=2
BF_STICKY_NEAR_KICKOFF_CONSECUTIVE_TICKS=1
```

Then restart only the REST client:

```bash
cd /opt/netbet
docker compose up -d --no-deps --force-recreate betfair-rest-client
```

## B) Code changes (already applied)

**Sticky (betfair-rest-client/main.py)**

- After expire, when `tracked_count < K`, use **1-tick maturity** for all catalogue candidates so we fill to 200.
- When `tracked_count >= K`, keep near-kickoff (1 tick within 2h) and 2 ticks otherwise.
- Logging: added `catalogue_candidates` and `matured_candidates` to the `[Sticky]` log line.

**API**

- `/events/book-risk-focus` already supports `require_book_risk=false` (include events with NULL Book Risk L3). No change.

**UI**

- Top 200 list now calls with `require_book_risk=false` so events with missing H/A/D are included and shown as "—".
- Sort: NULLs already sort last; display already shows "—" for null.

## C) Validation (on server, no DevTools)

**REST client logs**

```bash
docker logs -n 300 netbet-betfair-rest-client | grep "\[Sticky\]" | tail -n 20
```

Expect `tracked_count=200` repeatedly; `catalogue_candidates`, `matured_candidates`, `admitted_per_tick`, `expired` in the same line.

**DB (inside postgres container)**

```bash
docker exec -it netbet-postgres psql -U netbet -d netbet -c "SELECT MAX(snapshot_at) FROM market_derived_metrics;"
docker exec -it netbet-postgres psql -U netbet -d netbet -c "SELECT COUNT(DISTINCT market_id) FROM market_derived_metrics WHERE snapshot_at > NOW() - INTERVAL '2 hours';"
```

Expect recent `MAX(snapshot_at)` and ~200 distinct markets in last 2 hours.

**Browser (no DevTools)**

- `require_book_risk=true`: `http://158.220.83.195/api/events/book-risk-focus?limit=200&include_in_play=false&require_book_risk=true` — often fewer rows.
- `require_book_risk=false`: `http://158.220.83.195/api/events/book-risk-focus?limit=200&include_in_play=false&require_book_risk=false` — expect more (up to 200).
- UI main page should show up to 200 events; missing Book Risk shown as "—".

## Acceptance

1. Sticky: logs show `tracked_count=200` on successive ticks; DB ~200 distinct markets in last 2h.
2. UI: main page shows up to 200 events; NULL H/A/D render as "—"; sort stable (NULLs last).
