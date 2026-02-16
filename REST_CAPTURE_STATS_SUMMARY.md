# REST API Capture Statistics Report

**Date**: 2026-02-16  
**Database**: `netbet` (PostgreSQL)  
**Source**: `public.market_book_snapshots` (REST API ingestion)  
**Filters**: `MATCH_ODDS_FT` markets, `source = 'rest_listMarketBook'`

---

## 1. Overall Coverage (Single Row Summary)

**File**: `rest_capture_stats_overall.csv`

| Metric | Value |
|--------|-------|
| **Total snapshots** | 7,103 |
| **Distinct events** | 102 |
| **Distinct markets** | 102 |
| **Min snapshot_time** | 2026-02-06 20:45:29.194471+00 |
| **Max snapshot_time** | 2026-02-16 10:49:36.744748+00 |

### Key Answers

1. **How many distinct MATCH events?** → **102 events**
2. **How many distinct markets?** → **102 markets** (1 market per event)
3. **Time coverage**: 
   - **Start**: 2026-02-06 20:45:29 UTC
   - **End**: 2026-02-16 10:49:36 UTC
   - **Span**: ~9 days 14 hours 4 minutes

---

## 2. Daily Breakdown

**File**: `rest_capture_stats_daily.csv`

| Date | Snapshots | Events | Markets |
|------|-----------|--------|---------|
| **2026-02-06** | 15 | 1 | 1 |
| **2026-02-07** | 572 | 31 | 31 |
| **2026-02-08** | 541 | 25 | 25 |
| **2026-02-09** | 537 | 12 | 12 |
| **2026-02-10** | 200 | 4 | 4 |
| **2026-02-12** | 1,090 | 30 | 30 |
| **2026-02-13** | 1,717 | 21 | 21 |
| **2026-02-14** | 1,828 | 14 | 14 |
| **2026-02-15** | 515 | 5 | 5 |
| **2026-02-16** | 88 | 1 | 1 |
| **Total** | 7,103 | - | - |

### Observations

- **Peak day**: Feb 14 with 1,828 snapshots (26% of total)
- **Highest event count**: Feb 7 with 31 events
- **Gap**: No data on Feb 11 (likely no matches scheduled)
- **Recent activity**: Feb 16 has only 88 snapshots (partial day, query run at 10:49 UTC)

---

## 3. Per-Event Coverage

**File**: `rest_capture_stats_by_event.csv`

**Total events**: 102 events

### Sample Events (first 10)

| Event ID | Markets | Market Start | First Snapshot | Last Snapshot | Total Snapshots | Capture Span |
|----------|---------|--------------|----------------|---------------|-----------------|--------------|
| 35187302 | 1 | 2026-02-06 20:00:00+00 | 2026-02-06 20:45:29 | 2026-02-06 20:59:33 | 15 | 00:14:04 |
| 35189865 | 1 | 2026-02-07 04:00:00+00 | 2026-02-07 04:06:49 | 2026-02-07 04:59:07 | 53 | 00:52:17 |
| 35189836 | 1 | 2026-02-07 06:00:00+00 | 2026-02-07 05:00:07 | 2026-02-07 06:59:47 | 120 | 01:59:39 |
| 35189126 | 1 | 2026-02-07 15:15:00+00 | 2026-02-07 11:00:05 | 2026-02-07 16:00:14 | 21 | 05:00:09 |

### Capture Span Analysis

- **Shortest capture**: ~14 minutes (event 35187302)
- **Typical capture**: 1-7 hours per event
- **Snapshot frequency**: Varies by event (15-120+ snapshots per event)

---

## Comparison: REST API vs Streaming

| Metric | REST API | Streaming |
|--------|----------|-----------|
| **Total records** | 7,103 snapshots | 248,484 ticks |
| **Distinct events** | 102 | 56 |
| **Distinct markets** | 102 | 56 |
| **Time coverage start** | 2026-02-06 20:45 UTC | 2026-02-05 12:07 UTC |
| **Time coverage end** | 2026-02-16 10:49 UTC | 2026-02-06 23:57 UTC |
| **Coverage span** | ~9 days 14 hours | ~1 day 11 hours |
| **Data granularity** | Snapshots (periodic polls) | Ticks (real-time updates) |

### Key Differences

1. **Coverage**: REST API covers more events (102 vs 56) and longer time period (9+ days vs 1+ day)
2. **Volume**: Streaming has much higher volume (248k ticks vs 7k snapshots) due to real-time updates
3. **Time overlap**: Streaming started earlier (Feb 5) but ended earlier (Feb 6); REST started later (Feb 6) but continues to present (Feb 16)
4. **Data structure**: 
   - REST: Periodic snapshots with full market book JSON
   - Streaming: Continuous tick-by-tick ladder updates

---

## Summary Statistics

### REST API Coverage Metrics

- **Events captured**: 102 distinct MATCH events
- **Markets per event**: 1:1 ratio (102 markets for 102 events)
- **Total snapshots**: 7,103 snapshots
- **Average snapshots per event**: ~70 snapshots

### Time Coverage

- **Capture window**: Feb 6, 2026 20:45 UTC → Feb 16, 2026 10:49 UTC
- **Total span**: ~9 days 14 hours 4 minutes
- **Active days**: 10 days (Feb 6-10, 12-16; gap on Feb 11)

### Data Quality Notes

- All events have exactly 1 market (MATCH_ODDS_FT)
- Snapshot frequency varies by event (15-120+ snapshots)
- Capture spans typically cover match duration plus pre/post periods
- REST API provides broader event coverage but lower temporal resolution compared to streaming

---

## Files Delivered

1. ✅ `rest_capture_stats_overall.csv` - Overall summary (1 row)
2. ✅ `rest_capture_stats_daily.csv` - Daily breakdown (10 rows)
3. ✅ `rest_capture_stats_by_event.csv` - Per-event coverage (102 rows)

All files are located in: `c:\Users\WatMax\NetBet\`

---

## SQL Queries Used

- `export_rest_stats_overall.sql` - Overall statistics query
- `export_rest_stats_daily.sql` - Daily breakdown query
- `export_rest_stats_by_event.sql` - Per-event coverage query
