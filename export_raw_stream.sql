-- RAW streaming export: tick-by-tick ladder updates (no aggregation)
-- Filters: MATCH_ODDS_FT markets, BACK side, levels 1-8
-- Time filter: last 7 days (adjust as needed)

WITH match_markets AS (
  SELECT
    m.market_id,
    m.event_id,
    m.market_start_time
  FROM public.markets m
  WHERE m.market_type = 'MATCH_ODDS_FT'
)
SELECT
  mm.event_id,
  l.market_id,
  mm.market_start_time,
  l.selection_id,
  l.level,
  l.publish_time,
  l.received_time,
  l.price AS back_odds,
  l.size AS back_size
FROM stream_ingest.ladder_levels l
JOIN match_markets mm ON mm.market_id = l.market_id
WHERE l.side = 'B'
  AND l.level BETWEEN 1 AND 8
  -- No time filter: export all available data (Feb 5-6, 2026)
ORDER BY
  l.market_id, l.selection_id, l.level, l.publish_time;
