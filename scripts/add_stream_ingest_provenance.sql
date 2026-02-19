-- Add provenance columns to stream_ingest for attribution and ingestion audit.
-- ingest_source: e.g. 'stream_api' for the new stream API client.
-- client_version: application/build version of the writer.
-- Run as schema owner (netbet). Idempotent (ADD COLUMN IF NOT EXISTS where supported; else use DO block).

BEGIN;

-- PostgreSQL 9.5+ does not have ADD COLUMN IF NOT EXISTS; use DO block for idempotency.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'stream_ingest' AND table_name = 'ladder_levels' AND column_name = 'ingest_source'
  ) THEN
    ALTER TABLE stream_ingest.ladder_levels ADD COLUMN ingest_source VARCHAR(32) NULL;
    COMMENT ON COLUMN stream_ingest.ladder_levels.ingest_source IS 'Source of ingest e.g. stream_api for attribution';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'stream_ingest' AND table_name = 'ladder_levels' AND column_name = 'client_version'
  ) THEN
    ALTER TABLE stream_ingest.ladder_levels ADD COLUMN client_version VARCHAR(64) NULL;
    COMMENT ON COLUMN stream_ingest.ladder_levels.client_version IS 'Writer application version for audit';
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'stream_ingest' AND table_name = 'market_liquidity_history' AND column_name = 'ingest_source'
  ) THEN
    ALTER TABLE stream_ingest.market_liquidity_history ADD COLUMN ingest_source VARCHAR(32) NULL;
    COMMENT ON COLUMN stream_ingest.market_liquidity_history.ingest_source IS 'Source of ingest e.g. stream_api';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'stream_ingest' AND table_name = 'market_liquidity_history' AND column_name = 'client_version'
  ) THEN
    ALTER TABLE stream_ingest.market_liquidity_history ADD COLUMN client_version VARCHAR(64) NULL;
    COMMENT ON COLUMN stream_ingest.market_liquidity_history.client_version IS 'Writer application version for audit';
  END IF;
END $$;

COMMIT;
