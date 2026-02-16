SELECT tablename
FROM pg_tables
WHERE schemaname = 'stream_ingest'
  AND tablename LIKE 'ladder_levels%'
ORDER BY tablename;
