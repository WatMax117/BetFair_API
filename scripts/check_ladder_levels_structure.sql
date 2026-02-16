-- Check if ladder_levels is partitioned
SELECT 
    c.relkind,
    c.relname,
    CASE WHEN c.relkind = 'p' THEN 'partitioned table'
         WHEN c.relkind = 'r' THEN 'regular table'
         ELSE 'other'
    END AS table_type,
    (SELECT COUNT(*) FROM pg_inherits WHERE inhparent = c.oid) AS partition_count
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'stream_ingest' AND c.relname = 'ladder_levels';
