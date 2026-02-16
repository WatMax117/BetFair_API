-- Export B: Last observed ladder values per market+selection (levels 1-8)
WITH match_markets AS (
  SELECT market_id, event_id, market_start_time
  FROM public.markets
  WHERE market_type = 'MATCH_ODDS_FT'
),
last_rows AS (
  SELECT DISTINCT ON (l.market_id, l.selection_id, l.level)
    mm.event_id,
    l.market_id,
    mm.market_start_time,
    l.selection_id,
    l.level,
    l.price AS back_odds,
    l.size AS back_size,
    l.publish_time,
    l.received_time
  FROM stream_ingest.ladder_levels l
  JOIN match_markets mm ON mm.market_id = l.market_id
  WHERE l.level BETWEEN 1 AND 8
    AND l.side = 'B'
  ORDER BY l.market_id, l.selection_id, l.level, l.publish_time DESC
)
SELECT
  event_id,
  market_id,
  market_start_time,
  selection_id,
  MAX(publish_time) AS last_publish_time_utc,
  MAX(received_time) AS last_received_time_utc,
  MAX(CASE WHEN level = 1 THEN back_odds END) AS back_odds_l1,
  MAX(CASE WHEN level = 1 THEN back_size END) AS back_size_l1,
  MAX(CASE WHEN level = 2 THEN back_odds END) AS back_odds_l2,
  MAX(CASE WHEN level = 2 THEN back_size END) AS back_size_l2,
  MAX(CASE WHEN level = 3 THEN back_odds END) AS back_odds_l3,
  MAX(CASE WHEN level = 3 THEN back_size END) AS back_size_l3,
  MAX(CASE WHEN level = 4 THEN back_odds END) AS back_odds_l4,
  MAX(CASE WHEN level = 4 THEN back_size END) AS back_size_l4,
  MAX(CASE WHEN level = 5 THEN back_odds END) AS back_odds_l5,
  MAX(CASE WHEN level = 5 THEN back_size END) AS back_size_l5,
  MAX(CASE WHEN level = 6 THEN back_odds END) AS back_odds_l6,
  MAX(CASE WHEN level = 6 THEN back_size END) AS back_size_l6,
  MAX(CASE WHEN level = 7 THEN back_odds END) AS back_odds_l7,
  MAX(CASE WHEN level = 7 THEN back_size END) AS back_size_l7,
  MAX(CASE WHEN level = 8 THEN back_odds END) AS back_odds_l8,
  MAX(CASE WHEN level = 8 THEN back_size END) AS back_size_l8
FROM last_rows
GROUP BY event_id, market_id, market_start_time, selection_id
ORDER BY market_id, selection_id;
