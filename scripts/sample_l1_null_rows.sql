-- Step 1b: Sample 20 rows where any *_best_back_size_l1 is NULL
SELECT snapshot_id, snapshot_at, market_id,
       home_best_back_size_l1, away_best_back_size_l1, draw_best_back_size_l1
FROM market_derived_metrics
WHERE home_best_back_size_l1 IS NULL OR away_best_back_size_l1 IS NULL OR draw_best_back_size_l1 IS NULL
ORDER BY snapshot_at DESC
LIMIT 20;
