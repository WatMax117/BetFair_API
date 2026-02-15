-- Check raw ladder availability for a snapshot where L2/L3 are NULL in derived metrics
-- Pick one snapshot from market 1.253489253
SELECT d.snapshot_id, d.snapshot_at, d.market_id,
       d.home_back_odds_l2, d.home_back_size_l2, d.home_back_odds_l3, d.home_back_size_l3
FROM market_derived_metrics d
WHERE d.market_id = '1.253489253' AND d.home_back_odds_l2 IS NULL
ORDER BY d.snapshot_at DESC
LIMIT 1;
