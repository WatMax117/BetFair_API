-- Overall REST API capture statistics (single row)
WITH match_markets AS (
  SELECT market_id, event_id, market_start_time
  FROM public.markets
  WHERE market_type = 'MATCH_ODDS_FT'
),
s AS (
  SELECT
    mm.event_id,
    s.market_id,
    s.snapshot_at,
    s.source
  FROM public.market_book_snapshots s
  JOIN match_markets mm ON mm.market_id = s.market_id
  WHERE s.source = 'rest_listMarketBook'
)
SELECT
  COUNT(*) AS total_snapshots,
  COUNT(DISTINCT event_id) AS distinct_events,
  COUNT(DISTINCT market_id) AS distinct_markets,
  MIN(snapshot_at) AS min_snapshot_time,
  MAX(snapshot_at) AS max_snapshot_time
FROM s;
