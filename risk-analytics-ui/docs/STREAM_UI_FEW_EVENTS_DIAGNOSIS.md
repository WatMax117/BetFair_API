# Stream UI “Sorted events list” – Why So Few Events?

This document diagnoses why the **Sorted events list** on `/stream` shows only ~tens of events, with concrete pipeline stages and how to verify counts.

---

## 1. What the UI calls

### Endpoint

- **URL:** `GET /api/stream/events/by-date-snapshots`
- **Query params:** `date` (required) = UTC date `YYYY-MM-DD` (e.g. `2026-02-18`).
- **No pagination:** no `limit`, `top`, `pageSize`, or `offset`. The backend returns the full list for that date.

### Example request (browser / curl)

```http
GET /api/stream/events/by-date-snapshots?date=2026-02-18
```

### Example response (sanitized)

```json
[
  {
    "market_id": "1.234567890",
    "event_id": "32123456",
    "event_name": "Team A v Team B",
    "event_open_date": "2026-02-18T15:00:00+00:00",
    "competition_name": "English Premier League",
    "latest_snapshot_at": "2026-02-18T10:45:00+00:00",
    "home_best_back": 2.1,
    "away_best_back": 3.5,
    "draw_best_back": 3.2,
    "total_volume": 125000.5,
    "home_book_risk_l3": -120.5,
    "away_book_risk_l3": 80.2,
    "draw_book_risk_l3": 40.3,
    ...
  }
]
```

- **Backend:** `stream_router.py` → `stream_events_by_date_snapshots(date)` → `get_events_by_date_snapshots_stream(date)` in `stream_data.py`.
- **No explicit max rows** in code; the list is limited only by the pipeline below (stream data + metadata + staleness).

---

## 2. Counts at each stage (same date/window)

Use the **same UTC date** as the UI (default = today). Run the diagnostic SQL on the VPS to get real numbers:

```bash
cat risk-analytics-ui/scripts/diagnose_stream_events_pipeline.sql | docker exec -i netbet-postgres psql -U netbet -d netbet
```

Interpretation:

| Stage | What to count | Where |
|-------|----------------|--------|
| **Betfair (catalogue)** | Soccer events in window; markets per event for subscribed types | Not in DB; Betfair listMarketCatalogue with eventTypeIds=1, marketTypeCodes=[MATCH_ODDS_FT, OVER_UNDER_25_FT, OVER_UNDER_05_HT, MATCH_ODDS_HT, NEXT_GOAL], maxResults=200 → **at most 40 events × 5 = 200 markets**. |
| **Stream client / ingest** | Distinct event_ids and market_ids seen in stream in last N hours | In code: subscription is **capped at 40 events × 5 market types = 200 market IDs** (`PriorityMarketResolver`: MAX_EVENTS=40, MAX_MARKET_IDS=200). No extra filter in logs beyond Soccer + those market types. |
| **DB: stream data** | Distinct `market_id` in `stream_ingest.ladder_levels` with `publish_time` in [date 00:00, date 24:00) UTC | Diagnostic query **§2**: `stream_markets_in_date_window`. |
| **DB: metadata join** | Of those, how many exist in `market_event_metadata`? | Diagnostic **§3**: `with_metadata` vs `without_metadata`. If `market_event_metadata` is only populated for MATCH_ODDS (e.g. by REST client), you get **at most one market per event** (~40 rows) even if ladder has 200. |
| **DB: after staleness** | Of markets with metadata, how many have a last tick within **120 minutes** of the “latest bucket”? | Diagnostic **§6**: `after_staleness_kept`. `stream_data.STALE_MINUTES = 120`; any market with no tick in the last 2 hours is **excluded**. |
| **Risk Analytics API** | Count returned by `get_events_by_date_snapshots_stream(date)` | Equals “after staleness” (one row per market). No extra limit or filter; no Book Risk / volume filter before returning. |

So the **UI row count** = number of markets that:

1. Have at least one tick in `stream_ingest.ladder_levels` on that UTC date,  
2. Have a row in `market_event_metadata`, and  
3. Have their latest tick within 120 minutes of the current “latest” 15‑minute bucket.

---

## 3. Filters that can exclude events

