-- Step 1: Baseline NULL counts for *_best_back_size_l1
SELECT
  COUNT(*) AS total_rows,
  COUNT(*) FILTER (WHERE home_best_back_size_l1 IS NULL) AS home_l1_null,
  COUNT(*) FILTER (WHERE away_best_back_size_l1 IS NULL) AS away_l1_null,
  COUNT(*) FILTER (WHERE draw_best_back_size_l1 IS NULL) AS draw_l1_null
FROM market_derived_metrics;

-- Recent 7 days NULL counts
SELECT
  COUNT(*) AS recent_total,
  COUNT(*) FILTER (WHERE home_best_back_size_l1 IS NULL) AS home_l1_null,
  COUNT(*) FILTER (WHERE away_best_back_size_l1 IS NULL) AS away_l1_null,
  COUNT(*) FILTER (WHERE draw_best_back_size_l1 IS NULL) AS draw_l1_null
FROM market_derived_metrics
WHERE snapshot_at >= NOW() - INTERVAL '7 days';
