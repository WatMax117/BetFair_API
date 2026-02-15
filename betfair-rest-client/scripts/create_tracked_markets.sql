-- Sticky pre-match tracking: persistent state across restarts.
-- Run once: psql -U netbet -d netbet -f scripts/create_tracked_markets.sql
-- Or from main.py _ensure_three_layer_tables / _ensure_sticky_tables.

CREATE TABLE IF NOT EXISTS seen_markets (
    market_id TEXT NOT NULL,
    tick_id_first BIGINT NOT NULL,
    tick_id_last BIGINT NOT NULL,
    last_seen_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (market_id)
);

CREATE INDEX IF NOT EXISTS idx_seen_markets_tick_last ON seen_markets (tick_id_last);

CREATE TABLE IF NOT EXISTS tracked_markets (
    market_id TEXT NOT NULL PRIMARY KEY,
    event_id TEXT NULL,
    event_start_time_utc TIMESTAMPTZ NOT NULL,
    admitted_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    admission_score DOUBLE PRECISION NULL,
    state TEXT NOT NULL DEFAULT 'TRACKING' CHECK (state IN ('TRACKING', 'DROPPED')),
    last_polled_at_utc TIMESTAMPTZ NULL,
    last_snapshot_at_utc TIMESTAMPTZ NULL,
    created_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tracked_markets_state ON tracked_markets (state);
CREATE INDEX IF NOT EXISTS idx_tracked_markets_event_start ON tracked_markets (event_start_time_utc);
CREATE INDEX IF NOT EXISTS idx_tracked_markets_last_polled ON tracked_markets (last_polled_at_utc);

COMMENT ON TABLE tracked_markets IS 'Sticky pre-match set: once admitted, kept until kickoff+buffer or invalid. Max K enforced at admission.';
COMMENT ON TABLE seen_markets IS 'Catalogue presence for maturity filter (e.g. 2 consecutive ticks).';
