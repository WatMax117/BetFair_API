-- Layer 1: Raw REST snapshots (from listMarketBook).
-- Depends on market_event_metadata. Run after create_market_event_metadata.sql.

CREATE TABLE IF NOT EXISTS market_book_snapshots (
    snapshot_id BIGSERIAL PRIMARY KEY,
    snapshot_at TIMESTAMPTZ NOT NULL,
    market_id TEXT NOT NULL REFERENCES market_event_metadata(market_id) ON DELETE CASCADE,
    raw_payload JSONB NOT NULL,
    total_matched DOUBLE PRECISION NULL,
    inplay BOOLEAN NULL,
    status TEXT NULL,
    depth_limit INTEGER NULL,
    source TEXT NOT NULL DEFAULT 'rest_listMarketBook',
    capture_version TEXT NULL DEFAULT 'v1'
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_mbs_market_snapshot_unique ON market_book_snapshots (market_id, snapshot_at);
CREATE INDEX IF NOT EXISTS idx_mbs_market_id ON market_book_snapshots (market_id);
CREATE INDEX IF NOT EXISTS idx_mbs_snapshot_at ON market_book_snapshots (snapshot_at);
