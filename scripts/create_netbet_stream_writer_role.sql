-- Create netbet_stream_writer role if it doesn't exist
-- This role is required for the streaming client to write to stream_ingest schema
-- Run as: cat scripts/create_netbet_stream_writer_role.sql | docker exec -i netbet-postgres psql -U netbet -d netbet

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'netbet_stream_writer') THEN
        CREATE ROLE netbet_stream_writer LOGIN PASSWORD 'STREAM_WRITER_117';
        RAISE NOTICE 'Created role netbet_stream_writer';
    ELSE
        RAISE NOTICE 'Role netbet_stream_writer already exists';
    END IF;
END
$$;

-- Grant necessary privileges (CREATE required for Flyway schema history table)
GRANT USAGE, CREATE ON SCHEMA stream_ingest TO netbet_stream_writer;
GRANT INSERT, SELECT, UPDATE ON ALL TABLES IN SCHEMA stream_ingest TO netbet_stream_writer;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO netbet_stream_writer;

-- Grant privileges on future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA stream_ingest GRANT INSERT, SELECT, UPDATE ON TABLES TO netbet_stream_writer;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE ON TABLES TO netbet_stream_writer;

-- Verify role exists
SELECT rolname, rolcanlogin, rolcreaterole, rolcreatedb 
FROM pg_roles 
WHERE rolname = 'netbet_stream_writer';
