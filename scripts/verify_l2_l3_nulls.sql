SELECT
  COUNT(*) AS total_rows,
  COUNT(*) FILTER (WHERE home_back_odds_l2 IS NULL) AS home_l2_null,
  COUNT(*) FILTER (WHERE home_back_odds_l3 IS NULL) AS home_l3_null,
  COUNT(*) FILTER (WHERE away_back_odds_l2 IS NULL) AS away_l2_null,
  COUNT(*) FILTER (WHERE away_back_odds_l3 IS NULL) AS away_l3_null,
  COUNT(*) FILTER (WHERE draw_back_odds_l2 IS NULL) AS draw_l2_null,
  COUNT(*) FILTER (WHERE draw_back_odds_l3 IS NULL) AS draw_l3_null
FROM market_derived_metrics;
