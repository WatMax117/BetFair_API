# Bulk Buckets: EXPLAIN ANALYZE and Index

## Side and level scope (assumptions)

**Impedance index and Book Risk are designed to use only top-of-book back prices:**

- `side = 'B'` (back only)
- `level = 0` (best price only)
- No lay prices or multiple levels required for these metrics

This is documented in `stream_data.get_event_buckets_stream_bulk()` and in this file.
If lay prices or multiple levels are ever needed, the bulk query must be extended while
keeping ≤ 3 DB queries total and no per-bucket queries.

---

## total_volume handling

**Option A (implemented):** One additional aggregated query for `total_volume`.

- Query 3: `stream_ingest.market_liquidity_history` for the market in the time range
- No per-bucket liquidity queries; assign per bucket in Python from the bulk result

---

## Bulk queries (3 DB queries total)

### Query 1: metadata
```sql
SELECT m.market_id, m.event_id, m.event_name, m.event_open_date, m.competition_name,
       m.home_selection_id, m.away_selection_id, m.draw_selection_id
FROM market_event_metadata m
WHERE m.market_id = %s;
```

### Query 2: ladder rows (bulk fetch, level 0 side B only)
```sql
SELECT publish_time, selection_id, price, size
FROM stream_ingest.ladder_levels
WHERE market_id = %s
  AND selection_id = ANY(%s)
  AND side = 'B'
  AND level = 0
  AND publish_time >= %s
  AND publish_time <= %s
ORDER BY publish_time ASC;
```

### Query 3: liquidity (total_volume)
```sql
SELECT publish_time, total_matched
FROM stream_ingest.market_liquidity_history
WHERE market_id = %s
  AND publish_time >= %s
  AND publish_time <= %s
ORDER BY publish_time ASC;
```

Replace params:
- `%s` (market_id): e.g. `'1.253378204'`
- `%s` (selection_ids): e.g. `ARRAY[47972, 47973, 47974]`
- `%s` (from): e.g. `'2026-02-18T12:00:00+00:00'`
- `%s` (to): e.g. `'2026-02-18T18:00:00+00:00'`

---

## Indexes

Run `risk-analytics-ui/scripts/add_bulk_buckets_index.sql`:

```sql
CREATE INDEX IF NOT EXISTS idx_ladder_bulk_buckets
  ON stream_ingest.ladder_levels (market_id, selection_id, side, level, publish_time);
```

`market_liquidity_history` PK is `(market_id, publish_time)`; no extra index needed for Query 3.

---

## EXPLAIN (ANALYZE, BUFFERS)

### Ladder (Query 2)

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT publish_time, selection_id, price, size
FROM stream_ingest.ladder_levels
WHERE market_id = '1.253378204'
  AND selection_id = ANY(ARRAY[47972, 47973, 47974])
  AND side = 'B'
  AND level = 0
  AND publish_time >= '2026-02-18T12:00:00+00:00'
  AND publish_time <= '2026-02-18T18:00:00+00:00'
ORDER BY publish_time ASC;
```

Expected: Index Scan on `idx_ladder_bulk_buckets`. No Seq Scan.

### Liquidity (Query 3)

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT publish_time, total_matched
FROM stream_ingest.market_liquidity_history
WHERE market_id = '1.253378204'
  AND publish_time >= '2026-02-18T12:00:00+00:00'
  AND publish_time <= '2026-02-18T18:00:00+00:00'
ORDER BY publish_time ASC;
```

Expected: Index Scan on PK `(market_id, publish_time)` or `idx_stream_liquidity_market_id`. No Seq Scan.

---

## Performance validation

### 1. Default 180-minute window

```bash
# Start API; call buckets endpoint (no params = default 180 min)
curl -s "http://localhost:8000/stream/events/1.253378204/buckets" | jq 'length'

# Check API logs for:
# buckets_endpoint market_id=1.253378204 bucket_count=N db_query_count=3 total_ms=X payload_bytes=Y
```

### 2. 24-hour window

```bash
# from_ts = now - 24h, to_ts = now (adjust timestamps)
curl -s "http://localhost:8000/stream/events/1.253378204/buckets?from_ts=2026-02-17T12:00:00Z&to_ts=2026-02-18T12:00:00Z" | jq 'length'

# Check API logs for bucket_count, db_query_count, total_ms, payload_bytes
```

### Acceptance criteria

- ≤ 3 DB queries total ✓
- No per-bucket SQL ✓
- Latency stable with bucket count (linear only in row count, not in bucket count)
- Log: `market_id`, `bucket_count`, `db_query_count`, `total_ms`, `payload_bytes`
