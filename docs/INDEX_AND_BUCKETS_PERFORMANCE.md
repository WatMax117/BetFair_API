# Index Computation & Bucket/Tick Performance Diagnosis

## 1. Index: where is it computed?

### Answer: **Backend (API/DB)**

The index value displayed in the UI is **computed in the backend** and returned as a field in the API response. The frontend only displays it; it does not compute it.

---

### 1.1 Exact UI field name and rendering location

| Property | Value |
|----------|-------|
| **Field name** | `impedance_index_15m` |
| **Display label** | "Impedance Index (15m)" |
| **UI file** | `risk-analytics-ui/web/src/components/EventDetail.tsx` |
| **Line** | 434 |

```tsx
<TableCell align="right" rowSpan={4}>{num(selectedBucketData.impedance_index_15m ?? null)}</TableCell>
```

Related fields (also backend-computed, displayed same table):

- `impedance_abs_diff_home`, `impedance_abs_diff_away`, `impedance_abs_diff_draw` (line 452)

---

### 1.2 Backend trace

**Function:** `compute_impedance_index_from_medians()`  
**File:** `risk-analytics-ui/api/app/stream_data.py` (lines 187–259)

**Inputs (six medians):**

- `home_odds_median`, `home_size_median`
- `away_odds_median`, `away_size_median`
- `draw_odds_median`, `draw_size_median`

**Formula:**

1. `p_i = 1 / O_i` (implied probabilities from median odds)
2. `w_i = p_i / (p_H + p_A + p_D)` (normalized probabilities)
3. `s_i = S_i / S_total` (normalized sizes)
4. `I = sum_i |s_i - w_i|`
5. `I_norm = I / 2` (range 0..1) → `impedance_index_15m`

**Used in:**

- `get_event_buckets_stream` (line 506)
- `get_event_timeseries_stream` (line 459)
- `get_events_by_date_snapshots_stream` (line 394)
- `get_league_events_stream` (line 658)

Each of these returns `impedance_index_15m`, `impedance_abs_diff_home`, etc., in the response.

---

### 1.3 Example API response (sanitized)

```json
{
  "bucket_start": "2026-02-18T14:00:00+00:00",
  "bucket_end": "2026-02-18T14:15:00+00:00",
  "impedance_index_15m": 0.142,
  "impedance_abs_diff_home": 0.08,
  "impedance_abs_diff_away": 0.05,
  "impedance_abs_diff_draw": 0.012,
  "home_back_odds_median": 2.15,
  "home_back_size_median": 450.2,
  "away_back_odds_median": 3.40,
  "away_back_size_median": 320.1,
  "draw_back_odds_median": 3.25,
  "draw_back_size_median": 280.0
}
```

The frontend displays `selectedBucketData.impedance_index_15m` directly; no computation.

---

## 2. Buckets/ticks performance diagnosis

### 2.1 Endpoints and data flow

| Endpoint | Purpose | UI usage |
|----------|---------|----------|
| `GET /stream/events/{market_id}/buckets` | All 15‑min buckets for market (no window) | EventDetail chart + bucket list |
| `GET /stream/events/{market_id}/timeseries` | Buckets in `from_ts`–`to_ts` | Alternative timeseries |
| `GET /stream/events/{market_id}/markets/{market_id}/ticks` | Raw ticks in bucket | Tick audit view |

EventDetail loads **all buckets** via `/buckets` (no `from_ts`/`to_ts`).

---

### 2.2 Backend bottleneck (N+1 queries)

**`get_event_buckets_stream()`** (`stream_data.py` lines 701–903):

- No date/window: from `MIN(publish_time)` to `MAX(publish_time)` for the market.
- For each bucket it runs:
  - `_latest_publish_before` → 1 query
  - `_tick_count_in_bucket` → 1 query
  - `_compute_bucket_median_back_odds_and_size` (H/A/D) → 3 × 2 = 6 queries (baseline + updates)
  - `_runners_from_ladder` → 2 queries

Approx. **10 queries per bucket**. For 96 buckets (24h) that’s ~960 queries per market.

---

### 2.3 Main queries used

**Metadata:**
```sql
SELECT home_selection_id, away_selection_id, draw_selection_id
FROM market_event_metadata WHERE market_id = %s;
```

**Range:**
```sql
SELECT MIN(publish_time), MAX(publish_time)
FROM stream_ingest.ladder_levels WHERE market_id = %s;
```

**Per bucket (typical pattern):**
```sql
-- Baseline for median
SELECT price, size, publish_time FROM stream_ingest.ladder_levels
WHERE market_id = %s AND selection_id = %s AND side = 'B' AND level = 0
  AND publish_time <= %s
ORDER BY publish_time DESC LIMIT 1;

-- Updates in bucket
SELECT price, size, publish_time FROM stream_ingest.ladder_levels
WHERE market_id = %s AND selection_id = %s AND side = 'B' AND level = 0
  AND publish_time > %s AND publish_time <= %s
ORDER BY publish_time ASC;
```

