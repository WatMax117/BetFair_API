-- Export A: 5-minute aggregated time series (BACK side, levels 1-8)
-- Pivoted by home/away/draw with selection mapping

WITH match_markets AS (
  SELECT
    m.market_id,
    m.event_id,
    m.market_start_time
  FROM public.markets m
  WHERE m.market_type = 'MATCH_ODDS_FT'
),
sel_map AS (
  SELECT
    market_id,
    home_selection_id,
    away_selection_id,
    draw_selection_id
  FROM public.market_event_metadata
),
stream AS (
  SELECT
    mm.event_id,
    mm.market_id,
    mm.market_start_time,
    l.selection_id,
    l.level,
    l.price AS back_odds,
    l.size AS back_size,
    l.publish_time,
    l.received_time,
    date_bin('5 minutes', l.publish_time, TIMESTAMPTZ '1970-01-01') AS bucket_start
  FROM stream_ingest.ladder_levels l
  JOIN match_markets mm ON mm.market_id = l.market_id
  WHERE l.level BETWEEN 1 AND 8
    AND l.side = 'B'
)
SELECT
  s.event_id,
  s.market_id,
  s.market_start_time,
  s.bucket_start AS bucket_start_utc,
  MIN(s.publish_time) AS publish_time_min_utc,
  MAX(s.received_time) AS received_time_max_utc,
  -- HOME (8 levels)
  MAX(CASE WHEN s.selection_id = sm.home_selection_id AND s.level = 1 THEN s.back_odds END) AS home_back_odds_l1,
  MAX(CASE WHEN s.selection_id = sm.home_selection_id AND s.level = 1 THEN s.back_size END) AS home_back_size_l1,
  MAX(CASE WHEN s.selection_id = sm.home_selection_id AND s.level = 2 THEN s.back_odds END) AS home_back_odds_l2,
  MAX(CASE WHEN s.selection_id = sm.home_selection_id AND s.level = 2 THEN s.back_size END) AS home_back_size_l2,
  MAX(CASE WHEN s.selection_id = sm.home_selection_id AND s.level = 3 THEN s.back_odds END) AS home_back_odds_l3,
  MAX(CASE WHEN s.selection_id = sm.home_selection_id AND s.level = 3 THEN s.back_size END) AS home_back_size_l3,
  MAX(CASE WHEN s.selection_id = sm.home_selection_id AND s.level = 4 THEN s.back_odds END) AS home_back_odds_l4,
  MAX(CASE WHEN s.selection_id = sm.home_selection_id AND s.level = 4 THEN s.back_size END) AS home_back_size_l4,
  MAX(CASE WHEN s.selection_id = sm.home_selection_id AND s.level = 5 THEN s.back_odds END) AS home_back_odds_l5,
  MAX(CASE WHEN s.selection_id = sm.home_selection_id AND s.level = 5 THEN s.back_size END) AS home_back_size_l5,
  MAX(CASE WHEN s.selection_id = sm.home_selection_id AND s.level = 6 THEN s.back_odds END) AS home_back_odds_l6,
  MAX(CASE WHEN s.selection_id = sm.home_selection_id AND s.level = 6 THEN s.back_size END) AS home_back_size_l6,
  MAX(CASE WHEN s.selection_id = sm.home_selection_id AND s.level = 7 THEN s.back_odds END) AS home_back_odds_l7,
  MAX(CASE WHEN s.selection_id = sm.home_selection_id AND s.level = 7 THEN s.back_size END) AS home_back_size_l7,
  MAX(CASE WHEN s.selection_id = sm.home_selection_id AND s.level = 8 THEN s.back_odds END) AS home_back_odds_l8,
  MAX(CASE WHEN s.selection_id = sm.home_selection_id AND s.level = 8 THEN s.back_size END) AS home_back_size_l8,
  -- AWAY (8 levels)
  MAX(CASE WHEN s.selection_id = sm.away_selection_id AND s.level = 1 THEN s.back_odds END) AS away_back_odds_l1,
  MAX(CASE WHEN s.selection_id = sm.away_selection_id AND s.level = 1 THEN s.back_size END) AS away_back_size_l1,
  MAX(CASE WHEN s.selection_id = sm.away_selection_id AND s.level = 2 THEN s.back_odds END) AS away_back_odds_l2,
  MAX(CASE WHEN s.selection_id = sm.away_selection_id AND s.level = 2 THEN s.back_size END) AS away_back_size_l2,
  MAX(CASE WHEN s.selection_id = sm.away_selection_id AND s.level = 3 THEN s.back_odds END) AS away_back_odds_l3,
  MAX(CASE WHEN s.selection_id = sm.away_selection_id AND s.level = 3 THEN s.back_size END) AS away_back_size_l3,
  MAX(CASE WHEN s.selection_id = sm.away_selection_id AND s.level = 4 THEN s.back_odds END) AS away_back_odds_l4,
  MAX(CASE WHEN s.selection_id = sm.away_selection_id AND s.level = 4 THEN s.back_size END) AS away_back_size_l4,
  MAX(CASE WHEN s.selection_id = sm.away_selection_id AND s.level = 5 THEN s.back_odds END) AS away_back_odds_l5,
  MAX(CASE WHEN s.selection_id = sm.away_selection_id AND s.level = 5 THEN s.back_size END) AS away_back_size_l5,
  MAX(CASE WHEN s.selection_id = sm.away_selection_id AND s.level = 6 THEN s.back_odds END) AS away_back_odds_l6,
  MAX(CASE WHEN s.selection_id = sm.away_selection_id AND s.level = 6 THEN s.back_size END) AS away_back_size_l6,
  MAX(CASE WHEN s.selection_id = sm.away_selection_id AND s.level = 7 THEN s.back_odds END) AS away_back_odds_l7,
  MAX(CASE WHEN s.selection_id = sm.away_selection_id AND s.level = 7 THEN s.back_size END) AS away_back_size_l7,
  MAX(CASE WHEN s.selection_id = sm.away_selection_id AND s.level = 8 THEN s.back_odds END) AS away_back_odds_l8,
  MAX(CASE WHEN s.selection_id = sm.away_selection_id AND s.level = 8 THEN s.back_size END) AS away_back_size_l8,
  -- DRAW (8 levels)
  MAX(CASE WHEN s.selection_id = sm.draw_selection_id AND s.level = 1 THEN s.back_odds END) AS draw_back_odds_l1,
  MAX(CASE WHEN s.selection_id = sm.draw_selection_id AND s.level = 1 THEN s.back_size END) AS draw_back_size_l1,
  MAX(CASE WHEN s.selection_id = sm.draw_selection_id AND s.level = 2 THEN s.back_odds END) AS draw_back_odds_l2,
  MAX(CASE WHEN s.selection_id = sm.draw_selection_id AND s.level = 2 THEN s.back_size END) AS draw_back_size_l2,
  MAX(CASE WHEN s.selection_id = sm.draw_selection_id AND s.level = 3 THEN s.back_odds END) AS draw_back_odds_l3,
  MAX(CASE WHEN s.selection_id = sm.draw_selection_id AND s.level = 3 THEN s.back_size END) AS draw_back_size_l3,
  MAX(CASE WHEN s.selection_id = sm.draw_selection_id AND s.level = 4 THEN s.back_odds END) AS draw_back_odds_l4,
  MAX(CASE WHEN s.selection_id = sm.draw_selection_id AND s.level = 4 THEN s.back_size END) AS draw_back_size_l4,
  MAX(CASE WHEN s.selection_id = sm.draw_selection_id AND s.level = 5 THEN s.back_odds END) AS draw_back_odds_l5,
  MAX(CASE WHEN s.selection_id = sm.draw_selection_id AND s.level = 5 THEN s.back_size END) AS draw_back_size_l5,
  MAX(CASE WHEN s.selection_id = sm.draw_selection_id AND s.level = 6 THEN s.back_odds END) AS draw_back_odds_l6,
  MAX(CASE WHEN s.selection_id = sm.draw_selection_id AND s.level = 6 THEN s.back_size END) AS draw_back_size_l6,
  MAX(CASE WHEN s.selection_id = sm.draw_selection_id AND s.level = 7 THEN s.back_odds END) AS draw_back_odds_l7,
  MAX(CASE WHEN s.selection_id = sm.draw_selection_id AND s.level = 7 THEN s.back_size END) AS draw_back_size_l7,
  MAX(CASE WHEN s.selection_id = sm.draw_selection_id AND s.level = 8 THEN s.back_odds END) AS draw_back_odds_l8,
  MAX(CASE WHEN s.selection_id = sm.draw_selection_id AND s.level = 8 THEN s.back_size END) AS draw_back_size_l8
FROM stream s
LEFT JOIN sel_map sm ON sm.market_id = s.market_id
GROUP BY s.event_id, s.market_id, s.market_start_time, s.bucket_start
ORDER BY s.market_id, s.bucket_start;
