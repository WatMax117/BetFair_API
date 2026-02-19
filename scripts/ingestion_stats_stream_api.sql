-- Ingestion statistics for the new stream API client only.
-- Requires provenance columns (ingest_source, client_version) and client to set them (e.g. ingest_source = 'stream_api').
-- Run after add_stream_ingest_provenance.sql and after sink writes with ingest_source.

\echo '========== STREAM API INGESTION STATS (ingest_source = stream_api) =========='

-- Ladder (ticks)
SELECT
  'ladder_levels' AS dataset,
  count(*) AS total_records_written,
  count(DISTINCT market_id) AS distinct_events_markets,
  min(publish_time) AS min_event_time_publish,
  max(publish_time) AS max_event_time_publish,
  min(received_time) AS min_ingest_time,
  max(received_time) AS max_ingest_time
FROM stream_ingest.ladder_levels
WHERE ingest_source = 'stream_api';

-- If no provenance yet, report all rows (so we see current state)
SELECT
  'ladder_levels (all, no filter)' AS dataset,
  count(*) AS total_records_written,
  count(DISTINCT market_id) AS distinct_markets,
  min(publish_time) AS min_publish_time,
  max(publish_time) AS max_publish_time,
  min(received_time) AS min_received_time,
  max(received_time) AS max_received_time
FROM stream_ingest.ladder_levels;

\echo ''
\echo '========== LIQUIDITY (stream_api only) =========='
SELECT
  'market_liquidity_history' AS dataset,
  count(*) AS total_records_written,
  count(DISTINCT market_id) AS distinct_markets,
  min(publish_time) AS min_publish_time,
  max(publish_time) AS max_publish_time
FROM stream_ingest.market_liquidity_history
WHERE ingest_source = 'stream_api';

SELECT
  'market_liquidity_history (all)' AS dataset,
  count(*) AS total_records,
  count(DISTINCT market_id) AS distinct_markets,
  min(publish_time) AS min_pt,
  max(publish_time) AS max_pt
FROM stream_ingest.market_liquidity_history;