**Index used:** `idx_stream_ladder_market_publish ON stream_ingest.ladder_levels (market_id, publish_time DESC)`  
For these queries a composite index `(market_id, selection_id, side, level, publish_time)` would better support the median computation.

---

### 2.4 Timing instrumentation (backend)

**Implemented** in `stream_router.py`:

- **Buckets endpoint** (`GET /stream/events/{market_id}/buckets`): logs `market_id`, `rows`, `total_ms`, `payload_bytes`
- **Ticks endpoint** (`GET /stream/markets/{market_id}/ticks`): logs `market_id`, `rows`, `total_ms`, `payload_bytes`

Log format:
```
buckets_endpoint market_id=1.253378204 rows=96 total_ms=1250.3 payload_bytes=45000
ticks_endpoint market_id=1.253378204 rows=342 total_ms=45.2 payload_bytes=12000
```

Interpretation: `total_ms` includes DB query time, Python aggregation, and JSON serialization. If `rows` is high and `total_ms` is large, the bottleneck is likely the N+1 per-bucket queries.

---

### 2.5 DB diagnostics

**Run EXPLAIN ANALYZE on typical queries (example for one market):**

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT price, size, publish_time
FROM stream_ingest.ladder_levels
WHERE market_id = '1.253378204'
  AND selection_id = 47972
  AND side = 'B'
  AND level = 0
  AND publish_time > '2026-02-18T14:00:00+00:00'
  AND publish_time <= '2026-02-18T14:15:00+00:00'
ORDER BY publish_time ASC;
```

**Check indexes on `stream_ingest.ladder_levels`:**

```sql
SELECT indexname, indexdef FROM pg_indexes
WHERE tablename = 'ladder_levels' AND schemaname = 'stream_ingest';
```

**Current index (from add_replay_snapshot_index.sql):**
```sql
idx_stream_ladder_market_publish ON stream_ingest.ladder_levels (market_id, publish_time DESC)
```

**Suggested composite index** (faster median queries per selection):
```sql
CREATE INDEX IF NOT EXISTS idx_ladder_market_selection_side_level_publish
  ON stream_ingest.ladder_levels (market_id, selection_id, side, level, publish_time);
```

---

### 2.6 API response strategy (avoid over-fetch)

| Current | Issue |
|---------|-------|
| `/buckets` | No window; returns all buckets (often 24h+ = 96+ buckets) |
| `/timeseries` | Optional `from_ts`/`to_ts`; default 24h |

**Recommendations:**

1. Add optional `from_ts` / `to_ts` (or `window_minutes`) to `/buckets`, default last 180 minutes.
2. Server-side limit: cap to 96 buckets (24h) or add a `limit` parameter.
3. Gzip compression: already enabled via `GZipMiddleware` in `main.py` (min 500 bytes).

---

### 2.7 Frontend rendering diagnostics

**Measure in DevTools → Network:**

- Time to first byte (TTFB)
- Download time
- Response size

**Measure in DevTools → Performance:**

- `JSON.parse` time (if large payload)
- Chart/table render time
- Whether frequent re-renders occur on minor state changes

**EventDetail behavior:** `bucketListVisible` caps visible buttons to 50; the full `buckets` array is still loaded and used for `chartData`. With many buckets, chart libraries (e.g. Recharts) may slow down.

---

## 3. Fix plan and expected impact

| Fix | Effort | Expected impact |
|-----|--------|------------------|
| Add `from_ts`/`to_ts` to `/buckets` (default last 180 min) | Low | Large: fewer buckets → fewer queries |
| Batch/rewrite queries to avoid N+1 per bucket | High | Very large: 1–2 queries instead of ~10 per bucket |
| Add composite index `(market_id, selection_id, side, level, publish_time)` | Low | Medium: faster median queries |
| **Bulk buckets (implemented)** | Done | 3 queries total; default 180 min; total_volume via Query 3; see BULK_BUCKETS_EXPLAIN_ANALYZE.md |
| Enable gzip on API | Low | Medium: smaller payload |
| Frontend: limit chart points (e.g. last 48 buckets) | Low | Low–medium: smoother chart |

---

## 4. Quick acceptance criteria

1. **Index:** Impedance index (`impedance_index_15m`) is computed in the backend (`stream_data.compute_impedance_index_from_medians`); frontend only displays it.
2. **Latency:** Backend logs total time, DB time, bucket count, payload size, and aggregation time for the buckets endpoint.
3. **Plan:** Add windowing to `/buckets`, optimize queries (or add batching), add DB index, enable gzip, and optionally limit chart points on the frontend.
