-- Snapshot Inventory Audit for Backfill Eligibility
-- Run: docker exec -i netbet-postgres psql -U netbet -d netbet < risk-analytics-ui/sql/audit_snapshot_inventory.sql

\echo '========================================'
\echo 'SNAPSHOT INVENTORY AUDIT REPORT'
\echo '========================================'
\echo ''

\echo 'A) SNAPSHOT INVENTORY'
\echo '----------------------------------------'
SELECT 
    COUNT(*) AS total_snapshots,
    MIN(snapshot_at) AS oldest_snapshot,
    MAX(snapshot_at) AS latest_snapshot
FROM market_derived_metrics;
\echo ''

\echo 'B) RAW PAYLOAD AVAILABILITY'
\echo '----------------------------------------'
-- Check if raw_payload column exists
SELECT 
    CASE WHEN EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'market_book_snapshots' AND column_name = 'raw_payload'
    ) THEN 'YES' ELSE 'NO' END AS has_raw_payload_column;

-- Count snapshots with raw_payload
SELECT COUNT(*) AS snapshots_with_raw_payload
FROM market_book_snapshots
WHERE raw_payload IS NOT NULL;
\echo ''

\echo 'C) NULL PERCENTAGES'
\echo '----------------------------------------'
WITH stats AS (
    SELECT 
        COUNT(*) AS total_rows,
        -- Impedance inputs
        SUM(CASE WHEN home_back_stake IS NULL THEN 1 ELSE 0 END) AS home_back_stake_nulls,
        SUM(CASE WHEN away_back_stake IS NULL THEN 1 ELSE 0 END) AS away_back_stake_nulls,
        SUM(CASE WHEN draw_back_stake IS NULL THEN 1 ELSE 0 END) AS draw_back_stake_nulls,
        SUM(CASE WHEN home_lay_stake IS NULL THEN 1 ELSE 0 END) AS home_lay_stake_nulls,
        SUM(CASE WHEN away_lay_stake IS NULL THEN 1 ELSE 0 END) AS away_lay_stake_nulls,
        SUM(CASE WHEN draw_lay_stake IS NULL THEN 1 ELSE 0 END) AS draw_lay_stake_nulls,
        SUM(CASE WHEN home_back_odds IS NULL THEN 1 ELSE 0 END) AS home_back_odds_nulls,
        SUM(CASE WHEN away_back_odds IS NULL THEN 1 ELSE 0 END) AS away_back_odds_nulls,
        SUM(CASE WHEN draw_back_odds IS NULL THEN 1 ELSE 0 END) AS draw_back_odds_nulls,
        SUM(CASE WHEN home_lay_odds IS NULL THEN 1 ELSE 0 END) AS home_lay_odds_nulls,
        SUM(CASE WHEN away_lay_odds IS NULL THEN 1 ELSE 0 END) AS away_lay_odds_nulls,
        SUM(CASE WHEN draw_lay_odds IS NULL THEN 1 ELSE 0 END) AS draw_lay_odds_nulls,
        -- L1 sizes
        SUM(CASE WHEN home_best_back_size_l1 IS NULL THEN 1 ELSE 0 END) AS home_best_back_size_l1_nulls,
        SUM(CASE WHEN away_best_back_size_l1 IS NULL THEN 1 ELSE 0 END) AS away_best_back_size_l1_nulls,
        SUM(CASE WHEN draw_best_back_size_l1 IS NULL THEN 1 ELSE 0 END) AS draw_best_back_size_l1_nulls,
        SUM(CASE WHEN home_best_lay_size_l1 IS NULL THEN 1 ELSE 0 END) AS home_best_lay_size_l1_nulls,
        SUM(CASE WHEN away_best_lay_size_l1 IS NULL THEN 1 ELSE 0 END) AS away_best_lay_size_l1_nulls,
        SUM(CASE WHEN draw_best_lay_size_l1 IS NULL THEN 1 ELSE 0 END) AS draw_best_lay_size_l1_nulls,
        -- Impedance
        SUM(CASE WHEN home_impedance IS NULL THEN 1 ELSE 0 END) AS home_impedance_nulls,
        SUM(CASE WHEN away_impedance IS NULL THEN 1 ELSE 0 END) AS away_impedance_nulls,
        SUM(CASE WHEN draw_impedance IS NULL THEN 1 ELSE 0 END) AS draw_impedance_nulls,
        -- Risk (imbalance)
        SUM(CASE WHEN home_risk IS NULL THEN 1 ELSE 0 END) AS home_risk_nulls,
        SUM(CASE WHEN away_risk IS NULL THEN 1 ELSE 0 END) AS away_risk_nulls,
        SUM(CASE WHEN draw_risk IS NULL THEN 1 ELSE 0 END) AS draw_risk_nulls
    FROM market_derived_metrics
)
SELECT 
    total_rows,
    ROUND(100.0 * home_back_stake_nulls / NULLIF(total_rows, 0), 1) AS home_back_stake_pct_null,
    ROUND(100.0 * away_back_stake_nulls / NULLIF(total_rows, 0), 1) AS away_back_stake_pct_null,
    ROUND(100.0 * draw_back_stake_nulls / NULLIF(total_rows, 0), 1) AS draw_back_stake_pct_null,
    ROUND(100.0 * home_lay_stake_nulls / NULLIF(total_rows, 0), 1) AS home_lay_stake_pct_null,
    ROUND(100.0 * away_lay_stake_nulls / NULLIF(total_rows, 0), 1) AS away_lay_stake_pct_null,
    ROUND(100.0 * draw_lay_stake_nulls / NULLIF(total_rows, 0), 1) AS draw_lay_stake_pct_null,
    ROUND(100.0 * home_best_back_size_l1_nulls / NULLIF(total_rows, 0), 1) AS home_best_back_size_l1_pct_null,
    ROUND(100.0 * away_best_back_size_l1_nulls / NULLIF(total_rows, 0), 1) AS away_best_back_size_l1_pct_null,
    ROUND(100.0 * draw_best_back_size_l1_nulls / NULLIF(total_rows, 0), 1) AS draw_best_back_size_l1_pct_null,
    ROUND(100.0 * home_best_lay_size_l1_nulls / NULLIF(total_rows, 0), 1) AS home_best_lay_size_l1_pct_null,
    ROUND(100.0 * away_best_lay_size_l1_nulls / NULLIF(total_rows, 0), 1) AS away_best_lay_size_l1_pct_null,
    ROUND(100.0 * draw_best_lay_size_l1_nulls / NULLIF(total_rows, 0), 1) AS draw_best_lay_size_l1_pct_null,
    ROUND(100.0 * home_impedance_nulls / NULLIF(total_rows, 0), 1) AS home_impedance_pct_null,
    ROUND(100.0 * away_impedance_nulls / NULLIF(total_rows, 0), 1) AS away_impedance_pct_null,
    ROUND(100.0 * draw_impedance_nulls / NULLIF(total_rows, 0), 1) AS draw_impedance_pct_null,
    ROUND(100.0 * home_risk_nulls / NULLIF(total_rows, 0), 1) AS home_risk_pct_null,
    ROUND(100.0 * away_risk_nulls / NULLIF(total_rows, 0), 1) AS away_risk_pct_null,
    ROUND(100.0 * draw_risk_nulls / NULLIF(total_rows, 0), 1) AS draw_risk_pct_null
FROM stats;
\echo ''

\echo 'D) SAMPLE RAW PAYLOAD CHECK'
\echo '----------------------------------------'
\echo 'Checking if raw_payload contains runners with availableToBack/availableToLay...'
\echo ''
SELECT 
    snapshot_id,
    market_id,
    snapshot_at,
    CASE 
        WHEN raw_payload ? 'runners' THEN 'YES'
        ELSE 'NO'
    END AS has_runners,
    CASE 
        WHEN raw_payload -> 'runners' -> 0 -> 'ex' ? 'availableToBack' THEN 'YES'
        WHEN raw_payload -> 'runners' -> 0 -> 'ex' ? 'available_to_back' THEN 'YES'
        ELSE 'NO'
    END AS has_availableToBack
FROM market_book_snapshots
WHERE raw_payload IS NOT NULL
LIMIT 5;
\echo ''

\echo '========================================'
\echo 'AUDIT COMPLETE'
\echo '========================================'
\echo ''
\echo 'Next steps:'
\echo '1. Review NULL percentages'
\echo '2. Confirm raw_payload contains full order book arrays'
\echo '3. Determine eligibility tier (A/B/C)'
\echo '4. Implement backfill script if Tier A or B eligible'
\echo ''
