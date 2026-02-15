-- Run as netbet or postgres. Ensure analytics_reader exists and can read public tables.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'netbet_analytics_reader') THEN
    CREATE ROLE netbet_analytics_reader LOGIN PASSWORD 'ANALYTICS_READER_117';
  END IF;
END $$;
ALTER ROLE netbet_analytics_reader WITH PASSWORD 'ANALYTICS_READER_117';
GRANT CONNECT ON DATABASE netbet TO netbet_analytics_reader;
GRANT USAGE ON SCHEMA public TO netbet_analytics_reader;
GRANT SELECT ON public.market_derived_metrics TO netbet_analytics_reader;
GRANT SELECT ON public.market_event_metadata TO netbet_analytics_reader;
