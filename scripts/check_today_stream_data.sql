-- Check streaming data for today (UTC)
SELECT 
    count(*) AS row_count,
    min(publish_time) AS min_ts,
    max(publish_time) AS max_ts
FROM stream_ingest.ladder_levels
WHERE publish_time::date = CURRENT_DATE;

-- Also check last 24 hours
SELECT 
    count(*) AS rows_last_24h,
    min(publish_time) AS min_ts_24h,
    max(publish_time) AS max_ts_24h
FROM stream_ingest.ladder_levels
WHERE publish_time >= CURRENT_TIMESTAMP - interval '24 hours';
