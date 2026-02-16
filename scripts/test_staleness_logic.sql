-- Test staleness logic for snapshot API
-- Simulate the Python logic for 2026-02-16

-- Current time (simulated as 2026-02-16 12:00 UTC)
-- Latest bucket would be: floor to 15-min = 11:45:00
-- Stale cutoff = 11:45 - 120 minutes = 09:45:00

WITH test_markets AS (
    SELECT DISTINCT market_id
    FROM stream_ingest.ladder_levels
    WHERE publish_time >= '2026-02-16 00:00:00+00'::timestamptz
      AND publish_time < '2026-02-17 00:00:00+00'::timestamptz
    LIMIT 5
),
market_latest AS (
    SELECT 
        m.market_id,
        MAX(l.publish_time) AS latest_publish_time
    FROM test_markets m
    JOIN stream_ingest.ladder_levels l ON l.market_id = m.market_id
    WHERE l.publish_time <= '2026-02-16 11:45:00+00'::timestamptz  -- latest bucket
    GROUP BY m.market_id
)
SELECT 
    m.market_id,
    m.latest_publish_time,
    '2026-02-16 09:45:00+00'::timestamptz AS stale_cutoff,
    CASE 
        WHEN m.latest_publish_time IS NULL THEN 'NO_DATA'
        WHEN m.latest_publish_time < '2026-02-16 09:45:00+00'::timestamptz THEN 'STALE'
        ELSE 'FRESH'
    END AS status
FROM market_latest m
ORDER BY m.market_id;
