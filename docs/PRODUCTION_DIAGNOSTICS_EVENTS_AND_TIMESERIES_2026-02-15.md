# Production Diagnostics – Events Dates & Timeseries Range

**Date:** 2026-02-15  
**Server:** 158.220.83.195 (root, id_ed25519_contabo)  
**Scope:** Confirm current-day events, snapshot recency, ingestion, API/UI behaviour, timeseries range.

---

## PART 1 – Database: Current Events and Snapshots

### Query: Events with last_snapshot (top 20 by event_open_date DESC)

| event_name | event_start_utc | last_snapshot |
|------------|------------------|---------------|
| Lyon v Nice | 2026-02-15 19:45:00+00 | 2026-02-15 10:22:27+00 |
| Napoli v Roma | 2026-02-15 19:45:00+00 | 2026-02-15 10:22:27+00 |
| Levante v Valencia | 2026-02-15 17:30:00+00 | 2026-02-15 09:33:48+00 |
| … (20 rows total, all 2026-02-15) | | |

### Counts

- **Events with event_open_date >= NOW():** **195**
- **Snapshots in last 24h:** **2,850**
- **Most recent snapshot (any market):** **2026-02-15 10:22:27.697358+00**

### Answers

- **Do we have events with event_open_date >= NOW()?** **Yes** (195).
- **Do we have recent snapshots (last_snapshot within the last few hours)?** **Yes.** Latest snapshot 10:22 UTC; top events show last_snapshot on 2026-02-15 between ~04:00 and 10:22 UTC.
- **Are there today’s events in the DB?** **Yes.** Top 20 by event_open_date are all 2026-02-15 (event_start_utc from 01:06 to 19:45 UTC).
- **Are snapshots being written currently?** **Yes.** MAX(snapshot_at) = 2026-02-15 10:22:27 UTC; 2,850 snapshots in last 24h.

---

## PART 2 – REST Client Ingestion

### Log excerpt (tail ~300)

```
2026-02-15 10:29:16 [INFO] betfair_rest_client: Daemon started (STICKY PRE-MATCH). K=200, kickoff_buffer=60s, interval=900s, catalogue_max=200, batch_size=50
2026-02-15 10:29:16 [INFO] betfair_rest_client: Session expired or missing, performing login...
2026-02-15 10:29:17 [INFO] betfair_rest_client: [Sticky] tick_id=1 duration_ms=1016 tracked_count=196 admitted_per_tick=196 expired=0 requests_per_tick=0 markets_polled=0
```

### Answers

- **Is Sticky running with K=200?** **Yes.** Log: `K=200`, `catalogue_max=200`.
- **Are markets being tracked and updated?** **Yes.** `tracked_count=196`, `admitted_per_tick=196`.
- **Are new snapshots being inserted?** **Yes.** DB shows 2,850 snapshots in last 24h and latest snapshot 10:22 UTC; REST client was restarted at 10:29 and is running.
- **Any ingestion errors?** **No** in the captured tail; daemon started and first tick completed normally.

---

## PART 3 – API Filtering Logic

### API logs (tail ~80)

- All relevant requests returned **200 OK** (leagues, league events, book-risk-focus, meta, timeseries, debug/snapshots).
- **No filtering errors** and **no incorrect WHERE** conditions observed in logs.

### Default time window and behaviour (from code + logs)

- **Default for `/leagues` and `/leagues/{name}/events`:** When `from_ts`/`to_ts` omitted, API uses `from_dt = now`, `to_dt = now + 24h` (UTC). With `include_in_play=True`, `from_effective = min(from_dt, now - in_play_lookback_hours)` (extends into the past).
- **Filtering:** All date filters use **UTC** (`event_open_date >= from_effective` and `event_open_date <= to_dt`).
- **Ordering:** **`ORDER BY e.event_open_date ASC`** (oldest first) for league events and book-risk-focus.

So the API does **not** exclude today’s events by design; it returns events in the requested UTC window, oldest first.

---

## PART 4 – UI Behaviour

### Observed requests (from API access logs)

- **Leagues:**  
  `from_ts=2026-02-14T10:30:40.954Z`, `to_ts=2026-02-16T10:30:40.954Z`  
  → **now−24h to now+24h** (UTC). Matches expected 48h window.
- **League events (e.g. Italian Serie C, English FA Cup):**  
  Same `from_ts`/`to_ts` (UTC).
- **Book-risk-focus:** Same range, UTC.

### Answers

