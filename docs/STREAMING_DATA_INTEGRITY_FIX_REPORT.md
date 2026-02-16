# Streaming Data Integrity Fix Report

**Date:** 2026-02-16  
**Issues:** Missing `stream_ingest.traded_volume` table and snapshot API returning empty  
**Status:** ✅ **ISSUE 1 RESOLVED** | ⚠️ **ISSUE 2 DIAGNOSIS IN PROGRESS**

---

## Issue 1 — Missing `stream_ingest.traded_volume` and `market_lifecycle_events`

### Problem

Streaming client logs showed:
```
ERROR: relation "stream_ingest.traded_volume" does not exist
```

The streaming client code writes to:
- `stream_ingest.traded_volume`
- `stream_ingest.market_lifecycle_events`

But these tables existed only in `public` schema, not `stream_ingest`.

### Root Cause

When we schema-qualified the streaming SQL to use `stream_ingest.*`, we updated the INSERT statements but the tables themselves were never created in `stream_ingest` schema. They existed only in `public` (created by Flyway V1).

### Solution

**Created missing tables in `stream_ingest` schema:**

```sql
CREATE TABLE stream_ingest.traded_volume (
    market_id     VARCHAR(32)  NOT NULL,
    selection_id  BIGINT       NOT NULL,
    price         DOUBLE PRECISION NOT NULL,
    size_traded   DOUBLE PRECISION NOT NULL,
    publish_time  TIMESTAMPTZ  NOT NULL,
    received_time TIMESTAMPTZ  NOT NULL,
    PRIMARY KEY (market_id, selection_id, price, publish_time)
);

CREATE TABLE stream_ingest.market_lifecycle_events (
    market_id     VARCHAR(32)  NOT NULL,
    status        VARCHAR(32),
    in_play       BOOLEAN,
    publish_time  TIMESTAMPTZ  NOT NULL,
    received_time TIMESTAMPTZ  NOT NULL
);
```

**Script:** `scripts/create_stream_ingest_tables.sql`

### Verification

**After restart:**
- ✅ No "relation does not exist" errors in streaming logs
- ✅ `stream_ingest.traded_volume` receiving writes (61 rows in last 10 minutes)
- ✅ `stream_ingest.market_lifecycle_events` table exists

**Status:** ✅ **RESOLVED**

---

## Issue 2 — Snapshot API Endpoint Returns Empty Array

### Problem

**Endpoint:** `/api/stream/events/by-date-snapshots?date=2026-02-16`

**Returns:** `[]` (empty array)

**Despite:**
- 15,255+ ticks in last 30 minutes
- `publish_time` advancing (max: 2026-02-16 11:31:42+00)
- 76 markets with stream data for 2026-02-16
- 15 markets matching metadata filter

### Diagnostic Steps

#### Step 1: API Query Logic

**Code Location:** `risk-analytics-ui/api/app/stream_data.py` → `get_events_by_date_snapshots_stream()`

**Query Flow:**
1. Get markets with ladder data: `get_stream_markets_with_ladder_for_date(from_dt, to_dt)`
2. Query metadata: `SELECT ... FROM market_event_metadata WHERE market_id = ANY(...) AND event_open_date >= from_dt AND event_open_date < to_dt`
3. For each market:
   - Get latest publish_time before `latest_bucket`: `_latest_publish_before(market_id, latest_bucket)`
   - Filter if `last_pt < stale_cutoff` (STALE_MINUTES = 120)
   - Build runners and return result

#### Step 2: Manual SQL Execution

**Test Query Results:**
- ✅ **76 markets** have stream data for 2026-02-16
- ✅ **15 markets** match metadata WITH `event_open_date` filter
- ✅ **16 markets** match metadata WITHOUT filter (1 has NULL `event_open_date`)

**Sample Market:**
- `market_id`: `1.253003735`
- `event_open_date`: `2026-02-16 19:30:00+00` (IN_RANGE)

#### Step 3: Staleness Filter Analysis

**Configuration:**
- `STALE_MINUTES = 120` (temporarily increased for diagnostics)
- `latest_bucket` = latest 15-min bucket in the day (e.g., `2026-02-16 23:45:00+00`)
- `stale_cutoff` = `latest_bucket - 120 minutes` = `2026-02-16 21:45:00+00`

**Current Data:**
- Max `publish_time`: `2026-02-16 11:31:42+00`
- This is **before** `stale_cutoff` (21:45), so markets should pass staleness check

**Potential Issue:**
- If `latest_bucket` is calculated as `23:45` (end of day), but current time is only `11:32`, then `_latest_publish_before(market_id, 23:45)` might return `11:31`, which is > 10 hours before the bucket time
- However, the staleness check compares `last_pt < stale_cutoff` (21:45), and `11:31 < 21:45` is true, so it should pass

**Alternative Issue:**
- The `_latest_publish_before` function queries `publish_time <= bucket_time`
- If `bucket_time` is `23:45` and data exists up to `11:31`, it should return `11:31`
- But if the function is called with a future bucket time that has no data yet, it might behave unexpectedly

### Next Steps for Diagnosis

1. **Check actual bucket calculation:**
   - What is `latest_bucket` for 2026-02-16 at current time (11:32 UTC)?
   - Should it be `11:30:00` (current bucket) or `23:45:00` (end-of-day bucket)?

2. **Test staleness logic manually:**
   - Run `_latest_publish_before` equivalent query for sample markets
   - Verify staleness cutoff calculation

3. **Check API logs:**
   - Are there any errors or warnings?
   - Is the function being called correctly?

4. **Verify metadata completeness:**
   - Do all 15 matching markets have required fields (`home_selection_id`, `away_selection_id`, `draw_selection_id`)?

### Proposed Fix (Pending Diagnosis)

**Option A:** If bucket calculation is wrong:
- Fix `_bucket_times_in_range` to only return buckets up to current time, not end of day

**Option B:** If staleness filter is too aggressive:
- Reduce `STALE_MINUTES` from 120 to 20 (as noted in code comment)

**Option C:** If metadata is incomplete:
- Ensure `market_event_metadata` is populated for all streaming markets

---

## Summary

### ✅ Resolved

1. **Missing `stream_ingest.traded_volume` table** — Created, writes succeeding
2. **Missing `stream_ingest.market_lifecycle_events` table** — Created

### ⚠️ In Progress

1. **Snapshot API returns empty** — Diagnosis ongoing:
   - Data exists (76 markets, 15 match metadata)
   - Query logic appears correct
   - Staleness filter may be too aggressive or bucket calculation incorrect

---

## Files Created

- `scripts/create_stream_ingest_tables.sql` — Creates missing tables in `stream_ingest`
- `scripts/test_snapshot_api_query.sql` — Diagnostic queries for API issue
- `scripts/test_staleness_logic.sql` — Tests staleness filtering logic
- `docs/STREAMING_DATA_INTEGRITY_FIX_REPORT.md` — This report

---

## Acceptance Criteria Status

| Criterion | Status |
|-----------|--------|
| No "relation does not exist" errors | ✅ **MET** |
| `stream_ingest.traded_volume` writes succeed | ✅ **MET** (61 rows in 10 min) |
| Snapshot endpoint returns non-empty data | ⚠️ **PENDING** (diagnosis in progress) |
| UI displays today's events | ⚠️ **PENDING** (depends on API fix) |
| No schema ambiguity remains | ✅ **MET** |

---

**Next Action:** Complete diagnosis of snapshot API staleness/bucket logic and implement fix.
