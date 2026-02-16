-- Grant partition provisioning permissions to netbet user (Variant A).
-- Run as superuser or DB owner (e.g. postgres role).
-- Usage: psql -U postgres -d netbet -f scripts/grant_partition_permissions_netbet.sql
-- Or: docker exec -i netbet-postgres psql -U postgres -d netbet -f -

-- Ensure netbet role exists (if not already created)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'netbet') THEN
        CREATE ROLE netbet LOGIN PASSWORD 'CHANGE_ME';
        RAISE NOTICE 'Created role netbet (password must be set via ALTER ROLE)';
    END IF;
END
$$;

-- Grant CREATE on schema stream_ingest (required to create partition tables)
GRANT CREATE ON SCHEMA stream_ingest TO netbet;

-- IMPORTANT: In PostgreSQL, only the table OWNER can create partitions.
-- Therefore, we must transfer ownership to netbet for partition provisioning to work.
-- 
-- Check current owner:
SELECT 
    schemaname,
    tablename,
    tableowner AS current_owner
FROM pg_tables
WHERE schemaname = 'stream_ingest' AND tablename = 'ladder_levels';

-- Transfer ownership to netbet (required for partition creation)
ALTER TABLE stream_ingest.ladder_levels OWNER TO netbet;

-- Grant ALTER on parent table (redundant after ownership transfer, but explicit)
GRANT ALTER ON TABLE stream_ingest.ladder_levels TO netbet;

-- Verify permissions
SELECT 
    schemaname,
    tablename,
    tableowner,
    has_schema_privilege('netbet', 'stream_ingest', 'CREATE') AS can_create_in_schema,
    has_table_privilege('netbet', 'stream_ingest.ladder_levels', 'ALTER') AS can_alter_table
FROM pg_tables
WHERE schemaname = 'stream_ingest' AND tablename = 'ladder_levels';
