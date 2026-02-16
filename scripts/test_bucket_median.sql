-- Test query to validate bucket median calculation for a specific market/selection/bucket
-- Replace placeholders: MARKET_ID, SELECTION_ID, BUCKET_START

-- Example: Test for market '1.253494929', selection_id 47972 (home), bucket '2026-02-15 10:00:00+00'

WITH bucket_params AS (
    SELECT 
        '2026-02-15 10:00:00+00'::timestamptz AS bucket_start,
        '2026-02-15 10:15:00+00'::timestamptz AS bucket_end,
        LEAST('2026-02-15 10:15:00+00'::timestamptz, NOW()) AS effective_end
),
baseline AS (
    SELECT price AS baseline_odds, size AS baseline_size, publish_time AS baseline_time
    FROM stream_ingest.ladder_levels, bucket_params
    WHERE market_id = '1.253494929'
      AND selection_id = 47972
      AND side = 'B'
      AND level = 0
      AND publish_time <= bucket_start
    ORDER BY publish_time DESC
    LIMIT 1
),
updates AS (
    SELECT price, size, publish_time
    FROM stream_ingest.ladder_levels, bucket_params
    WHERE market_id = '1.253494929'
      AND selection_id = 47972
      AND side = 'B'
      AND level = 0
      AND publish_time > bucket_start
      AND publish_time <= effective_end
    ORDER BY publish_time ASC
)
SELECT 
    'Baseline' AS segment_type,
    baseline_odds,
    baseline_size,
    bucket_start AS segment_start,
    COALESCE((SELECT MIN(publish_time) FROM updates), effective_end) AS segment_end,
    EXTRACT(EPOCH FROM (COALESCE((SELECT MIN(publish_time) FROM updates), effective_end) - bucket_start)) AS duration_seconds
FROM baseline, bucket_params
WHERE EXISTS (SELECT 1 FROM baseline)
UNION ALL
SELECT 
    'Update ' || row_number() OVER (ORDER BY publish_time)::text AS segment_type,
    price AS baseline_odds,
    size AS baseline_size,
    publish_time AS segment_start,
    COALESCE(
        LEAD(publish_time) OVER (ORDER BY publish_time),
        effective_end
    ) AS segment_end,
    EXTRACT(EPOCH FROM (
        COALESCE(
            LEAD(publish_time) OVER (ORDER BY publish_time),
            effective_end
        ) - publish_time
    )) AS duration_seconds
FROM updates, bucket_params
ORDER BY segment_start;

-- Summary: Count segments and total duration
WITH bucket_params AS (
    SELECT 
        '2026-02-15 10:00:00+00'::timestamptz AS bucket_start,
        '2026-02-15 10:15:00+00'::timestamptz AS bucket_end,
        LEAST('2026-02-15 10:15:00+00'::timestamptz, NOW()) AS effective_end
),
baseline AS (
    SELECT price AS baseline_odds, size AS baseline_size
    FROM stream_ingest.ladder_levels, bucket_params
    WHERE market_id = '1.253494929'
      AND selection_id = 47972
      AND side = 'B'
      AND level = 0
      AND publish_time <= bucket_start
    ORDER BY publish_time DESC
    LIMIT 1
),
updates AS (
    SELECT price, size, publish_time
    FROM stream_ingest.ladder_levels, bucket_params
    WHERE market_id = '1.253494929'
      AND selection_id = 47972
      AND side = 'B'
      AND level = 0
      AND publish_time > bucket_start
      AND publish_time <= effective_end
    ORDER BY publish_time ASC
)
SELECT 
    COUNT(*) AS segment_count,
    SUM(EXTRACT(EPOCH FROM (segment_end - segment_start))) AS total_duration_seconds,
    baseline_odds AS baseline_odds,
    baseline_size AS baseline_size,
    (SELECT COUNT(*) FROM updates) AS update_count
FROM (
    SELECT 
        bucket_start AS segment_start,
        COALESCE((SELECT MIN(publish_time) FROM updates), effective_end) AS segment_end
    FROM baseline, bucket_params
    WHERE EXISTS (SELECT 1 FROM baseline)
    UNION ALL
    SELECT 
        publish_time AS segment_start,
        COALESCE(
            LEAD(publish_time) OVER (ORDER BY publish_time),
            effective_end
        ) AS segment_end
    FROM updates, bucket_params
) segments, baseline, bucket_params
GROUP BY baseline_odds, baseline_size;
