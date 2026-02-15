SELECT column_name
FROM information_schema.columns
WHERE table_name = 'market_derived_metrics'
  AND column_name IN (
    'home_impedance','away_impedance','draw_impedance',
    'home_impedance_norm','away_impedance_norm','draw_impedance_norm'
  )
ORDER BY column_name;
