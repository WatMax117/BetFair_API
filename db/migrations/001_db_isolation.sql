-- 001_db_isolation.sql
-- Minimal but robust logical isolation inside single PostgreSQL DB.
-- Run as the DB owner role (typically "netbet") or a superuser.
-- This script is idempotent and safe to apply multiple times.

BEGIN;

-- =============================================================================
-- 1. Schemas
-- =============================================================================

-- Application schemas for logical separation
CREATE SCHEMA IF NOT EXISTS rest_ingest AUTHORIZATION netbet;
CREATE SCHEMA IF NOT EXISTS stream_ingest AUTHORIZATION netbet;
CREATE SCHEMA IF NOT EXISTS analytics AUTHORIZATION netbet;

-- Lock down public: no application tables should live here.
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM PUBLIC;

-- Keep owner (netbet) able to use public if needed (extensions, etc.)
GRANT USAGE ON SCHEMA public TO netbet;


-- =============================================================================
-- 2. Roles (no passwords embedded)
-- =============================================================================
-- Passwords should be set out-of-band via ALTER ROLE, using secrets
-- or environment variables (see DB_ARCHITECTURE.md).

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'netbet_rest_writer') THEN
    CREATE ROLE netbet_rest_writer LOGIN;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'netbet_stream_writer') THEN
    CREATE ROLE netbet_stream_writer LOGIN;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'netbet_analytics_reader') THEN
    CREATE ROLE netbet_analytics_reader LOGIN;
  END IF;
END
$$;


-- =============================================================================
-- 3. Database-level access & search_path
-- =============================================================================

-- Allow roles to connect to the main application database.
GRANT CONNECT ON DATABASE netbet TO
  netbet_rest_writer,
  netbet_stream_writer,
  netbet_analytics_reader;

-- Optional: allow temporary tables
GRANT TEMPORARY ON DATABASE netbet TO
  netbet_rest_writer,
  netbet_stream_writer,
  netbet_analytics_reader;

-- Explicit search_path for each role (defensive; apps also set search_path).
ALTER ROLE netbet_rest_writer SET search_path = rest_ingest;
ALTER ROLE netbet_stream_writer SET search_path = stream_ingest;
ALTER ROLE netbet_analytics_reader SET search_path = analytics;


-- =============================================================================
-- 4. Schema-level privileges (least privilege)
-- =============================================================================

-- REST writer: only rest_ingest
GRANT USAGE, CREATE ON SCHEMA rest_ingest TO netbet_rest_writer;
REVOKE ALL ON SCHEMA rest_ingest FROM PUBLIC;

-- Streaming writer: only stream_ingest
GRANT USAGE, CREATE ON SCHEMA stream_ingest TO netbet_stream_writer;
REVOKE ALL ON SCHEMA stream_ingest FROM PUBLIC;

-- Analytics reader: read-only on analytics schema only
GRANT USAGE ON SCHEMA analytics TO netbet_analytics_reader;
REVOKE ALL ON SCHEMA analytics FROM PUBLIC;

-- Ensure writers CANNOT create objects outside their schema:
REVOKE CREATE ON SCHEMA public FROM netbet_rest_writer;
REVOKE CREATE ON SCHEMA public FROM netbet_stream_writer;
REVOKE CREATE ON SCHEMA analytics FROM netbet_rest_writer;
REVOKE CREATE ON SCHEMA analytics FROM netbet_stream_writer;

-- Ensure analytics role cannot write anywhere
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA rest_ingest FROM netbet_analytics_reader;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA stream_ingest FROM netbet_analytics_reader;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA analytics FROM netbet_analytics_reader;


-- =============================================================================
-- 5. Existing objects: baseline grants (idempotent)
-- =============================================================================
-- NOTE: These apply once objects have been moved into the target schemas.

-- REST writer needs full DML on rest_ingest objects
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA rest_ingest TO netbet_rest_writer;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA rest_ingest TO netbet_rest_writer;

-- Streaming writer needs full DML on stream_ingest objects
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA stream_ingest TO netbet_stream_writer;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA stream_ingest TO netbet_stream_writer;

-- Analytics reader: read-only on analytics objects
GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO netbet_analytics_reader;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA analytics TO netbet_analytics_reader;


-- =============================================================================
-- 6. Default privileges for future objects
-- =============================================================================
-- These ALTER DEFAULT PRIVILEGES statements must be run by the role that owns
-- future objects (here assumed to be "netbet"). Because this script should be
-- executed as netbet (or superuser SET ROLE netbet), these take effect.

-- When owner "netbet" creates tables/sequences in rest_ingest, automatically
-- grant DML to netbet_rest_writer.
ALTER DEFAULT PRIVILEGES FOR ROLE netbet IN SCHEMA rest_ingest
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO netbet_rest_writer;

ALTER DEFAULT PRIVILEGES FOR ROLE netbet IN SCHEMA rest_ingest
  GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO netbet_rest_writer;

-- When owner "netbet" creates tables/sequences in stream_ingest, automatically
-- grant DML to netbet_stream_writer.
ALTER DEFAULT PRIVILEGES FOR ROLE netbet IN SCHEMA stream_ingest
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO netbet_stream_writer;

ALTER DEFAULT PRIVILEGES FOR ROLE netbet IN SCHEMA stream_ingest
  GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO netbet_stream_writer;

-- When owner "netbet" creates tables/sequences in analytics, automatically
-- grant read-only access to netbet_analytics_reader.
ALTER DEFAULT PRIVILEGES FOR ROLE netbet IN SCHEMA analytics
  GRANT SELECT ON TABLES TO netbet_analytics_reader;

ALTER DEFAULT PRIVILEGES FOR ROLE netbet IN SCHEMA analytics
  GRANT SELECT ON SEQUENCES TO netbet_analytics_reader;

COMMIT;

