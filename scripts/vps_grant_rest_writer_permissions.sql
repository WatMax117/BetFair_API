-- Grant permissions to netbet_rest_writer for public schema
-- Run: docker exec -i netbet-postgres psql -U netbet -d netbet < scripts/vps_grant_rest_writer_permissions.sql

-- Grant usage on schema
GRANT USAGE ON SCHEMA public TO netbet_rest_writer;

-- Grant all privileges on existing tables
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO netbet_rest_writer;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO netbet_rest_writer;

-- Grant privileges on future tables/sequences
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO netbet_rest_writer;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON SEQUENCES TO netbet_rest_writer;

-- Verify permissions
SELECT grantee, privilege_type, table_schema, table_name 
FROM information_schema.role_table_grants 
WHERE grantee = 'netbet_rest_writer' 
  AND table_schema = 'public'
  AND table_name IN ('market_event_metadata', 'market_book_snapshots', 'market_derived_metrics')
ORDER BY table_name, privilege_type;
