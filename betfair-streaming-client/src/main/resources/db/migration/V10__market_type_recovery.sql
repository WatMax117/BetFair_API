-- V10: Recovery when stream MCMs arrive without marketDefinition.
-- Persisted market type cache (REST or rest_markets) so we can resolve type and persist ladder/liquidity.
-- Quarantine table for snapshots that cannot be typed after recovery (async retry / alerting).

-- Resolved market type from stream definition, REST recovery, or rest_markets. Source: 'stream' | 'rest' | 'rest_markets'.
CREATE TABLE IF NOT EXISTS market_type_cache (
    market_id     VARCHAR(32) PRIMARY KEY,
    market_type   VARCHAR(64) NOT NULL,
    source        VARCHAR(16) NOT NULL DEFAULT 'rest',
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_market_type_cache_updated_at ON market_type_cache(updated_at);

-- Quarantine: snapshots we could not type after recovery (reason=MISSING_DEFINITION). Optional async retry.
CREATE TABLE IF NOT EXISTS untyped_snapshots (
    id            BIGSERIAL PRIMARY KEY,
    market_id     VARCHAR(32) NOT NULL,
    publish_time  TIMESTAMPTZ NOT NULL,
    received_time TIMESTAMPTZ NOT NULL,
    reason        VARCHAR(32) NOT NULL DEFAULT 'MISSING_DEFINITION',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_untyped_snapshots_market_id ON untyped_snapshots(market_id);
CREATE INDEX IF NOT EXISTS idx_untyped_snapshots_created_at ON untyped_snapshots(created_at);
