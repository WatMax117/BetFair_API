SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_name = 'market_derived_metrics'
ORDER BY table_schema;
