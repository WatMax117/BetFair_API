# UI No Change Diagnosis Report

## Executive Summary

**Root Cause:** Streaming client inserts are failing due to missing partitions for today (2026-02-16). The partition provisioner has not run successfully after the table conversion, so no partitions exist for the current date. As a result:
- No new data is being written to `stream_ingest.ladder_levels` for today
- API correctly returns empty array `[]` for today's date
- UI correctly shows no events (there is no data to display)

**Status:** Data ingestion is broken. Partition provisioner needs to run to create today's partition.

---

## 1. UI Environment

**API Base URL:** Not directly verified from browser DevTools (requires browser access).  
**Expected:** UI calls `/api/stream/events/by-date-snapshots?date=<today>` which proxies to `http://127.0.0.1:8000/stream/events/by-date-snapshots?date=<today>` (or direct if configured).

**Container Status:**
- `risk-analytics-ui-api`: Up 13 minutes (recently restarted)
- `risk-analytics-ui-web`: Up 17 hours
- `netbet-streaming-client`: Up 10 days

---

## 2. API Responses

### `/health`
```json
{"status":"ok","ladder_levels_partition_horizon_days":30.0}
```
- HTTP 200 ✓
- Horizon = 30 days ✓

### `/metrics`
```
ladder_levels_partition_horizon_days 30.0
```
- Value = 30.0 (not -1) ✓

### `/stream/events/by-date-snapshots?date=2026-02-16`
```json
[]
```
- HTTP 200 ✓
- Empty array (no events) — **expected because no data exists for today**

### `/stream/events/by-date-snapshots?date=2026-02-15`
```json
[]
```
- HTTP 200 ✓
- Empty array (no events for yesterday either)

---

## 3. Database: Streaming Data for Today

**Query:**
```sql
SELECT count(*), min(publish_time), max(publish_time)
FROM stream_ingest.ladder_levels
WHERE publish_time::date = CURRENT_DATE;
```

**Result:**
- **Row count: 0**
- **min/max: NULL**

**Last 24 hours:**
- **Row count: 0**

**Latest data dates:**
- 2026-02-06: 405,835 rows (00:00:21 → 23:57:22)
- 2026-02-05: 307,447 rows (12:07:54 → 23:57:21)

**Conclusion:** No data exists for today (2026-02-16) or yesterday (2026-02-15). Last data is from 2026-02-06.

---

## 4. API Query Logic

**Endpoint:** `/api/stream/events/by-date-snapshots`  
**Function:** `get_events_by_date_snapshots_stream()` in `stream_data.py`

**Logic:**
1. Gets markets with ladder data in date range: `get_stream_markets_with_ladder_for_date(from_dt, to_dt)`
2. If no markets → returns `[]` (line 178-179)
3. Filters by metadata and staleness (STALE_MINUTES = 120)

**Manual SQL test:** Not run (would also return empty since no data exists).

**Conclusion:** API logic is correct. It returns empty because `get_stream_markets_with_ladder_for_date()` finds no markets with data in the date range.

---

## 5. Caching

**No caching detected:**
- No Redis mentioned in docker-compose
- No response caching middleware in API code
- Frontend uses standard fetch (no explicit cache headers)
- No CDN layer

**Conclusion:** Not a caching issue.

---

## 6. Partition Usage

**Partition pruning:** Not verified (no data to query).

**Partition list:** To be checked (see below).

---

## 7. Container Versions

**Running containers:**
- `risk-analytics-ui-api`: `netbet-risk-analytics-ui-api` (Up 13 minutes)
- `risk-analytics-ui-web`: `netbet-risk-analytics-ui-web` (Up 17 hours)
- `netbet-streaming-client`: `netbet-netbet-streaming-client` (Up 10 days)

**Last build times:** Not checked (requires `docker images`).

---

## CRITICAL FINDING: Streaming Client Insert Failures

**Streaming client logs show repeated failures:**

```
Postgres sink flush failed: ... ERROR: no partition of relation "ladder_levels" found for row
Detail: Partition key of the failing row contains (publish_time) = (2026-02-16 09:40:18.681+00)
```

