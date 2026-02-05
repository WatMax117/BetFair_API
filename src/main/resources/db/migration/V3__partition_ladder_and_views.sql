-- NetBet Betfair Streaming – Scale & Reliability: partition ladder_levels by publish_time, analytical views.
-- V3: Re-create ladder_levels as partitioned table; initial partition; v_market_top_prices and v_event_summary.

-- ---------------------------------------------------------------------------
-- 1) Re-create ladder_levels as partitioned table (RANGE on publish_time)
-- ---------------------------------------------------------------------------
ALTER TABLE ladder_levels RENAME TO ladder_levels_old;

CREATE TABLE ladder_levels (
    market_id     VARCHAR(32)  NOT NULL,
    selection_id  BIGINT       NOT NULL,
    side          CHAR(1)      NOT NULL CHECK (side IN ('B', 'L')),
    level         SMALLINT     NOT NULL CHECK (level >= 0 AND level <= 7),
    price         DOUBLE PRECISION NOT NULL,
    size          DOUBLE PRECISION NOT NULL,
    publish_time  TIMESTAMPTZ  NOT NULL,
    received_time TIMESTAMPTZ   NOT NULL,
    PRIMARY KEY (market_id, selection_id, side, level, publish_time)
) PARTITION BY RANGE (publish_time);

-- Initial partition: everything up to the start of the current day (UTC). No monthly partition.
-- Run scripts/manage_partitions.sql to create daily partitions from today onwards (no overlap).
DO $$
DECLARE
    today_start timestamptz := ((CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date::timestamp AT TIME ZONE 'UTC');
BEGIN
    EXECUTE format(
        'CREATE TABLE ladder_levels_initial PARTITION OF ladder_levels FOR VALUES FROM (%L) TO (%L)',
        '2020-01-01 00:00:00+00',
        today_start
    );
END
$$;

INSERT INTO ladder_levels SELECT * FROM ladder_levels_old;
DROP TABLE ladder_levels_old;

CREATE INDEX idx_ladder_market_selection_time ON ladder_levels(market_id, selection_id, publish_time DESC);

-- ---------------------------------------------------------------------------
-- 2) Analytical view: best Back/Lay (level 0) per runner per snapshot
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_market_top_prices AS
SELECT
    market_id,
    selection_id,
    publish_time,
    received_time,
    MAX(CASE WHEN side = 'B' AND level = 0 THEN price END) AS best_back_price,
    MAX(CASE WHEN side = 'B' AND level = 0 THEN size END)   AS best_back_size,
    MAX(CASE WHEN side = 'L' AND level = 0 THEN price END) AS best_lay_price,
    MAX(CASE WHEN side = 'L' AND level = 0 THEN size END)   AS best_lay_size
FROM ladder_levels
GROUP BY market_id, selection_id, publish_time, received_time;

-- ---------------------------------------------------------------------------
-- 3) Analytical view: events with all 5 target markets side-by-side
--    DISTINCT ON per (event_id, market_type) picks primary market (earliest market_start_time, then market_id ASC tie-breaker).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_event_summary AS
SELECT
    e.event_id,
    e.event_name,
    e.home_team,
    e.away_team,
    m1.market_id   AS match_odds_market_id,
    m1.market_name AS match_odds_market_name,
    m2.market_id   AS over_under_25_market_id,
    m2.market_name AS over_under_25_market_name,
    m3.market_id   AS half_time_market_id,
    m3.market_name AS half_time_market_name,
    m4.market_id   AS over_under_05_ht_market_id,
    m4.market_name AS over_under_05_ht_market_name,
    m5.market_id   AS next_goal_market_id,
    m5.market_name AS next_goal_market_name
FROM events e
LEFT JOIN (
    SELECT DISTINCT ON (event_id) event_id, market_id, market_name
    FROM markets WHERE market_type = 'MATCH_ODDS_FT'
    ORDER BY event_id, market_start_time ASC NULLS LAST, market_id ASC
) m1 ON m1.event_id = e.event_id
LEFT JOIN (
    SELECT DISTINCT ON (event_id) event_id, market_id, market_name
    FROM markets WHERE market_type = 'OVER_UNDER_25_FT'
    ORDER BY event_id, market_start_time ASC NULLS LAST, market_id ASC
) m2 ON m2.event_id = e.event_id
LEFT JOIN (
    SELECT DISTINCT ON (event_id) event_id, market_id, market_name
    FROM markets WHERE market_type = 'HALF_TIME_RESULT'
    ORDER BY event_id, market_start_time ASC NULLS LAST, market_id ASC
) m3 ON m3.event_id = e.event_id
LEFT JOIN (
    SELECT DISTINCT ON (event_id) event_id, market_id, market_name
    FROM markets WHERE market_type = 'OVER_UNDER_05_HT'
    ORDER BY event_id, market_start_time ASC NULLS LAST, market_id ASC
) m4 ON m4.event_id = e.event_id
LEFT JOIN (
    SELECT DISTINCT ON (event_id) event_id, market_id, market_name
    FROM markets WHERE market_type = 'NEXT_GOAL'
    ORDER BY event_id, market_start_time ASC NULLS LAST, market_id ASC
) m5 ON m5.event_id = e.event_id;
