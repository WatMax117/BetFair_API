-- NetBet Betfair Streaming – Production refinements (constraints and indexes)
-- V2: Final database integration phase.
-- Self-healing CTE dedup; traded_volume PK; lifecycle unique (market_id, publish_time, status, in_play); index on markets(event_id).

-- ---------------------------------------------------------------------------
-- 1) Self-healing: remove duplicate rows before adding constraints
--    DELETE ... WHERE ctid IN (...) keeps one row per key (latest received_time).
-- ---------------------------------------------------------------------------

-- traded_volume: keep one row per (market_id, selection_id, price, publish_time)
DELETE FROM traded_volume
WHERE ctid IN (
    SELECT ctid FROM (
        SELECT ctid,
               ROW_NUMBER() OVER (
                   PARTITION BY market_id, selection_id, price, publish_time
                   ORDER BY received_time DESC NULLS LAST
               ) AS rn
        FROM traded_volume
    ) ranked
    WHERE ranked.rn > 1
);

-- market_lifecycle_events: keep one row per (market_id, publish_time, status, in_play)
DELETE FROM market_lifecycle_events
WHERE ctid IN (
    SELECT ctid FROM (
        SELECT ctid,
               ROW_NUMBER() OVER (
                   PARTITION BY market_id, publish_time, status, in_play
                   ORDER BY received_time DESC NULLS LAST
               ) AS rn
        FROM market_lifecycle_events
    ) ranked
    WHERE ranked.rn > 1
);

-- ---------------------------------------------------------------------------
-- 2) traded_volume: PK to (market_id, selection_id, price, publish_time)
-- ---------------------------------------------------------------------------
ALTER TABLE traded_volume
    DROP CONSTRAINT IF EXISTS traded_volume_pkey;

ALTER TABLE traded_volume
    ADD PRIMARY KEY (market_id, selection_id, price, publish_time);

-- ---------------------------------------------------------------------------
-- 3) market_lifecycle_events: refined unique key (market_id, publish_time, status, in_play)
-- ---------------------------------------------------------------------------
ALTER TABLE market_lifecycle_events
    DROP CONSTRAINT IF EXISTS uq_lifecycle_market_publish_status;

ALTER TABLE market_lifecycle_events
    ADD CONSTRAINT uq_lifecycle_market_publish_status_inplay
    UNIQUE (market_id, publish_time, status, in_play);

-- ---------------------------------------------------------------------------
-- 4) Index on markets(event_id) to speed up joins between events and markets
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_markets_event_id ON markets(event_id);
