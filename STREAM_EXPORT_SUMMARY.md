# Streaming Database Export Summary

**Date**: 2026-02-16  
**Database**: `netbet` (PostgreSQL)  
**Source**: `stream_ingest.ladder_levels` (partitioned table)

---

## Confirmed Configuration

### Side Values
- **BACK**: `side = 'B'` ✓
- **LAY**: `side = 'L'` (not exported)

### Market Type Filter
- **Filter**: `market_type = 'MATCH_ODDS_FT'` (from `public.markets`)
- **Other types found**: `OVER_UNDER_05_HT`, `OVER_UNDER_25_FT`, `HALF_TIME_RESULT`

### Selection Mapping
- **Source**: `public.market_event_metadata`
- **Columns used**: `home_selection_id`, `away_selection_id`, `draw_selection_id`
- **Markets with complete mappings**: 792 markets

### Data Volume
- **Total BACK rows (levels 1-8)**: 308,570 rows
- **Markets**: 119 distinct markets
- **Selections**: 116 distinct selections

---

## Export A: 5-Minute Aggregated Time Series

**File**: `stream_back_5min_levels8.csv`  
**Size**: 2.33 MB (2,326,495 bytes)  
**Format**: CSV with headers

### Columns (55 total)

**Metadata**:
- `event_id`
- `market_id`
- `market_start_time` (timestamp with time zone)
- `bucket_start_utc` (5-minute bucket start)
- `publish_time_min_utc` (min publish_time in bucket)
- `received_time_max_utc` (max received_time in bucket)

**HOME outcome** (8 levels):
- `home_back_odds_l1` through `home_back_odds_l8`
- `home_back_size_l1` through `home_back_size_l8`

**AWAY outcome** (8 levels):
- `away_back_odds_l1` through `away_back_odds_l8`
- `away_back_size_l1` through `away_back_size_l8`

**DRAW outcome** (8 levels):
- `draw_back_odds_l1` through `draw_back_odds_l8`
- `draw_back_size_l1` through `draw_back_size_l8`

### Aggregation Logic
- **Time bucket**: 5-minute intervals using `date_bin('5 minutes', publish_time, TIMESTAMPTZ '1970-01-01')`
- **Aggregation**: `MAX()` per (market_id, bucket_start, selection_id, level)
- **Grouping**: By `event_id`, `market_id`, `market_start_time`, `bucket_start`
- **Selection mapping**: Uses `public.market_event_metadata` to map `selection_id` → home/away/draw

### Sample Row
```
event_id,market_id,market_start_time,bucket_start_utc,publish_time_min_utc,received_time_max_utc,home_back_odds_l1,home_back_size_l1,...
35166788,1.252931546,2026-02-05 20:00:00+00,2026-02-05 12:10:00+00,2026-02-05 12:10:54.031+00,2026-02-05 12:13:54.047+00,...
```

---

## Export B: Last Snapshot Per Market+Selection

**File**: `stream_back_last_levels8.csv`  
**Size**: 29.7 KB (29,705 bytes)  
**Format**: CSV with headers

### Columns (16 total)

**Metadata**:
- `event_id`
- `market_id`
- `market_start_time`
- `selection_id`
- `last_publish_time_utc`
- `last_received_time_utc`

**Last observed values** (8 levels):
- `back_odds_l1` through `back_odds_l8`
- `back_size_l1` through `back_size_l8`

### Selection Logic
- **Method**: `DISTINCT ON (market_id, selection_id, level)` ordered by `publish_time DESC`
- **Grouping**: By `event_id`, `market_id`, `market_start_time`, `selection_id`
- **Pivot**: `MAX(CASE WHEN level = N THEN ...)` to create level columns

### Sample Row
```
event_id,market_id,market_start_time,selection_id,last_publish_time_utc,last_received_time_utc,back_odds_l1,back_size_l1,...
35166788,1.252931546,2026-02-05 20:00:00+00,58805,2026-02-05 21:54:21.86+00,2026-02-05 21:54:21.871+00,1.3,2000,1.2,7.78,...
```

---

## Notes

1. **Selection mapping**: Export A uses `public.market_event_metadata` to pivot by home/away/draw. If a market lacks mapping, those columns will be NULL.

2. **Time reference**: 
   - `publish_time` = Betfair event time (when price was published)
   - `received_time` = Ingestion time (when our system received it)

3. **Levels**: Only levels 1-8 are exported. If a selection has fewer than 8 levels available, higher-level columns will be NULL.

4. **Market filter**: Only `MATCH_ODDS_FT` markets are included. Other market types (half-time, over/under) are excluded.

5. **Partitioning**: The query uses the parent table `stream_ingest.ladder_levels`, which automatically includes all date partitions.

---

## Files Delivered

- ✅ `stream_back_5min_levels8.csv` (2.33 MB)
- ✅ `stream_back_last_levels8.csv` (29.7 KB)

Both files are located in: `c:\Users\WatMax\NetBet\`

---

## SQL Queries Used

See:
- `export_5min_copy.sql` - Export A query
- `export_last_copy.sql` - Export B query