| Filter | Applied? | Where | Effect |
|--------|----------|--------|--------|
| **Narrow date range** | Yes | UI sends one date (e.g. today). Backend uses `[date 00:00 UTC, date 24:00 UTC)` for **which markets have any tick that day**. | Only markets with at least one tick on that calendar day are considered. |
| **Market type** | Indirect | Stream client subscribes to 5 types (MATCH_ODDS_FT, OVER_UNDER_25_FT, OVER_UNDER_05_HT, MATCH_ODDS_HT, NEXT_GOAL). **`market_event_metadata`** is populated elsewhere (e.g. REST client); if it only contains one type (e.g. MATCH_ODDS), the join drops the other 4 types per event. | Can reduce 200 → ~40 rows (one per event). |
| **totalMatched == 0 / volume == 0** | No | Backend does **not** filter out zero volume. | No exclusion. |
| **Full set of markets per event** | No | Backend does not require “3 markets” or “all 5 types” per event. | No exclusion. |
| **Competition allowlist** | No | No league allowlist in stream API. | No exclusion. |
| **“Latest snapshot time” (only updated in last Y min)** | Yes | **Staleness:** market is excluded if its latest tick is older than `latest_bucket - 120` minutes (`STALE_MINUTES` in `stream_data.py`). | Markets that stopped receiving ticks >2 hours ago disappear from the list. |

---

## 4. Deployment and market-type configuration

- **Streaming client:** Subscribes to Soccer (eventTypeIds=1), 5 market types (MATCH_ODDS_FT, OVER_UNDER_25_FT, OVER_UNDER_05_HT, MATCH_ODDS_HT, NEXT_GOAL), **top 40 events by MAXIMUM_TRADED**, up to 200 market IDs. Subscription payload is built in `SubscriptionManager.buildMarketSubscriptionPayload`; when no explicit `market-ids` are set, it uses `eventTypeIds` + `marketTypeCodes` (no `marketIds`), so the resolver’s 40×5 list is used. Confirm on the server: Docker image/tag or commit for `netbet-streaming-client`, and env `betfair.priority-subscription-enabled` (default true).
- **Risk Analytics API (stream):** Serves `/api/stream/*`. No market-type allowlist in code; it just joins `stream_ingest.ladder_levels` (by date) to `market_event_metadata`. Confirm which commit/image is running for `risk-analytics-ui-api`.
- **market_event_metadata:** Populated by the **REST client** (or another process), not by the streaming client. If the REST client only writes MATCH_ODDS (or one market per event), the stream UI will only show those markets. **HALF_TIME vs MATCH_ODDS_HT:** Stream subscription uses `MATCH_ODDS_HT`; DB view `v_event_summary` (V7) uses `MATCH_ODDS_HT`. Live API uses “HALF_TIME” in some docs; our code uses `MATCH_ODDS_HT`.

---

## 5. Root cause statement

**The UI shows only ~N events because:**

1. **Primary:** The stream pipeline is **capped by design at 40 events** (PriorityMarketResolver: top 40 Soccer events × 5 market types = 200 markets). So you never get “hundreds” of events from the current design. Within that 200, the list is further reduced by:
   - **Metadata join:** Only markets present in `market_event_metadata` are returned. If that table is populated only for one market type (e.g. MATCH_ODDS), you see at most **~40 rows** (one per event).
   - **Staleness (120 minutes):** Markets with no tick in the last 2 hours are dropped, so the count can be **~tens** (e.g. 20–40) depending on how many of the 40 events are still receiving ticks.

2. **Secondary:** The **date window** is a single UTC day. Only markets that have at least one tick in `stream_ingest.ladder_levels` with `publish_time` in that day are considered; if most activity is outside that day, the starting set is smaller.

**Evidence to collect:**

- Run `risk-analytics-ui/scripts/diagnose_stream_events_pipeline.sql` on the VPS and record:
  - §2: `stream_markets_in_date_window`
  - §3: `stream_market_count`, `with_metadata`, `without_metadata`
  - §6: `with_metadata`, `after_staleness_kept`
- Call the API: `GET /api/stream/events/by-date-snapshots?date=YYYY-MM-DD` and count the array length; it should match `after_staleness_kept` (and be ≤ 200, and often ~tens if metadata is one type and/or staleness applies).
- Optionally: streaming client logs for “Priority subscription: X events, Y market IDs” and the actual subscription payload (marketTypeCodes, no marketIds when using priority).

---

## Optional: increase the number of events shown

- **Increase subscription scope:** Raise `MAX_EVENTS` / `MAX_MARKET_IDS` in `PriorityMarketResolver` and ensure Betfair allows it (e.g. listMarketCatalogue maxResults, stream limits).
- **Ensure metadata for all stream market types:** Populate `market_event_metadata` for all five market types (e.g. from streaming client’s `public.markets` or a sync job), so the join doesn’t collapse to one market per event.
- **Relax or shorten staleness:** Reduce `STALE_MINUTES` in `stream_data.py` (e.g. from 120 to 60) so markets that haven’t had a tick in 1 hour still appear; or increase it if you want to keep “only recently active” but are comfortable with 2+ hours.
