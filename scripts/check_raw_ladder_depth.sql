SELECT m.snapshot_id, m.market_id,
       jsonb_array_length(COALESCE(m.raw_payload->'runners'->0->'ex'->'availableToBack','[]'::jsonb)) AS atb_levels
FROM market_book_snapshots m
INNER JOIN market_derived_metrics d ON d.snapshot_id = m.snapshot_id
WHERE d.home_back_odds_l2 IS NULL
LIMIT 10;
