-- Stage 1 validation: market_derived_metrics has impedance columns and recent rows have non-null values.
-- Run on VPS: docker exec -i netbet-postgres psql -U netbet -d netbet -c "\i /path/to/validate_stage1_impedance.sql"
-- Or paste the blocks below into: docker exec -it netbet-postgres psql -U netbet -d netbet
-- If your tables are in public schema, replace rest_ingest with public below.

-- 1) Required impedance columns (expect 6 rows)
SELECT column_name
FROM information_schema.columns
WHERE table_schema = 'rest_ingest'
  AND table_name = 'market_derived_metrics'
  AND column_name IN (
    'home_impedance', 'away_impedance', 'draw_impedance',
    'home_impedance_norm', 'away_impedance_norm', 'draw_impedance_norm'
  )
ORDER BY column_name;

-- 2) Count recent rows with non-null impedance (last 7 days)
SELECT COUNT(*) AS recent_with_impedance
FROM rest_ingest.market_derived_metrics
WHERE snapshot_at >= NOW() - INTERVAL '7 days'
  AND (home_impedance_norm IS NOT NULL OR away_impedance_norm IS NOT NULL OR draw_impedance_norm IS NOT NULL);

-- 3) Sample latest row with impedance
SELECT snapshot_at, market_id,
       home_impedance, away_impedance, draw_impedance,
       home_impedance_norm, away_impedance_norm, draw_impedance_norm
FROM rest_ingest.market_derived_metrics
WHERE home_impedance_norm IS NOT NULL OR away_impedance_norm IS NOT NULL OR draw_impedance_norm IS NOT NULL
ORDER BY snapshot_at DESC
LIMIT 1;
