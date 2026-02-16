-- Daily breakdown: REST API snapshots + unique counts per day
WITH match_markets AS (
  SELECT market_id, event_id
  FROM public.markets
  WHERE market_type = 'MATCH_ODDS_FT'
),
s AS (
  SELECT
    mm.event_id,
    s.market_id,
    s.snapshot_at::date AS snapshot_date
  FROM public.market_book_snapshots s
  JOIN match_markets mm ON mm.market_id = s.market_id
  WHERE s.source = 'rest_listMarketBook'
)
SELECT
  snapshot_date,
  COUNT(*) AS snapshots,
  COUNT(DISTINCT event_id) AS events,
  COUNT(DISTINCT market_id) AS markets
FROM s
GROUP BY snapshot_date
ORDER BY snapshot_date;
