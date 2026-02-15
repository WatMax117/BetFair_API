-- Post-event data integrity & Book Risk L3 dynamics report
-- Market: 1.253489253 (Lazio v Atalanta)
-- Run: docker exec -i netbet-postgres psql -U netbet -d netbet < scripts/report_lazio_atalanta_market.sql
-- Or: psql -U netbet -d netbet -v market_id=1.253489253 -f scripts/report_lazio_atalanta_market.sql

\set market_id '1.253489253'

\echo '========================================'
\echo 'LAZIO v ATALANTA - MARKET 1.253489253'
\echo 'Post-event Data Integrity & Book Risk L3 Report'
\echo '========================================'
\echo ''

-- Resolve schema: try public first, then rest_ingest
\echo '--- Event metadata (kickoff) ---'
SELECT market_id, event_name, event_open_date, competition_name,
       home_runner_name, away_runner_name, draw_runner_name
FROM (
  SELECT * FROM public.market_event_metadata WHERE market_id = :'market_id'
  UNION ALL
  SELECT * FROM rest_ingest.market_event_metadata WHERE market_id = :'market_id' AND NOT EXISTS (SELECT 1 FROM public.market_event_metadata WHERE market_id = :'market_id')
) x
LIMIT 1;

\echo ''
\echo '=== A1) SNAPSHOT CONTINUITY ==='

WITH dm AS (
  SELECT d.snapshot_id, d.snapshot_at
  FROM public.market_derived_metrics d WHERE d.market_id = :'market_id'
  UNION ALL
  SELECT d.snapshot_id, d.snapshot_at
  FROM rest_ingest.market_derived_metrics d WHERE d.market_id = :'market_id' AND NOT EXISTS (SELECT 1 FROM public.market_derived_metrics WHERE market_id = :'market_id')
),
ordered AS (
  SELECT snapshot_id, snapshot_at,
         LAG(snapshot_at) OVER (ORDER BY snapshot_at) AS prev_at,
         snapshot_at - LAG(snapshot_at) OVER (ORDER BY snapshot_at) AS gap
  FROM (SELECT DISTINCT snapshot_id, snapshot_at FROM dm) u
)
SELECT
  (SELECT COUNT(*) FROM dm) AS total_snapshots,
  (SELECT MIN(snapshot_at) FROM dm) AS min_snapshot_at,
  (SELECT MAX(snapshot_at) FROM dm) AS max_snapshot_at,
  (SELECT AVG(EXTRACT(EPOCH FROM gap)) FROM ordered WHERE gap IS NOT NULL) AS avg_interval_seconds,
  (SELECT COUNT(*) FROM ordered WHERE gap > INTERVAL '15 minutes') AS gaps_over_15min;

\echo ''
\echo '--- A1) Detected time gaps (>15 min) ---'
WITH dm AS (
  SELECT d.snapshot_at FROM public.market_derived_metrics d WHERE d.market_id = :'market_id'
  UNION ALL
  SELECT d.snapshot_at FROM rest_ingest.market_derived_metrics d WHERE d.market_id = :'market_id' AND NOT EXISTS (SELECT 1 FROM public.market_derived_metrics WHERE market_id = :'market_id')
),
ordered AS (
  SELECT snapshot_at AS end_at,
         LAG(snapshot_at) OVER (ORDER BY snapshot_at) AS start_at,
         snapshot_at - LAG(snapshot_at) OVER (ORDER BY snapshot_at) AS gap
  FROM (SELECT DISTINCT snapshot_at FROM dm) u
),
kickoff AS (SELECT COALESCE(
  (SELECT event_open_date FROM public.market_event_metadata WHERE market_id = :'market_id'),
  (SELECT event_open_date FROM rest_ingest.market_event_metadata WHERE market_id = :'market_id')
) AS k)
SELECT
  start_at AS gap_start,
  end_at AS gap_end,
  gap AS duration,
  CASE WHEN o.start_at < k.k AND o.end_at <= k.k THEN 'PRE-KICKOFF' WHEN o.start_at >= k.k THEN 'IN-PLAY' ELSE 'BRIDGE' END AS period
FROM ordered o, kickoff k
WHERE gap > INTERVAL '15 minutes'
ORDER BY start_at;

\echo ''
\echo '=== A2) DERIVED METRICS COMPLETENESS ==='

