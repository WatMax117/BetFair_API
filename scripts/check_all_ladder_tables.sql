SELECT schemaname, tablename, relkind
FROM pg_tables t
JOIN pg_class c ON c.relname = t.tablename AND c.relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = t.schemaname)
WHERE tablename = 'ladder_levels'
ORDER BY schemaname;
