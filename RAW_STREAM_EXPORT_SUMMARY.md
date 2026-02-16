# Raw Streaming Export Summary

**Date**: 2026-02-16  
**Database**: `netbet` (PostgreSQL)  
**Source**: `stream_ingest.ladder_levels` (partitioned table)

---

## Export: Raw Tick-by-Tick Ladder Updates

**File**: `stream_back_raw_levels8.csv`  
**Size**: 27.5 MB (28,858,640 bytes)  
**Rows**: 248,484 data rows + 1 header row = 248,485 total lines  
**Format**: CSV with headers

### Filters Applied

- **Market type**: `MATCH_ODDS_FT` (from `public.markets`)
- **Side**: `side = 'B'` (BACK only)
- **Levels**: `level BETWEEN 1 AND 8`
- **Time range**: All available data (Feb 5-6, 2026)
  - Min publish_time: `2026-02-05 12:07:54.024+00`
  - Max publish_time: `2026-02-06 23:57:22.957+00`

### Columns (9 total)

1. `event_id` - Event identifier (from markets table)
2. `market_id` - Market identifier
3. `market_start_time` - Match start time (timestamptz)
4. `selection_id` - Selection/runner identifier
5. `level` - Ladder level (1-8)
6. `publish_time` - Betfair publish timestamp (timestamptz)
7. `received_time` - Ingestion timestamp (timestamptz)
8. `back_odds` - Back price (from `price` column)
9. `back_size` - Back size (from `size` column)

### Data Characteristics

- **No aggregation**: One row per ladder update
- **No pivoting**: `selection_id` kept as-is (not mapped to home/away/draw)
- **Chronological order**: Sorted by `market_id`, `selection_id`, `level`, `publish_time`
- **Raw timestamps**: Both `publish_time` (event time) and `received_time` (ingestion time) included

### Sample Rows

```csv
event_id,market_id,market_start_time,selection_id,level,publish_time,received_time,back_odds,back_size
35166788,1.252931546,2026-02-05 20:00:00+00,58805,1,2026-02-05 12:10:54.031+00,2026-02-05 12:10:54.055+00,3.3,11090.28
35166788,1.252931546,2026-02-05 20:00:00+00,58805,1,2026-02-05 12:13:54.034+00,2026-02-05 12:13:54.047+00,3.3,11090.28
```

---

## Companion Export: Selection Mapping

**File**: `market_selection_mapping.csv`  
**Size**: 26.4 KB (26,377 bytes)  
**Format**: CSV with headers

### Purpose

Maps `market_id` to `home_selection_id`, `away_selection_id`, `draw_selection_id` for later use in labeling raw exports.

### Columns (4 total)

1. `market_id` - Market identifier
2. `home_selection_id` - Home team selection ID
3. `away_selection_id` - Away team selection ID
4. `draw_selection_id` - Draw selection ID

### Filter

Only includes markets where all three selection IDs are non-null (792 markets).

### Usage

Join this mapping table to `stream_back_raw_levels8.csv` on `market_id` and match `selection_id` to determine if a row represents home, away, or draw outcome.

---

## Comparison with Aggregated Exports

| Export Type | File Size | Rows | Granularity |
|-------------|-----------|------|-------------|
| **Raw** (this export) | 27.5 MB | 248,484 | Tick-by-tick |
| **5-minute aggregated** | 2.33 MB | ~thousands | 5-minute buckets |
| **Last snapshot** | 29.7 KB | ~hundreds | One row per market+selection |

The raw export is ~12x larger than the 5-minute aggregated export, reflecting the full temporal resolution of ladder updates.

---

## SQL Query Used

See `export_raw_stream.sql` for the complete query.

**Key points**:
- Joins `stream_ingest.ladder_levels` with `public.markets` to get `event_id` and `market_start_time`
- Filters to `MATCH_ODDS_FT` markets only
- No time filter (exports all available data)
- Ordered chronologically for time-series analysis

---

## Files Delivered

- ✅ `stream_back_raw_levels8.csv` (27.5 MB) - Raw tick-by-tick ladder updates
- ✅ `market_selection_mapping.csv` (26.4 KB) - Selection ID mapping for labeling

Both files are located in: `c:\Users\WatMax\NetBet\`

---

## Use Cases

This raw export is suitable for:

1. **Temporal analysis**: Track price/size changes over time at tick-level resolution
2. **Spectral analysis**: Frequency domain analysis of ladder dynamics
3. **Custom aggregation**: Create custom time buckets or aggregation windows
4. **Event detection**: Identify rapid price movements, gaps, or anomalies
5. **Microstructure research**: Study order book dynamics at the finest granularity

The companion mapping file enables labeling outcomes (home/away/draw) without requiring the mapping to be complete at export time.
