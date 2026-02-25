# /stream shows no events — VPS diagnostic results

**Date:** 2026-02-16  
**Endpoint:** `/api/stream/events/by-date-snapshots` returns 200 but body `[]`.

---

## 1. Data in `stream_ingest` (VPS)

| Query | Result |
|-------|--------|
| **total_rows** (ladder_levels) | **713,282** |
| **last_publish_time** (ladder_levels) | **2026-02-06 23:57:22.957+00** |
| **rows_last_12h** (ladder_levels) | **0** |
| **total_liquidity_rows** (market_liquidity_history) | **17,303** |
| **max(publish_time)** (market_liquidity_history) | **2026-02-06 23:57:22.957+00** |

---

## 2. Date filtering

| Query | Result |
|-------|--------|
| Count where `publish_time::date = '2026-02-16'` | **0** |
| Count where `(publish_time AT TIME ZONE 'utc')::date = '2026-02-16'` | **0** |
| **today_utc** (server) | **2026-02-16** |
| Count for today (UTC date) | **0** |

Conclusion: There is **no** ladder data with `publish_time` on 2026-02-16. All data is from **2026-02-06** or earlier.

---

## 3. Metadata join

| Query | Result |
|-------|--------|
| Ladder markets (last 12h) **without** metadata | **(0 rows)** — N/A (no data in last 12h) |
| Ladder markets (last 12h) **with** metadata (sample) | **(0 rows)** — no ladder in last 12h |

So the metadata join is not the cause: the “last 12h” set is empty because there is no recent ladder data.

---

## 4. API query logic (binding)

The stream endpoint does the following:

1. **Date range:** For a given calendar date (e.g. 2026-02-16), `from_dt` = that date 00:00 UTC, `to_dt` = next day 00:00 UTC.
2. **Stream markets:** `get_stream_markets_with_ladder_for_date(from_dt, to_dt)` returns market IDs that have **at least one** row in `stream_ingest.ladder_levels` with `publish_time >= from_dt AND publish_time < to_dt`.
3. **Metadata:** Events are loaded from `market_event_metadata` for those market IDs with `event_open_date` in the same `[from_dt, to_dt)`.
4. **Staleness:** For each market, the latest `publish_time` at or before the latest 15-min bucket must be within `STALE_MINUTES` (120) of that bucket.

So:

- The bucket date range **does** match the calendar day (UTC).
- The query **does** require ladder data in that day; it does **not** require liquidity rows for the initial list (liquidity is used per market when building the snapshot).
- Staleness can exclude a market only if its last update is older than 120 minutes before the bucket; it does not explain an empty list when **no** markets have any `publish_time` in the selected date.

**Conclusion:** The binding is correct. For 2026-02-16 there are simply **no** ladder rows with `publish_time` in that day, so `stream_markets` is empty and the API correctly returns `[]`.

---

## Root cause

**No recent ingestion into `stream_ingest`.**

- Latest data in `stream_ingest.ladder_levels` (and `market_liquidity_history`) is from **2026-02-06 23:57 UTC**.
- There are **0** rows in the last 12 hours and **0** rows for 2026-02-16.
- So the situation is **(1) No recent data** — the streaming writer is not currently writing to `stream_ingest` (or has been stopped since 2026-02-06).

---

## What to do

1. **Confirm streaming client**
   - Check that the Betfair streaming client (e.g. `netbet-streaming-client`) is running on the VPS and that it is configured to write to the same Postgres DB and **stream_ingest** schema (e.g. `currentSchema=stream_ingest` or equivalent).
   - Check its logs for connection/insert errors or restarts after 2026-02-06.

2. **Sanity-check the UI with existing data**
   - In the `/stream` UI, select date **2026-02-06** (the date of the latest data).  
   - If events and charts then appear, the “no events” behaviour for 2026-02-16 is confirmed to be due to missing data, not query/metadata/staleness logic.

3. **Backend logs**
   - No change needed to the API for this issue; no errors are expected when returning an empty list. If you see any errors in the API logs when calling `/api/stream/events/by-date-snapshots`, share those lines for follow-up.

---

## Summary table

| Check | Finding |
|-------|--------|
| Data exists in stream_ingest? | Yes — 713k ladder rows, 17k liquidity rows |
| Recent data (last 12h)? | No — 0 rows; last_publish_time = 2026-02-06 23:57 UTC |
| Data for 2026-02-16? | No — 0 rows |
| Timezone mismatch? | No — explicit UTC date still gives 0 for 2026-02-16 |
| Metadata excluding markets? | N/A — no recent ladder data to join |
| Query logic / binding? | Correct — returns [] when no ladder data in selected date |
| **Conclusion** | Ingestion not writing to stream_ingest since 2026-02-06; restart/configure streaming client and verify writes. |
