# Diagnostic Report: Outdated Events in UI, Date Display, and Timeseries Chart Range

**Date:** 2026-02-15  
**Scope:** Part 1 (outdated events), Part 2 (display required dates), Part 3 (chart limited to 10 snapshots).  
**Status:** Diagnosis only; no implementation changes.

---

## Schema Note for Part 1 SQL

The requested SQL uses `event_start_utc` and `event_name` from `market_derived_metrics`. In this codebase:

- **`market_derived_metrics`** has: `snapshot_id`, `snapshot_at`, `market_id`, and metric columns only. It does **not** have `event_name` or `event_start_utc`.
- **`market_event_metadata`** has: `event_name`, `event_open_date`, `market_start_time`, `first_seen_at`, etc.

Use this adjusted query for the DB check:

```sql
SELECT e.event_name,
       e.event_open_date AS event_start_utc,
       MAX(d.snapshot_at) AS last_snapshot
FROM market_derived_metrics d
JOIN market_event_metadata e ON e.market_id = d.market_id
GROUP BY e.event_name, e.event_open_date
ORDER BY e.event_open_date DESC
LIMIT 20;
```

Confirm:

- Are there events with `event_open_date >= NOW()`?
- Are snapshots being inserted for today? (check `last_snapshot` recency)

---

## Part 1 – Outdated Events in UI

### 1. Database

- **Relevant table:** `market_event_metadata` (event names, dates); `market_derived_metrics` (snapshots per market).
- **Date column:** `event_open_date` (TIMESTAMPTZ). There is no column named `event_start_utc`; treat `event_open_date` as event start in UTC.
- **Current events:** Run the adjusted SQL above on production. If all `event_open_date` are in the past, the DB has no “today” events and the UI will show older events only.

### 2. REST client

- Check `docker logs --tail=300 netbet-betfair-rest-client` for:
  - Current-day markets being tracked (e.g. sticky catalogue with today’s kickoffs).
  - New snapshots being written (no persistent errors, no TOO_MUCH_DATA blocking ingestion).

If the REST client is not ingesting today’s markets (e.g. due to catalogue/window or errors), the DB will only have yesterday’s (or older) data and the UI will reflect that.

### 3. API filtering

**Location:** `risk-analytics-ui/api/app/main.py`

- **`/leagues`:**  
  - Uses `market_event_metadata.event_open_date` with:
    - `event_open_date >= from_effective` and `event_open_date <= to_dt`.
  - Defaults when query params are omitted: `from_dt = now`, `to_dt = now + 24h` (UTC).
  - With `include_in_play=True`, `from_effective = min(from_dt, now - in_play_lookback_hours)` (extends window into the past).

- **`/leagues/{league_name}/events`** and **`/events/book-risk-focus`:**  
  - Same logic: filter on `event_open_date` in UTC; no extra filter that would drop “today” explicitly.
  - Order: `ORDER BY e.event_open_date ASC` (earliest first).

So the API does **not** filter out “today” by mistake. It returns events in `[from_effective, to_dt]` in UTC. If the UI sends a window that includes today, the API will return today’s events if they exist in the DB.

### 4. UI filtering

**Location:** `risk-analytics-ui/web/src/components/LeaguesAccordion.tsx`

- **Window:** `getWindowDates(windowHours)` with default 24h:
  - `from = now - 24h`, `to = now + 24h` (symmetric 48h window around “now”).
- **Request:** `from_ts` and `to_ts` are sent as `toISOString()` (UTC).
- **No client-side filter** on event date; the list is whatever the API returns, ordered by `event_open_date` ASC.

So the first rows are the **earliest** in the window (e.g. yesterday if the window starts 24h ago). That can look like “only yesterday’s date” if:

- The user expects “today and future” first, or
- There are no events with `event_open_date >= today` in the DB (REST client not ingesting today).

### Root cause (outdated events)

