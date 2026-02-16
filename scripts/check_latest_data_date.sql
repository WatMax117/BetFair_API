-- Check latest data date and row counts by date
SELECT 
    publish_time::date AS date,
    count(*) AS row_count,
    min(publish_time) AS min_ts,
    max(publish_time) AS max_ts
FROM stream_ingest.ladder_levels
GROUP BY publish_time::date
ORDER BY date DESC
LIMIT 5;