WITH dm AS (
  SELECT * FROM public.market_derived_metrics WHERE market_id = :'market_id'
  UNION ALL
  SELECT * FROM rest_ingest.market_derived_metrics d WHERE d.market_id = :'market_id' AND NOT EXISTS (SELECT 1 FROM public.market_derived_metrics WHERE market_id = :'market_id')
)
SELECT
  COUNT(*) AS total_snapshots,
  COUNT(CASE WHEN home_book_risk_l3 IS NULL OR away_book_risk_l3 IS NULL OR draw_book_risk_l3 IS NULL THEN 1 END) AS snapshots_with_null_book_risk_l3,
  COUNT(CASE WHEN home_back_odds_l2 IS NULL OR home_back_size_l2 IS NULL THEN 1 END) AS snapshots_missing_home_l2,
  COUNT(CASE WHEN home_back_odds_l3 IS NULL OR home_back_size_l3 IS NULL THEN 1 END) AS snapshots_missing_home_l3,
  COUNT(CASE WHEN total_volume IS NULL THEN 1 END) AS snapshots_null_total_volume
FROM dm;

\echo ''
\echo '=== A3) PRE-MATCH DATA (6h and 1h before kickoff) ==='

WITH kickoff AS (
  SELECT COALESCE(
    (SELECT event_open_date FROM public.market_event_metadata WHERE market_id = :'market_id'),
    (SELECT event_open_date FROM rest_ingest.market_event_metadata WHERE market_id = :'market_id')
  ) AS k
),
dm AS (
  SELECT d.* FROM public.market_derived_metrics d, kickoff k WHERE d.market_id = :'market_id' AND d.snapshot_at >= k.k - INTERVAL '6 hours' AND d.snapshot_at <= k.k
  UNION ALL
  SELECT d.* FROM rest_ingest.market_derived_metrics d, kickoff k
  WHERE d.market_id = :'market_id' AND d.snapshot_at >= k.k - INTERVAL '6 hours' AND d.snapshot_at <= k.k
  AND NOT EXISTS (SELECT 1 FROM public.market_derived_metrics WHERE market_id = :'market_id')
)
SELECT
  COUNT(*) AS pre_match_snapshots_6h_to_kickoff,
  COUNT(CASE WHEN snapshot_at >= (SELECT k - INTERVAL '1 hour' FROM kickoff) AND snapshot_at <= (SELECT k FROM kickoff) THEN 1 END) AS snapshots_last_1h,
  COUNT(CASE WHEN home_book_risk_l3 IS NOT NULL AND away_book_risk_l3 IS NOT NULL AND draw_book_risk_l3 IS NOT NULL THEN 1 END) AS with_full_book_risk_l3,
  COUNT(CASE WHEN home_best_back_size_l1 IS NOT NULL AND home_best_back_size_l1 > 0 THEN 1 END) AS with_l1_liquidity
FROM dm;

\echo ''
\echo '=== A4) SAMPLE: Snapshots with NULL book_risk_l3 (first 10) ==='

WITH dm AS (
  SELECT snapshot_id, snapshot_at, home_book_risk_l3, away_book_risk_l3, draw_book_risk_l3
  FROM public.market_derived_metrics WHERE market_id = :'market_id'
  UNION ALL
  SELECT snapshot_id, snapshot_at, home_book_risk_l3, away_book_risk_l3, draw_book_risk_l3
  FROM rest_ingest.market_derived_metrics d WHERE d.market_id = :'market_id' AND NOT EXISTS (SELECT 1 FROM public.market_derived_metrics WHERE market_id = :'market_id')
)
SELECT snapshot_id, snapshot_at, home_book_risk_l3, away_book_risk_l3, draw_book_risk_l3
FROM dm
WHERE home_book_risk_l3 IS NULL OR away_book_risk_l3 IS NULL OR draw_book_risk_l3 IS NULL
ORDER BY snapshot_at DESC
LIMIT 10;

\echo ''
\echo '=== B) BOOK RISK L3 AT KEY TIME POINTS ==='

