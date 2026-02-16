-- 002_stream_ingest_schema_vps.sql
-- Unify VPS with dev: ensure stream_ingest schema and tables exist.
-- Idempotent: safe to run multiple times. Run as DB owner (netbet) or superuser.
-- If ladder_levels / market_liquidity_history exist in public (or other schema), copies data into stream_ingest.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Schema
-- ---------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS stream_ingest;

-- ---------------------------------------------------------------------------
-- 2. Tables (canonical layout from betfair-streaming-client V1 + V5)
-- ---------------------------------------------------------------------------

-- ladder_levels: top-8 ladder snapshots (append-only). Non-partitioned for portability.
CREATE TABLE IF NOT EXISTS stream_ingest.ladder_levels (
    market_id     VARCHAR(32)  NOT NULL,
    selection_id  BIGINT       NOT NULL,
    side          CHAR(1)      NOT NULL CHECK (side IN ('B', 'L')),
    level         SMALLINT     NOT NULL CHECK (level >= 0 AND level <= 7),
    price         DOUBLE PRECISION NOT NULL,
    size          DOUBLE PRECISION NOT NULL,
    publish_time  TIMESTAMPTZ  NOT NULL,
    received_time TIMESTAMPTZ  NOT NULL,
    PRIMARY KEY (market_id, selection_id, side, level, publish_time)
);

CREATE INDEX IF NOT EXISTS idx_stream_ladder_market_selection_time
  ON stream_ingest.ladder_levels(market_id, selection_id, publish_time DESC);

-- market_liquidity_history: totalMatched per snapshot
CREATE TABLE IF NOT EXISTS stream_ingest.market_liquidity_history (
    market_id     VARCHAR(32)  NOT NULL,
    publish_time  TIMESTAMPTZ  NOT NULL,
    total_matched NUMERIC(20, 2) NOT NULL DEFAULT 0,
    max_runner_ltp NUMERIC(10, 2),
    PRIMARY KEY (market_id, publish_time)
);

CREATE INDEX IF NOT EXISTS idx_stream_liquidity_market_id
  ON stream_ingest.market_liquidity_history(market_id);
CREATE INDEX IF NOT EXISTS idx_stream_liquidity_publish_time
  ON stream_ingest.market_liquidity_history(publish_time DESC);

-- ---------------------------------------------------------------------------
-- 3. Data migration: copy from public if source tables exist (VPS may have data there)
--    Only inserts rows that do not already exist (by primary key).
-- ---------------------------------------------------------------------------

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'ladder_levels') THEN
    INSERT INTO stream_ingest.ladder_levels (
        market_id, selection_id, side, level, price, size, publish_time, received_time
    )
    SELECT market_id, selection_id, side, level, price, size, publish_time, received_time
    FROM public.ladder_levels
    ON CONFLICT (market_id, selection_id, side, level, publish_time) DO NOTHING;
  END IF;
END
$$;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'market_liquidity_history') THEN
    INSERT INTO stream_ingest.market_liquidity_history (market_id, publish_time, total_matched, max_runner_ltp)
    SELECT market_id, publish_time, total_matched, max_runner_ltp
    FROM public.market_liquidity_history
    ON CONFLICT (market_id, publish_time) DO NOTHING;
  END IF;
END
$$;

-- ---------------------------------------------------------------------------
-- 4. Grants so Risk Analytics API (netbet_analytics_reader) can read stream_ingest
-- ---------------------------------------------------------------------------
GRANT USAGE ON SCHEMA stream_ingest TO netbet_analytics_reader;
GRANT SELECT ON stream_ingest.ladder_levels TO netbet_analytics_reader;
GRANT SELECT ON stream_ingest.market_liquidity_history TO netbet_analytics_reader;

-- Future tables in stream_ingest (if netbet creates them) – analytics_reader can read
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'netbet') THEN
    ALTER DEFAULT PRIVILEGES FOR ROLE netbet IN SCHEMA stream_ingest
      GRANT SELECT ON TABLES TO netbet_analytics_reader;
  END IF;
END
$$;

COMMIT;
