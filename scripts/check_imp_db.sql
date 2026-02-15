SELECT snapshot_at, market_id,
  home_best_back_size_l1, away_best_back_size_l1, draw_best_back_size_l1,
  home_impedance, away_impedance, draw_impedance,
  home_back_stake, away_back_stake, draw_back_stake
FROM market_derived_metrics
WHERE market_id = '1.253002724'
ORDER BY snapshot_at DESC
LIMIT 3;
