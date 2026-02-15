-- Post-event data integrity & Book Risk L3 dynamics report
-- Market: 1.253489253 (Lazio v Atalanta)
-- Uses public schema only. Run: SET search_path = public; before this script if needed.
-- Run: docker exec -i netbet-postgres psql -U netbet -d netbet -f - < scripts/report_lazio_atalanta_market_public.sql

\set market_id '1.253489253'

\echo '========================================'
\echo 'LAZIO v ATALANTA - MARKET 1.253489253'
\echo 'Post-event Data Integrity & Book Risk L3 Report (public schema)'
\echo '========================================'
\echo ''

\echo '--- Event metadata (kickoff) ---'
SELECT market_id, event_name, event_open_date, competition_name,
       home_runner_name, away_runner_name, draw_runner_name
FROM market_event_metadata WHERE market_id = :'market_id';

\echo ''
\echo '=== A1) SNAPSHOT CONTINUITY ==='
WITH ordered AS (
  SELECT snapshot_id, snapshot_at,
         LAG(snapshot_at) OVER (ORDER BY snapshot_at) AS prev_at,
         snapshot_at - LAG(snapshot_at) OVER (ORDER BY snapshot_at) AS gap
  FROM market_derived_metrics WHERE market_id = :'market_id'
)
SELECT
  (SELECT COUNT(*) FROM market_derived_metrics WHERE market_id = :'market_id') AS total_snapshots,
  (SELECT MIN(snapshot_at) FROM market_derived_metrics WHERE market_id = :'market_id') AS min_snapshot_at,
  (SELECT MAX(snapshot_at) FROM market_derived_metrics WHERE market_id = :'market_id') AS max_snapshot_at,
  (SELECT ROUND(AVG(EXTRACT(EPOCH FROM gap)), 1) FROM ordered WHERE gap IS NOT NULL) AS avg_interval_seconds,
  (SELECT COUNT(*) FROM ordered WHERE gap > INTERVAL '15 minutes') AS gaps_over_15min;

\echo ''
\echo '--- A1) Detected time gaps (>15 min) ---'
WITH ordered AS (
  SELECT snapshot_at AS end_at,
         LAG(snapshot_at) OVER (ORDER BY snapshot_at) AS start_at,
         snapshot_at - LAG(snapshot_at) OVER (ORDER BY snapshot_at) AS gap
  FROM (SELECT DISTINCT snapshot_at FROM market_derived_metrics WHERE market_id = :'market_id') u
),
kickoff AS (SELECT event_open_date AS k FROM market_event_metadata WHERE market_id = :'market_id')
SELECT
  o.start_at AS gap_start,
  o.end_at AS gap_end,
  o.gap AS duration,
  CASE WHEN o.start_at < k.k AND o.end_at <= k.k THEN 'PRE-KICKOFF'
       WHEN o.start_at >= k.k THEN 'IN-PLAY'
       ELSE 'BRIDGE' END AS period
FROM ordered o, kickoff k
WHERE o.gap > INTERVAL '15 minutes'
ORDER BY o.start_at;

\echo ''
\echo '=== A2) DERIVED METRICS COMPLETENESS ==='
SELECT
  COUNT(*) AS total_snapshots,
  COUNT(CASE WHEN home_book_risk_l3 IS NULL OR away_book_risk_l3 IS NULL OR draw_book_risk_l3 IS NULL THEN 1 END) AS snapshots_with_null_book_risk_l3,
  COUNT(CASE WHEN home_back_odds_l2 IS NULL OR home_back_size_l2 IS NULL THEN 1 END) AS snapshots_missing_home_l2,
  COUNT(CASE WHEN home_back_odds_l3 IS NULL OR home_back_size_l3 IS NULL THEN 1 END) AS snapshots_missing_home_l3,
  COUNT(CASE WHEN total_volume IS NULL THEN 1 END) AS snapshots_null_total_volume
FROM market_derived_metrics WHERE market_id = :'market_id';

\echo ''
\echo '=== A3) PRE-MATCH DATA ==='
WITH kickoff AS (SELECT event_open_date AS k FROM market_event_metadata WHERE market_id = :'market_id')
SELECT
  COUNT(*) AS pre_match_snapshots_6h_to_kickoff,
  COUNT(CASE WHEN d.snapshot_at >= k.k - INTERVAL '1 hour' AND d.snapshot_at <= k.k THEN 1 END) AS snapshots_last_1h,
  COUNT(CASE WHEN d.home_book_risk_l3 IS NOT NULL AND d.away_book_risk_l3 IS NOT NULL AND d.draw_book_risk_l3 IS NOT NULL THEN 1 END) AS with_full_book_risk_l3,
  COUNT(CASE WHEN d.home_best_back_size_l1 IS NOT NULL AND d.home_best_back_size_l1 > 0 THEN 1 END) AS with_l1_liquidity
