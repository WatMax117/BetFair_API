-- V5: markets segment + total_matched; market_liquidity_history; analytical audit view.

-- ---------------------------------------------------------------------------
-- 1) markets: add segment (VARCHAR) and total_matched (NUMERIC)
-- ---------------------------------------------------------------------------
ALTER TABLE markets
    ADD COLUMN IF NOT EXISTS segment VARCHAR(32),
    ADD COLUMN IF NOT EXISTS total_matched NUMERIC(20, 2);

-- ---------------------------------------------------------------------------
-- 2) market_liquidity_history: 1:1 with Betfair snapshots (no ladder bloat)
--    Primary: totalMatched from marketDefinition; max_runner_ltp from LTP.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS market_liquidity_history (
    market_id          VARCHAR(32)  NOT NULL,
    publish_time       TIMESTAMPTZ  NOT NULL,
    total_matched      NUMERIC(20, 2) NOT NULL DEFAULT 0,
    max_runner_ltp     NUMERIC(10, 2),
    PRIMARY KEY (market_id, publish_time)
);

CREATE INDEX IF NOT EXISTS idx_market_liquidity_history_market_id ON market_liquidity_history(market_id);
CREATE INDEX IF NOT EXISTS idx_market_liquidity_history_publish_time ON market_liquidity_history(publish_time DESC);

-- ---------------------------------------------------------------------------
-- 3) Golden audit view: CTE aggregates ladder per market first to avoid join multiplication.
--    total_ladder_rows      = sum of ladder row counts per market (no inflation).
--    total_distinct_snapshots = sum of distinct (publish_time, received_time) counts per market.
--    current_volume         = sum of m.total_matched once per market (matches Betfair totalMatched).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_golden_audit AS
WITH market_stats AS (
    SELECT
        market_id,
        COUNT(*) AS total_ladder_rows,
        COUNT(DISTINCT (publish_time, received_time)) AS distinct_snapshots
    FROM ladder_levels
    GROUP BY market_id
)
SELECT
    e.event_name,
    m.segment,
    SUM(ms.total_ladder_rows) AS total_ladder_rows,
    SUM(ms.distinct_snapshots) AS total_distinct_snapshots,
    SUM(m.total_matched) AS current_volume
FROM events e
JOIN markets m ON e.event_id = m.event_id
JOIN market_stats ms ON m.market_id = ms.market_id
GROUP BY e.event_name, m.segment;
