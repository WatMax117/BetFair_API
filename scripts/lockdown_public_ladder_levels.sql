-- Lock down public.ladder_levels: revoke write privileges from streaming client user.
-- Prevents accidental writes to public.ladder_levels after streaming client fix.
-- Run as DB owner (netbet) or superuser.
-- Usage: cat scripts/lockdown_public_ladder_levels.sql | docker exec -i netbet-postgres psql -U netbet -d netbet -v ON_ERROR_STOP=1

BEGIN;

-- Revoke INSERT, UPDATE, DELETE, TRUNCATE on public.ladder_levels from streaming writer
-- (Keep SELECT for any reads that might still reference it)
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.ladder_levels FROM netbet_stream_writer;

-- Also revoke from any other roles that might have write access
-- (Adjust role names if different on your system)
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN 
        SELECT rolname FROM pg_roles 
        WHERE rolname IN ('netbet_stream_writer', 'netbet', 'postgres')
    LOOP
        EXECUTE format('REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.ladder_levels FROM %I', r.rolname);
    END LOOP;
END
$$;

-- Verify: show current privileges on public.ladder_levels
SELECT 
    grantee,
    privilege_type
FROM information_schema.table_privileges
WHERE table_schema = 'public' 
  AND table_name = 'ladder_levels'
  AND privilege_type IN ('INSERT', 'UPDATE', 'DELETE', 'TRUNCATE')
ORDER BY grantee, privilege_type;

COMMIT;

-- Note: If verification shows INSERT/UPDATE/DELETE/TRUNCATE still granted, investigate further.
-- The streaming client should only have SELECT (if needed) and full privileges on stream_ingest.ladder_levels.
