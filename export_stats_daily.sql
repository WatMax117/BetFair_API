-- Daily breakdown: ticks + unique counts per day
WITH match_markets AS (
  SELECT market_id, event_id
  FROM public.markets
  WHERE market_type = 'MATCH_ODDS_FT'
),
s AS (
  SELECT
    mm.event_id,
    l.market_id,
    l.selection_id,
    l.publish_time::date AS publish_date,
    l.received_time::date AS received_date
  FROM stream_ingest.ladder_levels l
  JOIN match_markets mm ON mm.market_id = l.market_id
  WHERE l.side = 'B'
    AND l.level BETWEEN 1 AND 8
)
SELECT
  publish_date,
  COUNT(*) AS ticks,
  COUNT(DISTINCT event_id) AS events,
  COUNT(DISTINCT market_id) AS markets,
  COUNT(DISTINCT selection_id) AS selections
FROM s
GROUP BY publish_date
ORDER BY publish_date;
