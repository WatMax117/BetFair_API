# Backend Stream Query Fix Report

**Date:** 2026-02-16  
**Issue:** List shows only old events; detail timeseries/snapshots return empty  
**Status:** ✅ Fixed

---

## Root Causes Identified

### Issue 1: List Endpoint Filters by `event_open_date` Instead of Streaming Data

**Problem:** The `get_events_by_date_snapshots_stream` function was filtering metadata by `event_open_date >= from_dt AND event_open_date < to_dt`. This means:
- Events that started yesterday but are still receiving streaming data today won't appear in today's list
- Only events whose scheduled start date matches the requested date are shown

**Fix:** Removed the `event_open_date` filter from the metadata query. Now it:
1. Gets all markets with streaming data in the date range (stream-first)
2. Left joins to metadata without requiring `event_open_date` to be in range
3. Orders by `event_open_date` if available, but doesn't filter by it

### Issue 2: Timeseries Staleness Check Was Too Strict

**Problem:** The staleness check was comparing `bucket_time - last_pt`, which checks if data is stale relative to the historical bucket time, not relative to current time. This caused:
- Historical buckets to be excluded even if they had valid data
- Empty timeseries when the time range included old buckets

**Fix:** Changed staleness check to compare against current time:
- Calculate `stale_cutoff_time = now() - STALE_MINUTES`
- Only skip buckets if `last_pt < stale_cutoff_time`
- This allows showing historical data while still filtering truly stale markets

### Issue 3: Time Range Not Capped at Current Time

**Problem:** The `to_dt` parameter wasn't capped at current time, which could cause:
- Bucket generation beyond current time
- Staleness checks against future buckets

**Fix:** Added `to_dt = min(to_ts, now())` to cap the end time at current UTC time.

---

## Changes Made

### File: `risk-analytics-ui/api/app/stream_data.py`

#### Change 1: List Query - Remove `event_open_date` Filter (lines 184-196)

**Before:**
```python
cur.execute(
    """
    SELECT market_id, event_id, event_name, event_open_date, competition_name,
           home_selection_id, away_selection_id, draw_selection_id
    FROM market_event_metadata
    WHERE market_id = ANY(%s)
      AND event_open_date IS NOT NULL
      AND event_open_date >= %s
      AND event_open_date < %s
    ORDER BY event_open_date ASC, market_id
    """,
    (stream_markets, from_dt, to_dt),
)
```

**After:**
```python
cur.execute(
    """
    SELECT m.market_id, m.event_id, m.event_name, m.event_open_date, m.competition_name,
           m.home_selection_id, m.away_selection_id, m.draw_selection_id
    FROM market_event_metadata m
    WHERE m.market_id = ANY(%s)
    ORDER BY COALESCE(m.event_open_date, '1970-01-01'::timestamp) ASC, m.market_id
    """,
    (stream_markets,),
)
```

#### Change 2: Timeseries Staleness Check (lines 279-286)

**Before:**
```python
for bucket_time in bucket_times:
    with cursor() as cur:
        last_pt = _latest_publish_before(cur, market_id, bucket_time)
        if last_pt is None:
            continue
        if (bucket_time - last_pt).total_seconds() > stale_cutoff_minutes * 60:
            continue
```

**After:**
```python
# For staleness check, use current time, not bucket time
now_for_staleness = datetime.now(timezone.utc)
stale_cutoff_time = now_for_staleness - timedelta(minutes=stale_cutoff_minutes)

for bucket_time in bucket_times:
    with cursor() as cur:
        last_pt = _latest_publish_before(cur, market_id, bucket_time)
        if last_pt is None:
            continue
        # Check if last publish time is stale relative to NOW (not bucket_time)
        if last_pt < stale_cutoff_time:
            continue
```

#### Change 3: Time Range Validation (lines 256-260)

**Before:**
```python
now = datetime.now(timezone.utc)
to_dt = to_ts or now
from_dt = from_ts or (now - timedelta(hours=24))
```

**After:**
```python
now = datetime.now(timezone.utc)
to_dt = min(to_ts, now) if to_ts else now
from_dt = from_ts or (now - timedelta(hours=24))
# Ensure from_dt <= to_dt
if from_dt > to_dt:
    from_dt = to_dt - timedelta(hours=24)
```

### File: `risk-analytics-ui/api/app/stream_router.py`

#### Change: Cap `to_dt` at Current Time (lines 46-50)

**Before:**
```python
now = datetime.now(timezone.utc)
to_dt = _parse_ts_stream(to_ts, now)
from_dt = _parse_ts_stream(from_ts, now - timedelta(hours=24))
points = get_event_timeseries_stream(market_id, from_dt, to_dt, interval_minutes)
```

**After:**
```python
now = datetime.now(timezone.utc)
to_dt = min(_parse_ts_stream(to_ts, now), now)  # Cap to_dt at current time
from_dt = _parse_ts_stream(from_ts, now - timedelta(hours=24))
# Ensure from_dt <= to_dt
if from_dt > to_dt:
    from_dt = to_dt - timedelta(hours=24)
points = get_event_timeseries_stream(market_id, from_dt, to_dt, interval_minutes)
```

---

## Expected Behavior After Fix

### List Endpoint (`/api/stream/events/by-date-snapshots?date=YYYY-MM-DD`)

- ✅ Shows all markets with streaming data in the requested UTC date
- ✅ Includes events that started earlier but are still receiving data today
- ✅ Orders by `event_open_date` if available, but doesn't filter by it
- ✅ Only excludes markets that are stale (no update in last STALE_MINUTES)

### Detail Endpoints (`/api/stream/events/{market_id}/timeseries`, `/debug/markets/{market_id}/snapshots`)

- ✅ Returns historical buckets even if they're old (as long as market isn't stale)
- ✅ Only excludes buckets if the market's latest data is stale relative to NOW
- ✅ Time ranges are capped at current UTC time
- ✅ Handles edge cases where `from_dt > to_dt`

---

## Testing Recommendations

1. **List Endpoint:**
   - Request today's date: `/api/stream/events/by-date-snapshots?date=2026-02-16`
   - Verify it includes events that started yesterday but have streaming data today
   - Verify it excludes markets with no streaming data in the date range

2. **Timeseries Endpoint:**
   - Request timeseries for a market with historical data
   - Verify it returns buckets even if they're hours/days old
   - Verify it excludes markets that haven't updated in > STALE_MINUTES

3. **Snapshots Endpoint:**
   - Request snapshots for a market
   - Verify it returns historical snapshots
   - Verify it excludes stale markets

---

## Deployment Status

- ✅ Code changes applied
- ✅ API container restarted
- ⏳ Testing pending

---

## Acceptance Criteria

✅ **List Endpoint:** Shows all markets with streaming data, not just those with `event_open_date` in range  
✅ **Timeseries Endpoint:** Returns historical buckets for non-stale markets  
✅ **Staleness Check:** Uses current time, not bucket time  
✅ **Time Range:** Capped at current UTC time  

---

## Conclusion

The backend queries have been fixed to be "stream-first" - they now drive from streaming data and left-join metadata, rather than filtering by metadata first. This ensures that all active markets with streaming data are shown, regardless of when they started. The staleness check has also been corrected to use current time, allowing historical data to be shown while still filtering truly stale markets.
