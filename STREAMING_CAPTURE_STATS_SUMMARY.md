# Streaming Capture Statistics Report

**Date**: 2026-02-16  
**Database**: `netbet` (PostgreSQL)  
**Source**: `stream_ingest.ladder_levels` (partitioned table)  
**Filters**: `MATCH_ODDS_FT` markets, `BACK` side, levels 1-8

---

## 1. Overall Coverage (Single Row Summary)

**File**: `streaming_capture_stats_overall.csv`

| Metric | Value |
|--------|-------|
| **Total ticks** | 248,484 |
| **Distinct events** | 56 |
| **Distinct markets** | 56 |
| **Distinct selections** | 112 |
| **Min publish_time** | 2026-02-05 12:07:54.024+00 |
| **Max publish_time** | 2026-02-06 23:57:22.957+00 |
| **Min received_time** | 2026-02-05 12:07:54.139+00 |
| **Max received_time** | 2026-02-06 23:57:22.969+00 |

### Key Answers

1. **How many distinct MATCH events?** → **56 events**
2. **How many distinct markets?** → **56 markets** (1 market per event)
3. **How many distinct selections?** → **112 selections** (~2 selections per market on average)
4. **Time coverage**: 
   - **Start**: 2026-02-05 12:07:54 UTC
   - **End**: 2026-02-06 23:57:22 UTC
   - **Span**: ~1 day 11 hours 49 minutes

---

## 2. Daily Breakdown

**File**: `streaming_capture_stats_daily.csv`

| Date | Ticks | Events | Markets | Selections |
|------|-------|--------|---------|------------|
| **2026-02-05** | 95,502 | 56 | 56 | 112 |
| **2026-02-06** | 152,982 | 25 | 25 | 51 |
| **Total** | 248,484 | - | - | - |

### Observations

- **Feb 5**: Higher event count (56 events), lower tick volume (95,502 ticks)
- **Feb 6**: Fewer events (25 events), higher tick volume (152,982 ticks)
- **Tick distribution**: ~38% on Feb 5, ~62% on Feb 6
- **Event overlap**: Some events span both days (25 events active on Feb 6)

---

## 3. Per-Event Coverage

**File**: `streaming_capture_stats_by_event.csv`

**Total events**: 56 events

### Sample Events (first 10)

| Event ID | Markets | Market Start | First Tick | Last Tick | Capture Span |
|----------|---------|--------------|------------|-----------|--------------|
| 35226507 | 1 | 2026-02-05 11:00:00+00 | 2026-02-05 12:07:54 | 2026-02-05 12:53:15 | 00:45:21 |
| 35175874 | 1 | 2026-02-05 20:00:00+00 | 2026-02-05 12:10:54 | 2026-02-05 21:48:21 | 09:37:27 |
| 35187302 | 1 | 2026-02-06 20:00:00+00 | 2026-02-05 12:10:54 | 2026-02-06 21:54:22 | 1 day 09:43:28 |
| 35187306 | 1 | 2026-02-08 16:30:00+00 | 2026-02-05 12:10:54 | 2026-02-06 23:57:22 | 1 day 11:46:28 |

### Capture Span Analysis

- **Shortest capture**: ~45 minutes (event 35226507)
- **Longest capture**: ~1 day 11 hours 46 minutes (event 35187306)
- **Typical pattern**: Events starting later in the week (Feb 6-8) have longer capture spans because streaming started on Feb 5

---

## Summary Statistics

### Coverage Metrics

- **Events captured**: 56 distinct MATCH events
- **Markets per event**: 1:1 ratio (56 markets for 56 events)
- **Selections per market**: ~2 selections on average (112 total / 56 markets)
- **Total ladder updates**: 248,484 ticks

### Time Coverage

- **Capture window**: Feb 5, 2026 12:07 UTC → Feb 6, 2026 23:57 UTC
- **Total span**: ~1 day 11 hours 49 minutes
- **Daily distribution**: 
  - Feb 5: 95,502 ticks (38%)
  - Feb 6: 152,982 ticks (62%)

### Data Quality Notes

- All events have exactly 1 market (MATCH_ODDS_FT)
- Selection count (112) suggests some markets may have 2 selections (e.g., binary markets) rather than the typical 3 (home/away/draw)
- Capture spans vary significantly based on when streaming started relative to match start times

---

## Files Delivered

1. ✅ `streaming_capture_stats_overall.csv` (260 bytes) - Overall summary (1 row)
2. ✅ `streaming_capture_stats_daily.csv` (99 bytes) - Daily breakdown (2 rows)
3. ✅ `streaming_capture_stats_by_event.csv` (5.9 KB) - Per-event coverage (56 rows)

All files are located in: `c:\Users\WatMax\NetBet\`

---

## SQL Queries Used

- `export_stats_overall.sql` - Overall statistics query
- `export_stats_daily.sql` - Daily breakdown query
- `export_stats_by_event.sql` - Per-event coverage query
