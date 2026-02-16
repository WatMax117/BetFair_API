-- List all child partitions of ladder_levels
SELECT 
    c.relname AS partition_name,
    pg_get_expr(c.relpartbound, c.oid) AS partition_bound
FROM pg_inherits i
JOIN pg_class p ON p.oid = i.inhparent
JOIN pg_class c ON c.oid = i.inhrelid
JOIN pg_namespace n ON n.oid = p.relnamespace
WHERE n.nspname = 'stream_ingest' AND p.relname = 'ladder_levels'
ORDER BY c.relname;