FROM market_derived_metrics d, kickoff k
WHERE d.market_id = :'market_id' AND d.snapshot_at >= k.k - INTERVAL '6 hours' AND d.snapshot_at <= k.k;

\echo ''
\echo '=== A4) Sample: Snapshots with NULL book_risk_l3 (first 10) ==='
SELECT snapshot_id, snapshot_at, home_book_risk_l3, away_book_risk_l3, draw_book_risk_l3
FROM market_derived_metrics
WHERE market_id = :'market_id'
  AND (home_book_risk_l3 IS NULL OR away_book_risk_l3 IS NULL OR draw_book_risk_l3 IS NULL)
ORDER BY snapshot_at DESC
LIMIT 10;

\echo ''
\echo '=== B) Book Risk L3 at 5 key time points ==='
WITH kickoff AS (SELECT event_open_date AS k FROM market_event_metadata WHERE market_id = :'market_id'),
pts AS (
  SELECT 'T-6h' AS pt, (SELECT k - INTERVAL '6 hours' FROM kickoff) AS t
  UNION ALL SELECT 'T-1h', (SELECT k - INTERVAL '1 hour' FROM kickoff)
  UNION ALL SELECT 'Kickoff', (SELECT k FROM kickoff)
  UNION ALL SELECT 'Mid-match', (SELECT k + INTERVAL '47 min' FROM kickoff)
  UNION ALL SELECT 'Final 15min', (SELECT k + INTERVAL '85 min' FROM kickoff)
)
SELECT p.pt,
       (SELECT d.snapshot_at FROM market_derived_metrics d WHERE d.market_id = :'market_id' ORDER BY ABS(EXTRACT(EPOCH FROM (d.snapshot_at - p.t))) LIMIT 1) AS snapshot_at,
       (SELECT d.home_book_risk_l3 FROM market_derived_metrics d WHERE d.market_id = :'market_id' ORDER BY ABS(EXTRACT(EPOCH FROM (d.snapshot_at - p.t))) LIMIT 1) AS home_br,
       (SELECT d.away_book_risk_l3 FROM market_derived_metrics d WHERE d.market_id = :'market_id' ORDER BY ABS(EXTRACT(EPOCH FROM (d.snapshot_at - p.t))) LIMIT 1) AS away_br,
       (SELECT d.draw_book_risk_l3 FROM market_derived_metrics d WHERE d.market_id = :'market_id' ORDER BY ABS(EXTRACT(EPOCH FROM (d.snapshot_at - p.t))) LIMIT 1) AS draw_br
FROM pts p;

\echo ''
\echo '=== C) Sample: Low liquidity or NULL book_risk ==='
SELECT snapshot_id, snapshot_at,
       home_book_risk_l3, away_book_risk_l3, draw_book_risk_l3,
       home_best_back_size_l1, away_best_back_size_l1, draw_best_back_size_l1
FROM market_derived_metrics
WHERE market_id = :'market_id'
  AND ((home_book_risk_l3 IS NULL OR away_book_risk_l3 IS NULL OR draw_book_risk_l3 IS NULL)
    OR (COALESCE(home_best_back_size_l1,0)+COALESCE(away_best_back_size_l1,0)+COALESCE(draw_best_back_size_l1,0) < 10))
ORDER BY snapshot_at DESC
LIMIT 15;

\echo ''
\echo '=== Raw payload: availableToBack for NULL book_risk snapshots ==='
SELECT m.snapshot_id,
       jsonb_array_length(COALESCE(m.raw_payload->'runners','[]'::jsonb)) AS runners_count,
       (m.raw_payload->'runners'->0->'ex'->'availableToBack') IS NOT NULL AS has_atb,
       jsonb_array_length(COALESCE(m.raw_payload->'runners'->0->'ex'->'availableToBack','[]'::jsonb)) AS atb_levels
FROM market_book_snapshots m
WHERE m.snapshot_id IN (
  SELECT snapshot_id FROM market_derived_metrics
  WHERE market_id = :'market_id' AND (home_book_risk_l3 IS NULL OR away_book_risk_l3 IS NULL OR draw_book_risk_l3 IS NULL)
)
LIMIT 5;

\echo ''
\echo 'REPORT SQL COMPLETE'
