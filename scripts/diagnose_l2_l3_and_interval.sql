-- Diagnosis: L2/L3 nulls and snapshot interval for one market.
-- Replace '1.253489253' with your market_id, then run on server:
--   docker cp scripts/diagnose_l2_l3_and_interval.sql netbet-postgres:/tmp/
--   docker exec netbet-postgres psql -U netbet -d netbet -f /tmp/diagnose_l2_l3_and_interval.sql

-- Part 1: L2/L3 and total_volume (last 20 snapshots)
SELECT snapshot_at,
       home_back_odds_l2, home_back_odds_l3,
       home_back_size_l2, home_back_size_l3,
       total_volume
FROM market_derived_metrics
WHERE market_id = '1.253489253'
ORDER BY snapshot_at DESC
LIMIT 20;

-- Part 2: Snapshot spacing (gaps in minutes)
WITH ordered AS (
  SELECT snapshot_at,
         LAG(snapshot_at) OVER (ORDER BY snapshot_at DESC) AS prev_at
  FROM market_derived_metrics
  WHERE market_id = '1.253489253'
)
SELECT snapshot_at,
       prev_at,
       ROUND(EXTRACT(EPOCH FROM (prev_at - snapshot_at)) / 60.0, 1) AS gap_minutes
FROM ordered
WHERE prev_at IS NOT NULL
ORDER BY snapshot_at DESC
LIMIT 15;
