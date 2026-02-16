-- Per-event coverage: REST API snapshots per event
WITH match_markets AS (
  SELECT market_id, event_id, market_start_time
  FROM public.markets
  WHERE market_type = 'MATCH_ODDS_FT'
),
s AS (
  SELECT
    mm.event_id,
    s.market_id,
    mm.market_start_time,
    s.snapshot_at
  FROM public.market_book_snapshots s
  JOIN match_markets mm ON mm.market_id = s.market_id
  WHERE s.source = 'rest_listMarketBook'
)
SELECT
  event_id,
  COUNT(DISTINCT market_id) AS markets,
  MIN(market_start_time) AS market_start_time,
  MIN(snapshot_at) AS first_snapshot_time,
  MAX(snapshot_at) AS last_snapshot_time,
  COUNT(*) AS total_snapshots,
  (MAX(snapshot_at) - MIN(snapshot_at)) AS capture_span
FROM s
GROUP BY event_id
ORDER BY first_snapshot_time;
