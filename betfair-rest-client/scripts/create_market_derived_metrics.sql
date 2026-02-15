-- Layer 2: Derived metrics (computed from Layer 1 raw + metadata mapping).
-- Depends on market_book_snapshots. Run after create_market_book_snapshots.sql.

-- Imbalance and Impedance indices removed (MVP simplification).
CREATE TABLE IF NOT EXISTS market_derived_metrics (
    snapshot_id BIGINT PRIMARY KEY REFERENCES market_book_snapshots(snapshot_id) ON DELETE CASCADE,
    snapshot_at TIMESTAMPTZ NOT NULL,
    market_id TEXT NOT NULL,
    total_volume DOUBLE PRECISION NOT NULL,
    home_best_back DOUBLE PRECISION NULL,
    away_best_back DOUBLE PRECISION NULL,
    draw_best_back DOUBLE PRECISION NULL,
    home_best_lay DOUBLE PRECISION NULL,
    away_best_lay DOUBLE PRECISION NULL,
    draw_best_lay DOUBLE PRECISION NULL,
    home_spread DOUBLE PRECISION NULL,
    away_spread DOUBLE PRECISION NULL,
    draw_spread DOUBLE PRECISION NULL,
    depth_limit INTEGER NULL,
    calculation_version TEXT NULL DEFAULT 'v1'
);

CREATE INDEX IF NOT EXISTS idx_mdm_market_snapshot ON market_derived_metrics (market_id, snapshot_at);
