-- Stream ingest diagnostic queries (run on VPS: docker exec -i netbet-postgres psql -U netbet -d netbet -f -)
\echo '=== 1. stream_ingest.ladder_levels ==='
SELECT count(*) AS total_rows FROM stream_ingest.ladder_levels;
SELECT max(publish_time) AS last_publish_time FROM stream_ingest.ladder_levels;
SELECT count(*) AS rows_last_12h FROM stream_ingest.ladder_levels WHERE publish_time > now() - interval '12 hours';

\echo '=== 1b. stream_ingest.market_liquidity_history ==='
SELECT count(*) AS total_liquidity_rows FROM stream_ingest.market_liquidity_history;
SELECT max(publish_time) AS max_liq_time FROM stream_ingest.market_liquidity_history;

\echo '=== 2. Date filtering (2026-02-16) ==='
SELECT count(*) AS cnt_date_cast FROM stream_ingest.ladder_levels WHERE publish_time::date = '2026-02-16';
SELECT count(*) AS cnt_utc_date FROM stream_ingest.ladder_levels WHERE (publish_time AT TIME ZONE 'utc')::date = '2026-02-16';

\echo '=== 2b. Today UTC ==='
SELECT (now() AT TIME ZONE 'utc')::date AS today_utc;
SELECT count(*) AS cnt_today_utc FROM stream_ingest.ladder_levels WHERE (publish_time AT TIME ZONE 'utc')::date = (now() AT TIME ZONE 'utc')::date;

\echo '=== 3. Metadata join: ladder markets last 12h without metadata ==='
SELECT ll.market_id
FROM (
  SELECT DISTINCT market_id
  FROM stream_ingest.ladder_levels
  WHERE publish_time > now() - interval '12 hours'
) ll
LEFT JOIN public.market_event_metadata m ON m.market_id = ll.market_id
WHERE m.market_id IS NULL
LIMIT 20;

\echo '=== 3b. Ladder markets last 12h WITH metadata (sample) ==='
SELECT ll.market_id, m.event_name, m.event_open_date
FROM (
  SELECT DISTINCT market_id
  FROM stream_ingest.ladder_levels
  WHERE publish_time > now() - interval '12 hours'
) ll
JOIN public.market_event_metadata m ON m.market_id = ll.market_id
WHERE m.event_open_date IS NOT NULL
LIMIT 5;
