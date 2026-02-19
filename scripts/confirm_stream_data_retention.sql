-- Confirm with database queries (not assumptions) what is stored for stream/ingest and retention.
-- Run: docker exec -i netbet-postgres psql -U netbet -d netbet -f - < scripts/confirm_stream_data_retention.sql
-- Or on VPS: psql -U netbet -d netbet -f scripts/confirm_stream_data_retention.sql

\echo '========== 1. SCHEMA / TABLE EXISTENCE =========='
SELECT n.nspname AS schema_name, c.relname AS table_name,
       CASE WHEN c.relkind = 'p' THEN 'partitioned' WHEN c.relkind = 'r' THEN 'table' ELSE c.relkind::text END AS kind
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname IN ('stream_ingest', 'public')
  AND c.relname IN ('ladder_levels', 'market_liquidity_history', 'market_book_snapshots', 'traded_volume', 'market_lifecycle_events')
ORDER BY n.nspname, c.relname;

\echo ''
\echo '========== 2. STREAM INGEST: TICK DATA (ladder_levels) =========='
SELECT
  (SELECT count(*) FROM stream_ingest.ladder_levels) AS total_ladder_rows,
  (SELECT count(DISTINCT market_id) FROM stream_ingest.ladder_levels) AS distinct_markets,
  (SELECT min(publish_time) FROM stream_ingest.ladder_levels) AS min_publish_time,
  (SELECT max(publish_time) FROM stream_ingest.ladder_levels) AS max_publish_time,
  (SELECT min(received_time) FROM stream_ingest.ladder_levels) AS min_received_time,
  (SELECT max(received_time) FROM stream_ingest.ladder_levels) AS max_received_time;

\echo ''
\echo '========== 3. STREAM INGEST: LIQUIDITY (market_liquidity_history) =========='
SELECT
  (SELECT count(*) FROM stream_ingest.market_liquidity_history) AS total_liquidity_rows,
  (SELECT count(DISTINCT market_id) FROM stream_ingest.market_liquidity_history) AS distinct_markets,
  (SELECT min(publish_time) FROM stream_ingest.market_liquidity_history) AS min_publish_time,
  (SELECT max(publish_time) FROM stream_ingest.market_liquidity_history) AS max_publish_time;

\echo ''
\echo '========== 4. COMPLETED EVENTS: DO WE HAVE TICKS? =========='
-- Events that have event_open_date in the past (completed) and that appear in metadata
WITH completed_events AS (
  SELECT market_id, event_id, event_name, event_open_date
  FROM public.market_event_metadata
  WHERE event_open_date IS NOT NULL
    AND event_open_date < (now() AT TIME ZONE 'utc')::date - interval '1 day'
  LIMIT 500
),
with_ticks AS (
  SELECT ce.market_id, ce.event_open_date,
         (SELECT count(*) FROM stream_ingest.ladder_levels ll WHERE ll.market_id = ce.market_id) AS tick_count
  FROM completed_events ce
)
SELECT
  count(*) AS completed_events_in_sample,
  count(*) FILTER (WHERE tick_count > 0) AS with_at_least_one_tick,
  count(*) FILTER (WHERE tick_count = 0) AS with_zero_ticks,
  min(event_open_date) AS min_event_open_date,
  max(event_open_date) AS max_event_open_date
FROM with_ticks;

\echo ''
\echo '========== 5. RAW SNAPSHOTS (REST only; stream has NONE) =========='
-- market_book_snapshots = REST listMarketBook captures. Stream API does not write raw_payload.
SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'market_book_snapshots') AS rest_snapshots_table_exists;
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'market_book_snapshots') THEN
    RAISE NOTICE 'REST snapshot count and time range: run SELECT count(*), min(snapshot_at), max(snapshot_at) FROM public.market_book_snapshots;';
  END IF;
END $$;

\echo ''
\echo '========== 6. PARTITIONS (if ladder_levels is partitioned) =========='
SELECT parent.relname AS parent_table, child.relname AS partition_name,
       pg_get_expr(child.relpartbound, child.oid, true) AS range_bound
FROM pg_inherits
JOIN pg_class parent ON parent.oid = pg_inherits.inhparent
JOIN pg_class child ON child.oid = pg_inherits.inhrelid
JOIN pg_namespace n ON n.oid = parent.relnamespace
WHERE parent.relname = 'ladder_levels'
  AND n.nspname IN ('stream_ingest', 'public')
ORDER BY child.relname;

\echo ''
\echo '========== 7. PROVENANCE COLUMNS (ingest_source / client_version) =========='
SELECT table_schema, table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'stream_ingest'
  AND table_name IN ('ladder_levels', 'market_liquidity_history')
  AND column_name IN ('ingest_source', 'client_version', 'received_time', 'publish_time')
ORDER BY table_name, column_name;