- **If the DB has current-day events and recent snapshots:** The issue is not DB/API/UI filtering logic; it may be UX (order or default window) or labelling.
- **If the DB has no current-day events or stale snapshots:** The issue is **upstream data**: REST client not tracking/writing today’s markets or snapshots. Then the UI correctly shows “outdated” because that’s all that exists.
- **Timezone:** API and DB use UTC. UI sends UTC and displays with `toLocaleString(undefined, …)`, so conversion to local time is consistent. No evidence of a “server local vs UTC” bug in the code.

**Deliverable summary (Part 1):**

- Run the adjusted SQL and REST client logs to confirm whether **current events exist in the DB** and **snapshots are recent**.
- If yes → root cause is likely ordering/UX or user expectation (yesterday vs today).
- If no → root cause is **data ingestion** (REST client / catalogue / window), not the UI or API filter.

---

## Part 2 – Display Required Dates in UI

### 1. What the DB has

**`market_event_metadata`** (from `betfair-rest-client/scripts/create_market_event_metadata.sql`):

| Column               | Type        | Notes                          |
|----------------------|------------|---------------------------------|
| `event_open_date`    | TIMESTAMPTZ| Event start (kickoff).          |
| `market_start_time`  | TIMESTAMPTZ| Market start (if different).   |
| `first_seen_at`      | TIMESTAMPTZ| First time we saw this market. |
| (no `market_created_at`) | —      | Use `first_seen_at` as proxy.   |

So the DB has:

- **Event start:** `event_open_date`
- **Market start:** `market_start_time`
- **Creation proxy:** `first_seen_at` (no separate “market creation” from Betfair in this schema)

### 2. What the API exposes

- **`/events/{market_id}/meta`** currently returns:  
  `market_id`, `event_name`, `event_open_date`, `competition_name`, `home_runner_name`, `away_runner_name`, `draw_runner_name`.  
  It does **not** return `market_start_time` or `first_seen_at`.

- **`/leagues/{league}/events`** and **`/events/book-risk-focus`** return `event_open_date` per event; they do not expose `market_start_time` or creation.

So:

- **Event start datetime:** Already in API as `event_open_date` (UTC ISO).
- **Market start datetime:** In DB as `market_start_time`; **not** in API.
- **Market creation proxy:** In DB as `first_seen_at`; **not** in API.

### 3. Required changes (for implementation phase)

- **API:** Extend `/events/{market_id}/meta` (and, if desired, events list endpoints) to include:
  - `market_start_time` (or `market_start_utc`) if present in DB.
  - `first_seen_at` (or `market_created_at`) as creation proxy.
- **UI:** In EventDetail header (and anywhere else showing event/market dates):
  - Show **event start** (event_open_date) in local time.
  - Show **market start** when available and different from event start.
  - Show **market creation** (first_seen_at) when available.
  - Use consistent local-time formatting and clear labels (e.g. “Event start (local)”, “Market start (local)”).

---

## Part 3 – Chart Possibly Limited to 10 Snapshots

### 1. API `/events/{market_id}/timeseries`

**Location:** `risk-analytics-ui/api/app/main.py` – `get_event_timeseries()`

- **No row limit.** The query:
  - Filters `market_derived_metrics` by `market_id` and `snapshot_at IN [from_dt, to_dt]`.
  - Buckets by `interval_minutes` (default 15).
  - Uses `DISTINCT ON (bucket_epoch)` to take one point per bucket (latest in bucket).
  - Returns all such points in `[from_dt, to_dt]` with `ORDER BY snapshot_at ASC`.
- **Default window:** `from_dt = now - 24h`, `to_dt = now` when `from_ts`/`to_ts` are omitted.
- **No `LIMIT 10`** (or any limit) in this endpoint.

So the timeseries endpoint returns the **full range** in the requested window (e.g. up to 96 points for 24h at 15‑min buckets), not “last 10”.

### 2. Debug snapshots endpoint (separate from chart)

**`GET /debug/markets/{market_id}/snapshots`**

- Uses `ORDER BY m.snapshot_at DESC` and `LIMIT %s` (default 500, max 500).
- The UI calls this with `limit = 200` and then does **`last10 = snapshots.slice(0, 10)`** for the **“Last 10 snapshots (copy-friendly)” table** only.

