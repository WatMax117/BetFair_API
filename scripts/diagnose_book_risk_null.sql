-- Diagnose why Book Risk L3 is NULL for some markets
-- Run per market_id. Replace :market_id with actual value.

-- A1) Latest 20 derived rows for a market (NULL vs non-NULL)
SELECT snapshot_id, snapshot_at,
       home_book_risk_l3, away_book_risk_l3, draw_book_risk_l3,
       home_back_odds_l2, home_back_size_l2, home_back_odds_l3, home_back_size_l3
FROM market_derived_metrics
WHERE market_id = :market_id
ORDER BY snapshot_at DESC
LIMIT 20;

-- A2) For a snapshot_id with NULL book_risk_l3, check raw_payload has availableToBack
-- (run separately; raw_payload is large)
-- SELECT snapshot_id, snapshot_at, market_id,
--        jsonb_path_exists(raw_payload, '$.runners[*].ex.availableToBack[0]') AS has_l1,
--        jsonb_path_exists(raw_payload, '$.runners[*].ex.availableToBack[2]') AS has_l3
-- FROM market_book_snapshots WHERE snapshot_id = :snapshot_id;

-- A3) Runner metadata (HOME/AWAY/DRAW mapping)
SELECT market_id, home_selection_id, away_selection_id, draw_selection_id
FROM market_event_metadata
WHERE market_id = :market_id;
