-- Per-event coverage: start/end timestamps per event
WITH match_markets AS (
  SELECT market_id, event_id, market_start_time
  FROM public.markets
  WHERE market_type = 'MATCH_ODDS_FT'
),
s AS (
  SELECT
    mm.event_id,
    l.market_id,
    mm.market_start_time,
    l.publish_time
  FROM stream_ingest.ladder_levels l
  JOIN match_markets mm ON mm.market_id = l.market_id
  WHERE l.side = 'B'
    AND l.level BETWEEN 1 AND 8
)
SELECT
  event_id,
  COUNT(DISTINCT market_id) AS markets,
  MIN(market_start_time) AS market_start_time,
  MIN(publish_time) AS first_tick_time,
  MAX(publish_time) AS last_tick_time,
  (MAX(publish_time) - MIN(publish_time)) AS capture_span
FROM s
GROUP BY event_id
ORDER BY first_tick_time;