So the “10” limit applies only to the **debug snapshot table**, not to the timeseries used for the chart.

### 3. UI – chart vs “Last 10” table

**Location:** `risk-analytics-ui/web/src/components/EventDetail.tsx`

- **Chart:** `chartData = timeseries.map(...)`. Data source is **`timeseries`**, which comes from **`fetchEventTimeseries(marketId, from, to, 15)`** (i.e. the **timeseries** endpoint). Same `from`/`to` as the 6h/24h/72h selector.
- **“Last 10 snapshots” table:** Uses **`snapshots`** from **`fetchMarketSnapshots(marketId, from, to, 200)`** (debug endpoint), then **`last10 = snapshots.slice(0, 10)`**.

So:

- The chart is **not** fed from the “Last 10 snapshots” array.
- The chart uses the **full timeseries** returned by the API for the selected range (6h / 24h / 72h).

If the chart **appears** to show only ~10 points, plausible causes are:

1. **Data:** That market has few snapshots in the selected window (e.g. new market, or low ingest frequency), so after 15‑min bucketing there are only ~10 buckets with data.
2. **Backend/DB:** The timeseries query or DB has few rows for that market in the window (e.g. no recent writes).
3. **Frontend bug:** Unlikely given current code (chart is clearly wired to `timeseries`), but worth a quick check that no other code overwrites `timeseries` or limits it to 10.

### Deliverable (Part 3)

- **Is the chart limited to 10 in code?** **No.** The chart uses the full `timeseries` response; the only “10” in the UI is the debug “Last 10 snapshots” table.
- **Where could “only 10 points” come from?** From the **data**: few snapshots in the chosen time range for that market, or a problem in data ingestion. Not from a hard-coded limit in the timeseries API or in the chart data path.
- **Proposed approach:**  
  - Keep timeseries as full range (or configurable window); keep “Last 10” table as-is.  
  - If users need more points on the chart: ensure the selected range (6h/24h/72h) is appropriate and that the REST client is writing snapshots for that market in that window; optionally add a larger range (e.g. 7d) if needed.

---

## Acceptance Criteria – Summary

| Criterion | Finding |
|-----------|--------|
| **1. Root cause of outdated events** | Either **(A)** no current events in DB / no recent snapshots → fix REST client / catalogue / window, or **(B)** data is current → UX (order/window) or expectation (yesterday vs today). Run adjusted SQL + REST client logs to decide. |
| **2. Current events in DB?** | To be confirmed with the adjusted SQL and REST client logs on production. |
| **3. Timeseries limited to 10?** | **No.** Timeseries API has no limit; chart uses full timeseries. Only “10” is the debug “Last 10 snapshots” table. If chart shows ~10 points, it’s due to data in the selected window, not a 10-point cap. |
| **4. Minimal changes for dates** | Extend API meta (and optionally list endpoints) with `market_start_time` and `first_seen_at`; in EventDetail (and elsewhere) show event start, market start, and creation in local time with clear labels. |
| **5. Minimal changes for chart range** | No code change needed for “full range”; timeseries already returns full window. If needed, add a longer range option (e.g. 7d) and/or verify ingestion so enough snapshots exist in the chosen window. |

---

## Recommended Next Steps (after diagnosis confirmed)

1. **Run on production:** Adjusted SQL (Part 1) and `docker logs --tail=300 netbet-betfair-rest-client`; confirm whether current events and recent snapshots exist.
2. **If data is stale:** Fix REST client / catalogue / TOO_MUCH_DATA / window so today’s markets and snapshots are written.
3. **Part 2:** Add `market_start_time` and `first_seen_at` to `/events/{market_id}/meta` (and optionally to events list responses); update EventDetail to show event start, market start, and creation in local time.
4. **Part 3:** No change to timeseries limit. If chart still looks sparse, verify data density and consider a 7d (or longer) range option.

No implementation changes have been made in this phase; the above is diagnosis and proposed approach only.