- **What start/end timestamps are being sent?** **UTC**, roughly **now−24h** to **now+24h** (48h window).
- **Is the list sorted by ascending event date?** **Yes.** API returns `ORDER BY event_open_date ASC`; UI does not re-sort.
- **Client-side filtering removing events?** **No.** From code review, the UI does not filter out events by date; it displays what the API returns.

So the **first rows** in the list are the **earliest** in the window (e.g. yesterday or early today). If the UI “feels” like it shows “yesterday’s date”, it is because **ordering is oldest-first**, not because today’s events are missing.

---

## PART 5 – Timeseries Range

### API behaviour (code)

- **Endpoint:** `GET /events/{market_id}/timeseries` with `from_ts`, `to_ts`, `interval_minutes` (default 15).
- **SQL:** No `LIMIT`. Query returns all 15‑min buckets in `[from_dt, to_dt]` (one point per bucket, latest snapshot in bucket).
- **Default window:** `from_dt = now - 24h`, `to_dt = now` when params omitted.

### Observed usage (API logs)

- Timeseries called with **24h** windows (e.g. `from_ts=2026-02-14T10:31:01.136Z`, `to_ts=2026-02-15T10:31:01.136Z`).
- Also **6h** (e.g. 04:33–10:33) and **72h** (e.g. 2026-02-12 to 2026-02-15), consistent with UI range selector (6h / 24h / 72h).
- All timeseries requests returned **200 OK**.

### Answers

- **How many rows returned?** Not fully captured in this run (curl/wc timing); **code confirms no LIMIT** in the timeseries SQL.
- **Is there any LIMIT in SQL?** **No.**
- **Does the response contain more than 10 points?** **Yes** for any window with more than ~10 buckets (e.g. 24h at 15‑min = up to 96 points).
- **Is the chart limited to 10 by code?** **No.** Chart uses the full timeseries response; the only “10” is the **“Last 10 snapshots”** debug table (separate endpoint, `snapshots.slice(0, 10)`).
- **Or are there simply only ~10 snapshots available?** For markets with sparse data in the chosen window, the number of **buckets with data** can be small (e.g. ~10). That would be **data density**, not an API or UI cap.

---

## Required Deliverable – Short Written Report

### 1. Do current-day events exist in the DB?

**Yes.** 195 events with `event_open_date >= NOW()`. Top 20 by event_open_date are all 2026-02-15 (event_start_utc from 01:06 to 19:45 UTC).

### 2. Are snapshots current?

**Yes.** Most recent snapshot 2026-02-15 10:22:27 UTC; 2,850 snapshots in last 24h. Last snapshot per event in the top 20 is on 2026-02-15 (between ~04:00 and 10:22 UTC).

### 3. Is the issue ingestion, filtering, or ordering?

**Ordering (and possibly UX expectation).** Ingestion is healthy (REST client K=200, tracked_count=196, snapshots current). API filtering is UTC-based and does not exclude today. Events are returned **oldest first** (`event_open_date ASC`), so the **first** rows are the **earliest** in the 48h window (e.g. yesterday or early today). If the UI “shows yesterday’s date”, it is because the list is ordered that way, not because today’s events are missing.

### 4. Is timeseries limited in API or UI?

**No.** The timeseries endpoint has **no row limit** in SQL and returns the full bucketed range for the requested window. The chart uses this full response. The only “10” in the UI is the **“Last 10 snapshots”** debug table (separate data source). If the chart shows few points, it is due to **data density** in the selected range (e.g. few snapshots in that window for that market), not a hard limit.

### 5. Recommended minimal fixes

- **Date visibility**  
  - Expose **event start**, **market start** (`market_start_time`), and **market creation** (e.g. `first_seen_at`) from API and show them clearly in the EventDetail header in local time.  
  - (As in diagnosis doc: extend `/events/{market_id}/meta` and optionally list endpoints; update UI labels.)

- **Ordering**  
  - **Option A:** Add a UI control to sort by **event_open_date DESC** (newest/future first) so “today” and “tomorrow” appear at the top.  
  - **Option B:** Keep ASC but add a clear label, e.g. “Events (earliest first in selected range)”.  
  - **Option C:** Default to a “future-only” or “today and tomorrow” window so the first page is not dominated by past events.

- **Chart density**  
  - No change needed for “full range”; API already returns full window.  
  - If charts look sparse: (1) confirm that the selected range (6h/24h/72h) contains enough snapshots for that market; (2) optionally add a **7d** (or longer) range option for markets with longer history.

---

**No implementation changes were made.** This report is diagnosis only; implement the above only after you confirm the diagnosis with your own run if needed.
