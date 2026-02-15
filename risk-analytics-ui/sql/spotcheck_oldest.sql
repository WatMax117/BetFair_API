SELECT snapshot_at,
       home_best_back_size_l1, away_best_back_size_l1, draw_best_back_size_l1,
       home_best_lay_size_l1,  away_best_lay_size_l1,  draw_best_lay_size_l1,
       home_back_stake, away_back_stake, draw_back_stake,
       home_lay_stake,  away_lay_stake,  draw_lay_stake,
       home_impedance, away_impedance, draw_impedance
FROM market_derived_metrics
ORDER BY snapshot_at ASC
LIMIT 5;