WITH kickoff AS (
  SELECT COALESCE(
    (SELECT event_open_date FROM public.market_event_metadata WHERE market_id = :'market_id'),
    (SELECT event_open_date FROM rest_ingest.market_event_metadata WHERE market_id = :'market_id')
  ) AS k
),
dm AS (
  SELECT d.snapshot_at, d.home_book_risk_l3, d.away_book_risk_l3, d.draw_book_risk_l3,
         d.home_risk, d.away_risk, d.draw_risk,
         d.home_impedance, d.away_impedance, d.draw_impedance
  FROM public.market_derived_metrics d WHERE d.market_id = :'market_id'
  UNION ALL
  SELECT d.snapshot_at, d.home_book_risk_l3, d.away_book_risk_l3, d.draw_book_risk_l3,
         d.home_risk, d.away_risk, d.draw_risk,
         d.home_impedance, d.away_impedance, d.draw_impedance
  FROM rest_ingest.market_derived_metrics d WHERE d.market_id = :'market_id' AND NOT EXISTS (SELECT 1 FROM public.market_derived_metrics WHERE market_id = :'market_id')
),
buckets AS (
  SELECT k, 'T-6h' AS bucket, k - INTERVAL '6 hours' AS t0, k - INTERVAL '5 hours 50 minutes' AS t1 FROM kickoff
  UNION ALL SELECT k, 'T-1h', k - INTERVAL '1 hour', k - INTERVAL '50 minutes' FROM kickoff
  UNION ALL SELECT k, 'Kickoff', k - INTERVAL '10 minutes', k + INTERVAL '10 minutes' FROM kickoff
  UNION ALL SELECT k, 'Mid-match', k + INTERVAL '40 minutes', k + INTERVAL '55 minutes' FROM kickoff
  UNION ALL SELECT k, 'Final 15min', k + INTERVAL '75 minutes', k + INTERVAL '95 minutes' FROM kickoff
)
SELECT b.bucket,
       (SELECT d.snapshot_at FROM dm d WHERE d.snapshot_at >= b.t0 AND d.snapshot_at <= b.t1 ORDER BY ABS(EXTRACT(EPOCH FROM (d.snapshot_at - (b.t0 + (b.t1 - b.t0)/2)))) LIMIT 1) AS snapshot_at,
       (SELECT d.home_book_risk_l3 FROM dm d WHERE d.snapshot_at >= b.t0 AND d.snapshot_at <= b.t1 ORDER BY ABS(EXTRACT(EPOCH FROM (d.snapshot_at - (b.t0 + (b.t1 - b.t0)/2)))) LIMIT 1) AS home_book_risk_l3,
       (SELECT d.away_book_risk_l3 FROM dm d WHERE d.snapshot_at >= b.t0 AND d.snapshot_at <= b.t1 ORDER BY ABS(EXTRACT(EPOCH FROM (d.snapshot_at - (b.t0 + (b.t1 - b.t0)/2)))) LIMIT 1) AS away_book_risk_l3,
       (SELECT d.draw_book_risk_l3 FROM dm d WHERE d.snapshot_at >= b.t0 AND d.snapshot_at <= b.t1 ORDER BY ABS(EXTRACT(EPOCH FROM (d.snapshot_at - (b.t0 + (b.t1 - b.t0)/2)))) LIMIT 1) AS draw_book_risk_l3
FROM buckets b;

\echo ''
\echo '--- B) Nearest snapshots to each time bucket (simplified) ---'
WITH kickoff AS (
  SELECT COALESCE(
    (SELECT event_open_date FROM public.market_event_metadata WHERE market_id = :'market_id'),
    (SELECT event_open_date FROM rest_ingest.market_event_metadata WHERE market_id = :'market_id')
  ) AS k
),
dm AS (
  SELECT d.* FROM public.market_derived_metrics d WHERE d.market_id = :'market_id'
  UNION ALL
  SELECT d.* FROM rest_ingest.market_derived_metrics d WHERE d.market_id = :'market_id' AND NOT EXISTS (SELECT 1 FROM public.market_derived_metrics WHERE market_id = :'market_id')
),
pts AS (
  SELECT 'T-6h' AS pt, (SELECT k - INTERVAL '6 hours' FROM kickoff) AS t
  UNION ALL SELECT 'T-1h', (SELECT k - INTERVAL '1 hour' FROM kickoff)
  UNION ALL SELECT 'Kickoff', (SELECT k FROM kickoff)
  UNION ALL SELECT 'Mid-match', (SELECT k + INTERVAL '47 min' FROM kickoff)
  UNION ALL SELECT 'Final 15min', (SELECT k + INTERVAL '85 min' FROM kickoff)
)
SELECT p.pt,
       (SELECT d.snapshot_at FROM dm d ORDER BY ABS(EXTRACT(EPOCH FROM (d.snapshot_at - p.t))) LIMIT 1) AS snapshot_at,
       (SELECT d.home_book_risk_l3 FROM dm d ORDER BY ABS(EXTRACT(EPOCH FROM (d.snapshot_at - p.t))) LIMIT 1) AS home_br,
       (SELECT d.away_book_risk_l3 FROM dm d ORDER BY ABS(EXTRACT(EPOCH FROM (d.snapshot_at - p.t))) LIMIT 1) AS away_br,
       (SELECT d.draw_book_risk_l3 FROM dm d ORDER BY ABS(EXTRACT(EPOCH FROM (d.snapshot_at - p.t))) LIMIT 1) AS draw_br
