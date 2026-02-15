-- Check snapshot ingestion status
-- Run: docker exec -i netbet-postgres psql -U netbet -d netbet < scripts/check_snapshot_ingestion.sql

\echo '=== Snapshot Ingestion Status ==='
\echo ''

\echo '--- Latest Snapshot Timestamp ---'
SELECT 
    MAX(snapshot_at) as latest_snapshot_at,
    COUNT(*) as total_snapshots,
    COUNT(DISTINCT market_id) as distinct_markets,
    NOW() as current_time,
    EXTRACT(EPOCH FROM (NOW() - MAX(snapshot_at))) as seconds_since_latest,
    CASE 
        WHEN EXTRACT(EPOCH FROM (NOW() - MAX(snapshot_at))) > 1800 THEN 'STALE (>30 min)'
        WHEN EXTRACT(EPOCH FROM (NOW() - MAX(snapshot_at))) > 900 THEN 'WARNING (>15 min)'
        ELSE 'OK'
    END as status
FROM rest_ingest.market_book_snapshots;

\echo ''
\echo '--- Recent Snapshots (last 10) ---'
SELECT 
    snapshot_id,
    snapshot_at,
    market_id,
    total_matched,
    inplay,
    status,
    EXTRACT(EPOCH FROM (NOW() - snapshot_at)) as age_seconds
FROM rest_ingest.market_book_snapshots
ORDER BY snapshot_at DESC
LIMIT 10;

\echo ''
\echo '--- Snapshot Rate (last hour) ---'
SELECT 
    DATE_TRUNC('minute', snapshot_at) as minute_bucket,
    COUNT(*) as snapshot_count
FROM rest_ingest.market_book_snapshots
WHERE snapshot_at >= NOW() - INTERVAL '1 hour'
GROUP BY minute_bucket
ORDER BY minute_bucket DESC
LIMIT 10;

\echo ''
\echo '--- Markets with Recent Snapshots ---'
SELECT 
    market_id,
    COUNT(*) as snapshot_count,
    MAX(snapshot_at) as latest_snapshot,
    EXTRACT(EPOCH FROM (NOW() - MAX(snapshot_at))) as seconds_since_latest
FROM rest_ingest.market_book_snapshots
GROUP BY market_id
ORDER BY latest_snapshot DESC
LIMIT 10;
