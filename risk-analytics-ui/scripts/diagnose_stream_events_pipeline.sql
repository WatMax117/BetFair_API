-- Stream UI "Sorted events list" pipeline diagnosis
-- Run on VPS: cat risk-analytics-ui/scripts/diagnose_stream_events_pipeline.sql | docker exec -i netbet-postgres psql -U netbet -d netbet
-- Or: psql -U netbet -d netbet -f risk-analytics-ui/scripts/diagnose_stream_events_pipeline.sql
--
-- Uses current_date UTC for "today" (same as UI default). STALE_MINUTES = 120 (stream_data.STALE_MINUTES).

\echo '=== 1. Time window (same as UI: selected date = today UTC) ==='
WITH window AS (
  SELECT
    (current_date::timestamp AT TIME ZONE 'UTC') AS from_dt,
    (current_date::timestamp AT TIME ZONE 'UTC') + interval '1 day' AS to_dt,
    least((current_date::timestamp AT TIME ZONE 'UTC') + interval '1 day', now()) AS effective_to
)
SELECT current_date AS selected_date, * FROM window;

\echo ''
\echo '=== 2. DB: stream_ingest.ladder_levels – markets with ≥1 tick in date window ==='
SELECT count(DISTINCT market_id) AS stream_markets_in_date_window
FROM stream_ingest.ladder_levels
WHERE publish_time >= (current_date::timestamp AT TIME ZONE 'UTC')
  AND publish_time < (current_date::timestamp AT TIME ZONE 'UTC') + interval '1 day';

\echo ''
\echo '=== 3. DB: market_event_metadata – how many of those have metadata? ==='
WITH stream_markets AS (
  SELECT DISTINCT market_id
  FROM stream_ingest.ladder_levels
  WHERE publish_time >= (current_date::timestamp AT TIME ZONE 'UTC')
    AND publish_time < (current_date::timestamp AT TIME ZONE 'UTC') + interval '1 day'
)
SELECT
  (SELECT count(*) FROM stream_markets) AS stream_market_count,
  (SELECT count(*) FROM market_event_metadata m WHERE m.market_id IN (SELECT market_id FROM stream_markets)) AS with_metadata,
  (SELECT count(*) FROM stream_markets sm LEFT JOIN market_event_metadata m ON m.market_id = sm.market_id WHERE m.market_id IS NULL) AS without_metadata;

\echo ''
\echo '=== 4. DB: distinct events in metadata (for stream markets in window) ==='
WITH stream_markets AS (
  SELECT DISTINCT market_id
  FROM stream_ingest.ladder_levels
  WHERE publish_time >= (current_date::timestamp AT TIME ZONE 'UTC')
    AND publish_time < (current_date::timestamp AT TIME ZONE 'UTC') + interval '1 day'
)
SELECT count(DISTINCT m.event_id) AS distinct_events_with_metadata
FROM market_event_metadata m
WHERE m.market_id IN (SELECT market_id FROM stream_markets);

\echo ''
\echo '=== 5. Staleness: latest_bucket and cutoff (STALE_MINUTES = 120) ==='
WITH effective AS (
  SELECT least((current_date::timestamp AT TIME ZONE 'UTC') + interval '1 day', now()) AS effective_to
),
bucket AS (
  SELECT date_trunc('hour', (SELECT effective_to FROM effective)) +
    (interval '15 min' * floor(extract(epoch FROM (SELECT effective_to FROM effective) - date_trunc('hour', (SELECT effective_to FROM effective))) / 900)) AS latest_bucket
)
SELECT
  (SELECT latest_bucket FROM bucket) AS latest_bucket_utc,
  (SELECT latest_bucket FROM bucket) - interval '120 minutes' AS stale_cutoff_utc;

\echo ''
\echo '=== 6. Markets: with metadata, then after staleness (last tick within 120 min of latest_bucket) ==='
WITH stream_markets AS (
  SELECT DISTINCT market_id
  FROM stream_ingest.ladder_levels
  WHERE publish_time >= (current_date::timestamp AT TIME ZONE 'UTC')
    AND publish_time < (current_date::timestamp AT TIME ZONE 'UTC') + interval '1 day'
),
effective AS (
  SELECT least((current_date::timestamp AT TIME ZONE 'UTC') + interval '1 day', now()) AS effective_to
),
latest_bucket AS (
  SELECT date_trunc('hour', (SELECT effective_to FROM effective)) +
    (interval '15 min' * floor(extract(epoch FROM (SELECT effective_to FROM effective) - date_trunc('hour', (SELECT effective_to FROM effective))) / 900)) AS lb
),
last_tick AS (
  SELECT market_id, max(publish_time) AS last_pt
  FROM stream_ingest.ladder_levels
  GROUP BY market_id
)
SELECT
  count(*) FILTER (WHERE m.market_id IS NOT NULL) AS with_metadata,
  count(*) FILTER (WHERE m.market_id IS NOT NULL AND lt.last_pt IS NOT NULL AND lt.last_pt >= (SELECT lb FROM latest_bucket) - interval '120 minutes') AS after_staleness_kept
FROM stream_markets sm
LEFT JOIN market_event_metadata m ON m.market_id = sm.market_id
LEFT JOIN last_tick lt ON lt.market_id = sm.market_id;

\echo ''
\echo '=== 7. Total rows in market_event_metadata (all time) ==='
SELECT count(*) AS total_metadata_rows FROM market_event_metadata;

\echo ''
\echo '=== 8. market_event_metadata last_seen_at (when was metadata last updated?) ==='
SELECT min(last_seen_at) AS min_last_seen, max(last_seen_at) AS max_last_seen, count(*) AS total
FROM market_event_metadata;

\echo ''
\echo '=== 9. public.markets (streaming client) – market types and counts ==='
SELECT market_type, count(*) AS cnt
FROM public.markets
GROUP BY market_type
ORDER BY market_type;

\echo ''
\echo '=== 10. Sample market_ids in ladder_levels (last 24h) not in market_event_metadata ==='
SELECT ll.market_id
FROM (
  SELECT DISTINCT market_id FROM stream_ingest.ladder_levels
  WHERE publish_time > now() - interval '24 hours'
) ll
LEFT JOIN public.market_event_metadata m ON m.market_id = ll.market_id
WHERE m.market_id IS NULL
LIMIT 15;
