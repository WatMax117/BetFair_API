-- Settlement records date range (stream_ingest.market_settlement).
-- Run on VPS: docker exec -i netbet-postgres psql -U netbet -d netbet -v ON_ERROR_STOP=1 -f - < scripts/settlement_date_range.sql
-- Or from inside container: psql -U netbet -d netbet -f /path/to/settlement_date_range.sql

\echo '========== stream_ingest.market_settlement: date range =========='
SELECT
  COUNT(*) AS total_markets,
  MIN(settled_at) AS earliest_settled_at,
  MAX(settled_at) AS latest_settled_at,
  MIN(created_at) AS earliest_created_at,
  MAX(created_at) AS latest_created_at
FROM stream_ingest.market_settlement;

\echo ''
\echo '========== by source (stream vs rest) =========='
SELECT source, COUNT(*) AS markets, MIN(settled_at) AS earliest_settled_at, MAX(settled_at) AS latest_settled_at
FROM stream_ingest.market_settlement
GROUP BY source
ORDER BY source;

\echo ''
\echo '========== stream_ingest.market_runner_settlement: row count =========='
SELECT COUNT(*) AS total_runner_rows FROM stream_ingest.market_runner_settlement;
