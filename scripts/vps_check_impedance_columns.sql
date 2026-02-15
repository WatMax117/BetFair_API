-- Check if impedance input columns exist
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'market_derived_metrics'
  AND (column_name LIKE '%back_stake%' OR column_name LIKE '%back_odds%' 
       OR column_name LIKE '%lay_stake%' OR column_name LIKE '%lay_odds%'
       OR column_name LIKE '%impedance%')
ORDER BY column_name;

-- Sample query to see what columns we have
SELECT snapshot_at, home_impedance, away_impedance, draw_impedance
FROM market_derived_metrics
ORDER BY snapshot_at DESC
LIMIT 5;
