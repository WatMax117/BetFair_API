\echo '=== Tables by schema ==='
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_name IN ('market_book_snapshots','market_derived_metrics','ladder_levels','market_liquidity_history')
ORDER BY table_schema, table_name;

\echo ''
\echo '=== market_derived_metrics new columns (VWAP + L1) ==='
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'market_derived_metrics'
  AND (column_name LIKE '%back_stake%' OR column_name LIKE '%lay_stake%'
       OR column_name LIKE '%best_back_size_l1%' OR column_name LIKE '%best_lay_size_l1%'
       OR column_name LIKE '%impedance%' OR column_name LIKE '%_risk%')
ORDER BY column_name;

\echo ''
\echo '=== Post-deploy newest snapshots (last 100 by snapshot_at) - NULL counts ==='
WITH last_100 AS (
  SELECT snapshot_id, snapshot_at, market_id,
         home_best_back_size_l1, away_best_back_size_l1, draw_best_back_size_l1,
         home_back_stake, away_back_stake, draw_back_stake
  FROM market_derived_metrics
  ORDER BY snapshot_at DESC
  LIMIT 100
)
SELECT
  COUNT(*) AS total,
  SUM(CASE WHEN home_best_back_size_l1 IS NOT NULL THEN 1 ELSE 0 END) AS home_l1_back_nonnull,
  SUM(CASE WHEN home_back_stake IS NOT NULL THEN 1 ELSE 0 END) AS home_back_stake_nonnull
FROM last_100;
