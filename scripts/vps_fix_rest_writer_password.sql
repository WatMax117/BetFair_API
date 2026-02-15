-- Run as netbet (or postgres). Ensure rest_writer exists and can read/update public tables for backfill.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'netbet_rest_writer') THEN
    CREATE ROLE netbet_rest_writer LOGIN PASSWORD 'REST_WRITER_117';
  END IF;
END $$;
ALTER ROLE netbet_rest_writer WITH PASSWORD 'REST_WRITER_117';
GRANT CONNECT ON DATABASE netbet TO netbet_rest_writer;
GRANT USAGE ON SCHEMA public TO netbet_rest_writer;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.market_book_snapshots TO netbet_rest_writer;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.market_derived_metrics TO netbet_rest_writer;
GRANT SELECT ON public.market_event_metadata TO netbet_rest_writer;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO netbet_rest_writer;
