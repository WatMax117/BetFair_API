-- Check partition coverage for today
SELECT 
    schemaname,
    tablename,
    pg_get_expr(c.relpartbound, c.oid) AS partition_bound
FROM pg_tables t
JOIN pg_class c ON c.relname = t.tablename
JOIN pg_namespace n ON n.nspname = t.schemaname AND n.oid = c.relnamespace
WHERE t.schemaname = 'stream_ingest'
  AND t.tablename LIKE 'ladder_levels%'
  AND c.relkind = 'p'
ORDER BY tablename;

-- Also check if streaming client is writing to the right schema
SELECT current_schema();
