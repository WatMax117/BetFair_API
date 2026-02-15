SELECT COUNT(*) FILTER (WHERE home_book_risk_l3 IS NULL) AS null_count,
       COUNT(*) AS total_count
FROM market_derived_metrics;