FROM pts p;

\echo ''
\echo '=== C) SAMPLE: Snapshots with very small L1 size or NULL book_risk ==='

WITH dm AS (
  SELECT d.snapshot_id, d.snapshot_at, d.home_book_risk_l3, d.away_book_risk_l3, d.draw_book_risk_l3,
         d.home_best_back_size_l1, d.away_best_back_size_l1, d.draw_best_back_size_l1
  FROM public.market_derived_metrics d WHERE d.market_id = :'market_id'
  UNION ALL
  SELECT d.snapshot_id, d.snapshot_at, d.home_book_risk_l3, d.away_book_risk_l3, d.draw_book_risk_l3,
         d.home_best_back_size_l1, d.away_best_back_size_l1, d.draw_best_back_size_l1
  FROM rest_ingest.market_derived_metrics d WHERE d.market_id = :'market_id' AND NOT EXISTS (SELECT 1 FROM public.market_derived_metrics WHERE market_id = :'market_id')
)
SELECT snapshot_id, snapshot_at,
       home_book_risk_l3, away_book_risk_l3, draw_book_risk_l3,
       home_best_back_size_l1, away_best_back_size_l1, draw_best_back_size_l1
FROM dm
WHERE (home_book_risk_l3 IS NULL OR away_book_risk_l3 IS NULL OR draw_book_risk_l3 IS NULL)
   OR (COALESCE(home_best_back_size_l1, 0) + COALESCE(away_best_back_size_l1, 0) + COALESCE(draw_best_back_size_l1, 0) < 10)
ORDER BY snapshot_at DESC
LIMIT 15;

\echo ''
\echo '=== RAW PAYLOAD: availableToBack check for NULL book_risk snapshots ==='

WITH null_br AS (
  SELECT d.snapshot_id FROM public.market_derived_metrics d
  WHERE d.market_id = :'market_id' AND (d.home_book_risk_l3 IS NULL OR d.away_book_risk_l3 IS NULL OR d.draw_book_risk_l3 IS NULL)
  UNION
  SELECT d.snapshot_id FROM rest_ingest.market_derived_metrics d
  WHERE d.market_id = :'market_id' AND (d.home_book_risk_l3 IS NULL OR d.away_book_risk_l3 IS NULL OR d.draw_book_risk_l3 IS NULL)
  AND NOT EXISTS (SELECT 1 FROM public.market_derived_metrics WHERE market_id = :'market_id')
),
mbs AS (
  SELECT m.snapshot_id, m.raw_payload FROM public.market_book_snapshots m WHERE m.snapshot_id IN (SELECT snapshot_id FROM null_br)
  UNION ALL
  SELECT m.snapshot_id, m.raw_payload FROM rest_ingest.market_book_snapshots m WHERE m.snapshot_id IN (SELECT snapshot_id FROM null_br) AND NOT EXISTS (SELECT 1 FROM public.market_book_snapshots WHERE snapshot_id = m.snapshot_id)
)
SELECT m.snapshot_id,
       jsonb_array_length(COALESCE(raw_payload->'runners','[]'::jsonb)) AS runners_count,
       (raw_payload->'runners'->0->'ex'->'availableToBack') IS NOT NULL AS has_atb,
       jsonb_array_length(COALESCE(raw_payload->'runners'->0->'ex'->'availableToBack','[]'::jsonb)) AS atb_levels
FROM mbs
LIMIT 5;

\echo ''
\echo '========================================'
\echo 'REPORT SQL COMPLETE'
\echo '========================================'
