-- Liquidity Deep Dive Audit - Step 1: Database Pulse Check
-- Run: docker exec -i netbet-postgres psql -U netbet -d netbet -f - < liquidity_pulse_check.sql
-- Or:  psql -U netbet -d netbet -f liquidity_pulse_check.sql

\echo '=== Query A: market_liquidity_history population ==='
SELECT count(*) AS rows,
       min(publish_time) AS min_publish_time,
       max(publish_time) AS max_publish_time
FROM market_liquidity_history;

\echo ''
\echo '=== Query B: markets with volume (total_matched) ==='
SELECT count(*) FILTER (WHERE coalesce(total_matched, 0) > 0) AS markets_with_volume,
       max(total_matched) AS max_total_matched
FROM markets;
