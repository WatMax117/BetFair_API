-- Diagnose snapshot API logic step by step
-- Simulates the Python function get_events_by_date_snapshots_stream('2026-02-16')

-- Step 1: Get markets with ladder data (equivalent to get_stream_markets_with_ladder_for_date)
WITH stream_markets AS (
    SELECT DISTINCT market_id
    FROM stream_ingest.ladder_levels
    WHERE publish_time >= '2026-02-16 00:00:00+00'::timestamptz
      AND publish_time < '2026-02-17 00:00:00+00'::timestamptz
)
SELECT 'Step 1: Stream markets count' AS step, count(*) AS value FROM stream_markets;

-- Step 2: Get metadata for those markets (with event_open_date filter)
WITH stream_markets AS (
    SELECT DISTINCT market_id
    FROM stream_ingest.ladder_levels
    WHERE publish_time >= '2026-02-16 00:00:00+00'::timestamptz
      AND publish_time < '2026-02-17 00:00:00+00'::timestamptz
)
SELECT 
    'Step 2: Metadata matches' AS step,
    count(*) AS value
FROM market_event_metadata
WHERE market_id = ANY(ARRAY(SELECT market_id FROM stream_markets))
  AND event_open_date IS NOT NULL
  AND event_open_date >= '2026-02-16 00:00:00+00'::timestamptz
  AND event_open_date < '2026-02-17 00:00:00+00'::timestamptz;

-- Step 3: Check staleness for sample market (using CURRENT bucket, not end of day)
-- Current time bucket: 11:30:00 (assuming current time is ~11:32)
-- Stale cutoff: 11:30 - 120 minutes = 09:30:00
WITH test_market AS (
    SELECT '1.253003735'::text AS market_id
),
latest_bucket AS (
    SELECT '2026-02-16 11:30:00+00'::timestamptz AS bucket  -- Current bucket, not end of day
),
stale_cutoff AS (
    SELECT bucket - INTERVAL '120 minutes' AS cutoff FROM latest_bucket
),
market_latest AS (
    SELECT 
        MAX(publish_time) AS last_pt
    FROM stream_ingest.ladder_levels
    WHERE market_id = (SELECT market_id FROM test_market)
      AND publish_time <= (SELECT bucket FROM latest_bucket)
)
SELECT 
    'Step 3: Staleness check' AS step,
    m.market_id,
    ml.last_pt,
    sc.cutoff AS stale_cutoff,
    CASE 
        WHEN ml.last_pt IS NULL THEN 'NO_DATA'
        WHEN ml.last_pt < sc.cutoff THEN 'STALE'
        ELSE 'FRESH'
    END AS status
FROM test_market m
CROSS JOIN market_latest ml
CROSS JOIN stale_cutoff sc;

-- Step 4: Check if markets have required selection IDs
WITH stream_markets AS (
    SELECT DISTINCT market_id
    FROM stream_ingest.ladder_levels
    WHERE publish_time >= '2026-02-16 00:00:00+00'::timestamptz
      AND publish_time < '2026-02-17 00:00:00+00'::timestamptz
    LIMIT 10
)
SELECT 
    'Step 4: Metadata completeness' AS step,
    m.market_id,
    CASE WHEN mem.home_selection_id IS NOT NULL AND mem.away_selection_id IS NOT NULL AND mem.draw_selection_id IS NOT NULL THEN 'COMPLETE' ELSE 'INCOMPLETE' END AS metadata_status
FROM stream_markets m
LEFT JOIN market_event_metadata mem ON mem.market_id = m.market_id
WHERE mem.market_id IS NOT NULL
  AND mem.event_open_date IS NOT NULL
  AND mem.event_open_date >= '2026-02-16 00:00:00+00'::timestamptz
  AND mem.event_open_date < '2026-02-17 00:00:00+00'::timestamptz
LIMIT 5;
