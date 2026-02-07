-- Optional: drop old single-table schema. Do NOT run automatically.
-- Run only after 3-layer flow is verified and you no longer need market_risk_snapshots.

-- DROP TABLE IF EXISTS market_derived_metrics;
-- DROP TABLE IF EXISTS market_book_snapshots;
-- DROP TABLE IF EXISTS market_event_metadata;

DROP TABLE IF EXISTS market_risk_snapshots;
