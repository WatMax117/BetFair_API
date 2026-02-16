# Stream UI Clone (`/stream`)

## Where the new route is implemented

- **Frontend (same UI, different API base)**
  - **Entry / routing:** `web/src/main.tsx` — `BrowserRouter` with routes `/stream`, `/stream/*`, and `*`. When path starts with `/stream`, `ApiBaseSync` sets `window.__API_BASE__ = '/api/stream'` so all API calls use the stream backend.
  - **API client:** `web/src/api.ts` — `getApiBase()` returns `window.__API_BASE__` when set, otherwise `VITE_API_URL` or `'/api'`. All fetch helpers use `getApiBase()` so no component changes were required.
  - **Components:** Unchanged. `LeaguesAccordion`, `EventDetail`, `SortedEventsList`, `EventsTable` are shared; they call the same `api.ts` functions, which hit `/api/stream/...` when the app is loaded at `/stream`.

- **Backend (streaming-derived endpoints)**
  - **Router:** `api/app/stream_router.py` — FastAPI router mounted at prefix `/stream` in `api/app/main.py`.
  - **Data layer:** `api/app/stream_data.py` — 15-min UTC bucket logic, reads from `stream_ingest.ladder_levels` and `stream_ingest.market_liquidity_history`; metadata from `public.market_event_metadata`.
  - **Book Risk L3:** `api/app/book_risk_l3.py` — Same formulas as `betfair-rest-client/risk.py`; used by `stream_data` with stream-derived ladder data.

## Streaming endpoints used and mapping to UI data models

| Endpoint | Purpose | Source | Response shape |
|----------|---------|--------|----------------|
| `GET /stream/events/by-date-snapshots?date=YYYY-MM-DD` | Events for date (calendar) | `stream_ingest` 15-min bucket + `market_event_metadata` | Same as REST: `EventItem[]` (market_id, event_name, latest_snapshot_at, home/away/draw best back/lay, total_volume, home/away/draw_book_risk_l3, etc.). |
| `GET /stream/events/{market_id}/timeseries?from_ts=&to_ts=&interval_minutes=15` | Chart time series | Last state in each 15-min UTC bucket from `ladder_levels` + `market_liquidity_history` | Same as REST: `TimeseriesPoint[]` (snapshot_at, best back/lay, book_risk_l3, total_volume, depth_limit, calculation_version). |
| `GET /stream/events/{market_id}/meta` | Event header (name, league, runners) | `public.market_event_metadata` | Same as REST: `EventMeta`. |
| `GET /stream/events/{market_id}/latest_raw` | Raw snapshot JSON | N/A (stream has no raw payload) | 404. |
| `GET /stream/debug/markets/{market_id}/snapshots` | Debug snapshot table | Same 15-min bucket points as timeseries | Same shape as REST debug snapshots (snapshot_id, snapshot_at, best back/lay, book_risk_l3, mbs_source=stream_15min). |
| `GET /stream/debug/snapshots/{id}/raw` | Raw payload for one snapshot | N/A | 404. |

Mapping: Ladder rows in `stream_ingest.ladder_levels` (per market_id, selection_id, side, level, publish_time) are aggregated to “last state at or before” each 15-min bucket time. From that we build per-runner `availableToBack` (top 3 levels) and call `compute_book_risk_l3`; best back/lay L1 come from the first level with size > 0. Total volume is from `stream_ingest.market_liquidity_history` at or before the bucket time. Home/Away/Draw come from `market_event_metadata` (home_selection_id, away_selection_id, draw_selection_id).

## Staleness rule and assumptions

- **Staleness:** A market is **excluded** from a 15-min bucket if the latest `ladder_levels.publish_time` at or before that bucket time is older than **20 minutes** (configurable as `STALE_MINUTES` in `api/app/stream_data.py`). So: *no update in the last 20 minutes (UTC) → market is omitted from that bucket.*
- **Config:** `STALE_MINUTES = 20` in `stream_data.py`. No update in last N minutes → market not shown for that bucket (and for “latest” snapshot we use the latest bucket in the day and apply the same rule).
- **Assumptions:**
  - `stream_ingest.ladder_levels` and `stream_ingest.market_liquidity_history` are populated by the Betfair streaming client; `market_event_metadata` is populated by the REST/catalogue path (shared).
  - 15-min bucket = floor to UTC :00 / :15 / :30 / :45; snapshot for a bucket = last state with `publish_time <= bucket_time`.
  - Book Risk L3 uses the same logic as REST (top 3 back levels, R[o] = W[o] - L[o]); only the data source and 15-min timing differ.

## How to use

- **REST UI (unchanged):** Open `http(s)://<ip>/` — uses `/api` (REST, `market_derived_metrics`).
- **Stream UI:** Open `http(s)://<ip>/stream` — uses `/api/stream` (stream_ingest, 15-min UTC buckets). Same pages, charts, tables, and filters; data source and snapshot timing are the only differences.
