-- V11: Winner status capture on market settlement (before unsubscription).
-- Idempotent: INSERT ... ON CONFLICT DO NOTHING. One row per market in market_settlement;
-- one row per (market_id, selection_id) in market_runner_settlement.

CREATE TABLE IF NOT EXISTS market_settlement (
    market_id   VARCHAR(50) PRIMARY KEY,
    settled_at  TIMESTAMPTZ NOT NULL,
    source      VARCHAR(20) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE market_settlement IS 'Settlement timestamp and source (stream|rest). One row per market; idempotent.';

CREATE TABLE IF NOT EXISTS market_runner_settlement (
    market_id      VARCHAR(50) NOT NULL,
    selection_id   BIGINT NOT NULL,
    runner_status  VARCHAR(20) NOT NULL,
    PRIMARY KEY (market_id, selection_id)
);

COMMENT ON TABLE market_runner_settlement IS 'Runner-level outcome: WINNER, LOSER, REMOVED. Idempotent.';

CREATE INDEX IF NOT EXISTS idx_market_settlement_settled_at ON market_settlement (settled_at);
CREATE INDEX IF NOT EXISTS idx_market_settlement_source ON market_settlement (source);
