-- Verification queries: confirm streaming writes go to stream_ingest.ladder_levels (not public).
-- Run after deploying schema-qualified SQL fix and restarting streaming client.

-- A) Confirm streaming writes are landing in stream_ingest today
SELECT 
    'stream_ingest.ladder_levels' AS table_name,
    count(*) AS row_count,
    min(publish_time) AS min_ts,
    max(publish_time) AS max_ts
FROM stream_ingest.ladder_levels
WHERE publish_time::date = CURRENT_DATE;

-- B) Confirm public.ladder_levels is no longer receiving writes
SELECT 
    'public.ladder_levels' AS table_name,
    count(*) AS row_count,
    min(publish_time) AS min_ts,
    max(publish_time) AS max_ts
FROM public.ladder_levels
WHERE publish_time::date = CURRENT_DATE;

-- C) Compare max publish_time: stream_ingest should be newer than public
SELECT 
    'stream_ingest max' AS label,
    max(publish_time) AS max_ts
FROM stream_ingest.ladder_levels
UNION ALL
SELECT 
    'public max',
    max(publish_time)
FROM public.ladder_levels;

-- Expected results:
-- A) stream_ingest: count > 0, max_ts advances forward
-- B) public: count = 0 (or max_ts does not advance)
-- C) stream_ingest max_ts > public max_ts (or public max_ts is NULL/old)
