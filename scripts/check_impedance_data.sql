-- Check impedance data availability
-- Run: docker exec -i netbet-postgres psql -U netbet -d netbet < scripts/check_impedance_data.sql

\echo '=== Impedance Data Status ==='
\echo ''

\echo '--- Impedance Column Statistics ---'
SELECT 
    COUNT(*) as total_rows,
    COUNT(home_impedance) as rows_with_home_impedance,
    COUNT(away_impedance) as rows_with_away_impedance,
    COUNT(draw_impedance) as rows_with_draw_impedance,
    COUNT(home_impedance_norm) as rows_with_home_impedance_norm,
    COUNT(away_impedance_norm) as rows_with_away_impedance_norm,
    COUNT(draw_impedance_norm) as rows_with_draw_impedance_norm,
    ROUND(100.0 * COUNT(home_impedance) / NULLIF(COUNT(*), 0), 2) as pct_with_impedance,
    MAX(snapshot_at) as latest_snapshot_with_impedance
FROM rest_ingest.market_derived_metrics;

\echo ''
\echo '--- Sample Impedance Values (Latest 5) ---'
SELECT 
    snapshot_id,
    snapshot_at,
    market_id,
    home_impedance,
    away_impedance,
    draw_impedance,
    home_impedance_norm,
    away_impedance_norm,
    draw_impedance_norm,
    home_back_stake,
    home_back_odds,
    home_lay_stake,
    home_lay_odds
FROM rest_ingest.market_derived_metrics
WHERE home_impedance IS NOT NULL
   OR away_impedance IS NOT NULL
   OR draw_impedance IS NOT NULL
ORDER BY snapshot_at DESC
LIMIT 5;

\echo ''
\echo '--- Markets with Impedance Data ---'
SELECT 
    market_id,
    COUNT(*) as total_snapshots,
    COUNT(CASE WHEN home_impedance IS NOT NULL THEN 1 END) as snapshots_with_impedance,
    MAX(snapshot_at) as latest_snapshot,
    ROUND(100.0 * COUNT(CASE WHEN home_impedance IS NOT NULL THEN 1 END) / NULLIF(COUNT(*), 0), 2) as pct_with_impedance
FROM rest_ingest.market_derived_metrics
GROUP BY market_id
HAVING COUNT(CASE WHEN home_impedance IS NOT NULL THEN 1 END) > 0
ORDER BY latest_snapshot DESC
LIMIT 10;

\echo ''
\echo '--- Recent Snapshots WITHOUT Impedance (last 10) ---'
SELECT 
    snapshot_id,
    snapshot_at,
    market_id,
    home_impedance IS NULL as missing_home_impedance,
    away_impedance IS NULL as missing_away_impedance,
    draw_impedance IS NULL as missing_draw_impedance
FROM rest_ingest.market_derived_metrics
WHERE home_impedance IS NULL
   AND away_impedance IS NULL
   AND draw_impedance IS NULL
ORDER BY snapshot_at DESC
LIMIT 10;
