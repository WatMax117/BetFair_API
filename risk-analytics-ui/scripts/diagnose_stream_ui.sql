-- Stream UI diagnostics (run with psql, e.g. psql -U netbet -d netbet -f scripts/diagnose_stream_ui.sql)
-- 2. Streaming data freshness
\echo '=== 2. Streaming data freshness (stream_ingest.ladder_levels) ==='
SELECT max(publish_time) AS last_publish_time
FROM stream_ingest.ladder_levels;

SELECT count(*) AS rows_last_60m
FROM stream_ingest.ladder_levels
WHERE publish_time > now() - interval '60 minutes';

-- 4. Metadata join: ladder markets without public.market_event_metadata
\echo '=== 4. Metadata join (markets in ladder last 6h without metadata) ==='
SELECT ll.market_id
FROM (
  SELECT DISTINCT market_id
  FROM stream_ingest.ladder_levels
  WHERE publish_time > now() - interval '6 hours'
) ll
LEFT JOIN public.market_event_metadata m ON m.market_id = ll.market_id
WHERE m.market_id IS NULL
LIMIT 20;

-- 5. Timezone consistency
\echo '=== 5. Timezone consistency ==='
SELECT
  now() AS server_time,
  now() AT TIME ZONE 'utc' AS utc_time,
  max(publish_time) AS last_publish_time
FROM stream_ingest.ladder_levels;
