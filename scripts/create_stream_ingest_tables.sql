-- Create traded_volume and market_lifecycle_events tables in stream_ingest schema
-- These tables are referenced by the streaming client but don't exist in stream_ingest
-- Run as: cat scripts/create_stream_ingest_tables.sql | docker exec -i netbet-postgres psql -U netbet -d netbet

-- Create traded_volume table in stream_ingest schema
CREATE TABLE IF NOT EXISTS stream_ingest.traded_volume (
    market_id     VARCHAR(32)  NOT NULL,
    selection_id  BIGINT       NOT NULL,
    price         DOUBLE PRECISION NOT NULL,
    size_traded   DOUBLE PRECISION NOT NULL,
    publish_time  TIMESTAMPTZ  NOT NULL,
    received_time TIMESTAMPTZ  NOT NULL,
    PRIMARY KEY (market_id, selection_id, price, publish_time)
);

CREATE INDEX IF NOT EXISTS idx_traded_volume_market_time ON stream_ingest.traded_volume(market_id, selection_id, publish_time DESC);

-- Create market_lifecycle_events table in stream_ingest schema
CREATE TABLE IF NOT EXISTS stream_ingest.market_lifecycle_events (
    market_id     VARCHAR(32)  NOT NULL,
    status        VARCHAR(32),
    in_play       BOOLEAN,
    publish_time  TIMESTAMPTZ  NOT NULL,
    received_time TIMESTAMPTZ  NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_lifecycle_market_time ON stream_ingest.market_lifecycle_events(market_id, publish_time DESC);

-- Verify tables created
SELECT tablename FROM pg_tables WHERE schemaname = 'stream_ingest' AND tablename IN ('traded_volume', 'market_lifecycle_events') ORDER BY tablename;