**Timestamps in errors:**
- 2026-02-16 09:40:18.681+00
- 2026-02-16 09:43:18.682+00
- 2026-02-16 09:46:18.684+00

**Root cause:** The streaming client is trying to INSERT data for 2026-02-16, but no partition exists for that date. The partition provisioner should have created `ladder_levels_20260216` but either:
1. Has not run since the table conversion
2. Failed to create the partition
3. Created partitions with incorrect bounds

**Action required:** Verify partition coverage and trigger partition provisioner if needed.

---

## Required Actions

1. **Verify partition coverage:** Check if `ladder_levels_20260216` exists and covers the full day
2. **Check provisioner logs:** Verify if partition provisioner ran after API restart
3. **Manually create partition if missing:** Create partition for 2026-02-16 if provisioner failed
4. **Restart streaming client:** After partition exists, streaming client should resume writing
5. **Verify data ingestion:** Confirm rows start appearing in `stream_ingest.ladder_levels` for today

---

## 8. Partition Coverage Verification

**Partitions exist:**
- `ladder_levels_20260216`: `FROM ('2026-02-16 00:00:00+00') TO ('2026-02-17 00:00:00+00')` ✓
- `ladder_levels_20260217` through `ladder_levels_20260318`: All created ✓
- `ladder_levels_initial`: Historical data partition ✓

**Partition bounds:** All partitions use UTC timestamps and cover full days correctly.

**Streaming client JDBC URL:** `jdbc:postgresql://postgres:5432/netbet?currentSchema=stream_ingest`  
**Expected target:** `stream_ingest.ladder_levels` (partitioned table)

**Issue:** Despite partitions existing, streaming client logs show:
```
ERROR: no partition of relation "ladder_levels" found for row
Detail: Partition key of the failing row contains (publish_time) = (2026-02-16 09:40:18.681+00)
```

**ROOT CAUSE IDENTIFIED:** There are **TWO** partitioned `ladder_levels` tables:

1. **`public.ladder_levels`** (partitioned):
   - Partitions: `ladder_levels_initial` (2020-01-01 → 2026-02-05), `ladder_levels_20260205`, `ladder_levels_20260206`
   - **Missing:** No partition for 2026-02-16 (today) or later dates
   - **Last partition:** 2026-02-06

2. **`stream_ingest.ladder_levels`** (partitioned):
   - Partitions: `ladder_levels_initial` (2020-01-01 → 2026-02-16), `ladder_levels_20260216` through `ladder_levels_20260318`
   - **Has:** Full coverage through today + 30 days ✓

**The streaming client is writing to `public.ladder_levels`** (which has no partition for today), not `stream_ingest.ladder_levels` (which has partitions).

**Why:** Despite JDBC URL having `currentSchema=stream_ingest`, the streaming client's INSERT statements are likely using unqualified table names that default to `public` schema, or the connection isn't respecting the `currentSchema` parameter.

**Solution Options:**
1. **Create partitions for `public.ladder_levels`** for today + 30 days (quick fix)
2. **Fix streaming client to write to `stream_ingest.ladder_levels`** (proper fix - ensure schema qualification or connection respects `currentSchema`)
3. **Drop `public.ladder_levels`** if it's not needed (if all data should be in `stream_ingest`)

---

## Conclusion

**This is NOT a UI or API issue.** The UI correctly shows no events because:
1. No data exists for today (2026-02-16)
2. Streaming client inserts are failing despite partitions existing
3. API correctly returns empty array when no data exists

**The issue is data ingestion:** Streaming client is writing to `public.ladder_levels` (which has no partition for today) instead of `stream_ingest.ladder_levels` (which has full partition coverage). 

**Immediate fix:** Create partitions for `public.ladder_levels` for today + 30 days, OR fix streaming client to write to `stream_ingest.ladder_levels`.

**Long-term fix:** Ensure streaming client uses `stream_ingest.ladder_levels` as intended (schema-qualified INSERTs or proper `currentSchema` handling).
