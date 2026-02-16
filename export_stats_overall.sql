-- Overall streaming capture statistics (single row)
WITH match_markets AS (
  SELECT market_id, event_id, market_start_time
  FROM public.markets
  WHERE market_type = 'MATCH_ODDS_FT'
),
s AS (
  SELECT
    mm.event_id,
    l.market_id,
    l.selection_id,
    l.publish_time,
    l.received_time
  FROM stream_ingest.ladder_levels l
  JOIN match_markets mm ON mm.market_id = l.market_id
  WHERE l.side = 'B'
    AND l.level BETWEEN 1 AND 8
)
SELECT
  COUNT(*) AS total_ticks,
  COUNT(DISTINCT event_id) AS distinct_events,
  COUNT(DISTINCT market_id) AS distinct_markets,
  COUNT(DISTINCT selection_id) AS distinct_selections,
  MIN(publish_time) AS min_publish_time,
  MAX(publish_time) AS max_publish_time,
  MIN(received_time) AS min_received_time,
  MAX(received_time) AS max_received_time
FROM s;
