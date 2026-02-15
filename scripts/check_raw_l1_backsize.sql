-- Step 2: Raw ladder L1 check - show availableToBack[0] for runners in sample snapshots with NULL L1 backsize
WITH sample AS (
  SELECT m.snapshot_id, m.market_id, m.raw_payload
  FROM market_book_snapshots m
  INNER JOIN market_derived_metrics d ON d.snapshot_id = m.snapshot_id
  WHERE d.home_best_back_size_l1 IS NULL OR d.away_best_back_size_l1 IS NULL OR d.draw_best_back_size_l1 IS NULL
  LIMIT 5
)
SELECT s.snapshot_id, s.market_id,
       jsonb_array_length(COALESCE(s.raw_payload->'runners'->0->'ex'->'availableToBack','[]'::jsonb)) AS home_atb_len,
       (s.raw_payload->'runners'->0->'ex'->'availableToBack'->0->>0)::float AS home_atb0_price,
       (s.raw_payload->'runners'->0->'ex'->'availableToBack'->0->>1)::float AS home_atb0_size,
       jsonb_array_length(COALESCE(s.raw_payload->'runners'->1->'ex'->'availableToBack','[]'::jsonb)) AS away_atb_len,
       (s.raw_payload->'runners'->1->'ex'->'availableToBack'->0->>0)::float AS away_atb0_price,
       (s.raw_payload->'runners'->1->'ex'->'availableToBack'->0->>1)::float AS away_atb0_size,
       jsonb_array_length(COALESCE(s.raw_payload->'runners'->2->'ex'->'availableToBack','[]'::jsonb)) AS draw_atb_len,
       (s.raw_payload->'runners'->2->'ex'->'availableToBack'->0->>0)::float AS draw_atb0_price,
       (s.raw_payload->'runners'->2->'ex'->'availableToBack'->0->>1)::float AS draw_atb0_size
FROM sample s;
