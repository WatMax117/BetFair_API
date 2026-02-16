-- Part 1: Database topology and table investigation (VPS)
-- Run: docker exec -i netbet-postgres psql -U netbet -d netbet -f - < scripts/investigate_vps_topology.sql

\echo '=== 1. Databases on this instance (\l equivalent) ==='
SELECT datname, datallowconn FROM pg_database WHERE datistemplate = false ORDER BY datname;

\echo ''
\echo '=== 2. stream_ingest.ladder_levels: relkind, owner, row count, publish_time range ==='
SELECT
    c.relkind,
    c.relname,
    pg_catalog.pg_get_userbyid(c.relowner) AS table_owner
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'stream_ingest' AND c.relname = 'ladder_levels';

SELECT COUNT(*) AS row_count FROM stream_ingest.ladder_levels;
SELECT MIN(publish_time) AS min_publish_time, MAX(publish_time) AS max_publish_time FROM stream_ingest.ladder_levels;

\echo ''
\echo '=== 3. Flyway schema history table location ==='
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_name = 'flyway_schema_history';

\echo ''
\echo '=== 4. Flyway history (public) - skip if relation does not exist ==='
SELECT installed_rank, version, description, script, installed_on, success
FROM public.flyway_schema_history
ORDER BY installed_rank;
