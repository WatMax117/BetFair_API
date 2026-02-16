-- Test query that matches the snapshot API logic
-- Date: 2026-02-16

-- Step 1: Get markets with ladder data for the date
WITH stream_markets AS (
    SELECT DISTINCT market_id
    FROM stream_ingest.ladder_levels
    WHERE publish_time >= '2026-02-16 00:00:00+00'::timestamptz
      AND publish_time < '2026-02-17 00:00:00+00'::timestamptz
)
SELECT 
    'Stream markets count' AS label,
    count(*) AS value
FROM stream_markets;

-- Step 2: Check if market_event_metadata has entries for those markets
WITH stream_markets AS (
    SELECT DISTINCT market_id
    FROM stream_ingest.ladder_levels
    WHERE publish_time >= '2026-02-16 00:00:00+00'::timestamptz
      AND publish_time < '2026-02-17 00:00:00+00'::timestamptz
)
SELECT 
    'Metadata matches (with event_open_date filter)' AS label,
    count(*) AS value
FROM market_event_metadata
WHERE market_id = ANY(ARRAY(SELECT market_id FROM stream_markets))
  AND event_open_date IS NOT NULL
  AND event_open_date >= '2026-02-16 00:00:00+00'::timestamptz
  AND event_open_date < '2026-02-17 00:00:00+00'::timestamptz;

-- Step 3: Check metadata matches WITHOUT event_open_date filter
WITH stream_markets AS (
    SELECT DISTINCT market_id
    FROM stream_ingest.ladder_levels
    WHERE publish_time >= '2026-02-16 00:00:00+00'::timestamptz
      AND publish_time < '2026-02-17 00:00:00+00'::timestamptz
)
SELECT 
    'Metadata matches (NO event_open_date filter)' AS label,
    count(*) AS value
FROM market_event_metadata
WHERE market_id = ANY(ARRAY(SELECT market_id FROM stream_markets));

-- Step 4: Sample market_id and its event_open_date
WITH stream_markets AS (
    SELECT DISTINCT market_id
    FROM stream_ingest.ladder_levels
    WHERE publish_time >= '2026-02-16 00:00:00+00'::timestamptz
      AND publish_time < '2026-02-17 00:00:00+00'::timestamptz
    LIMIT 5
)
SELECT 
    m.market_id,
    m.event_open_date,
    CASE 
        WHEN m.event_open_date IS NULL THEN 'NULL'
        WHEN m.event_open_date >= '2026-02-16 00:00:00+00'::timestamptz 
         AND m.event_open_date < '2026-02-17 00:00:00+00'::timestamptz THEN 'IN_RANGE'
        ELSE 'OUT_OF_RANGE'
    END AS filter_status
FROM market_event_metadata m
WHERE m.market_id = ANY(ARRAY(SELECT market_id FROM stream_markets))
ORDER BY m.market_id;
