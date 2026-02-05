-- Backfill segment from market_type in batches of 5000 to avoid long table locks.
-- Run manually after V5 (or when segment is NULL).
-- Repeat this script until: SELECT COUNT(*) FROM markets WHERE segment IS NULL OR segment = ''; returns 0.

-- Batch 1: MATCH_ODDS_FT -> 1X2_FT
UPDATE markets
SET segment = '1X2_FT'
WHERE market_type = 'MATCH_ODDS_FT'
  AND (segment IS NULL OR segment = '')
  AND market_id IN (
    SELECT market_id FROM markets
    WHERE market_type = 'MATCH_ODDS_FT' AND (segment IS NULL OR segment = '')
    LIMIT 5000
  );

-- Batch 2: OVER_UNDER_25_FT -> OU_FT
UPDATE markets
SET segment = 'OU_FT'
WHERE market_type = 'OVER_UNDER_25_FT'
  AND (segment IS NULL OR segment = '')
  AND market_id IN (
    SELECT market_id FROM markets
    WHERE market_type = 'OVER_UNDER_25_FT' AND (segment IS NULL OR segment = '')
    LIMIT 5000
  );

-- Batch 3: OVER_UNDER_05_HT -> OU_HT
UPDATE markets
SET segment = 'OU_HT'
WHERE market_type = 'OVER_UNDER_05_HT'
  AND (segment IS NULL OR segment = '')
  AND market_id IN (
    SELECT market_id FROM markets
    WHERE market_type = 'OVER_UNDER_05_HT' AND (segment IS NULL OR segment = '')
    LIMIT 5000
  );

-- Batch 4: HALF_TIME_RESULT -> HT_LOGIC
UPDATE markets
SET segment = 'HT_LOGIC'
WHERE market_type = 'HALF_TIME_RESULT'
  AND (segment IS NULL OR segment = '')
  AND market_id IN (
    SELECT market_id FROM markets
    WHERE market_type = 'HALF_TIME_RESULT' AND (segment IS NULL OR segment = '')
    LIMIT 5000
  );

-- Batch 5: NEXT_GOAL -> NEXT_GOAL
UPDATE markets
SET segment = 'NEXT_GOAL'
WHERE market_type = 'NEXT_GOAL'
  AND (segment IS NULL OR segment = '')
  AND market_id IN (
    SELECT market_id FROM markets
    WHERE market_type = 'NEXT_GOAL' AND (segment IS NULL OR segment = '')
    LIMIT 5000
  );
