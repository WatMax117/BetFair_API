-- NetBet Betfair Streaming – PostgreSQL v1 schema
-- All timestamps TIMESTAMPTZ. Metadata (low-frequency) + high-frequency append-only time series.

-- Metadata: events (from listMarketCatalogue, home/away from eventName parsing)
CREATE TABLE events (
    event_id     VARCHAR(32) PRIMARY KEY,
    event_name   TEXT,
    home_team    VARCHAR(255),
    away_team    VARCHAR(255),
    open_date    TIMESTAMPTZ
);

-- Metadata: markets (only allowed 5 market types)
CREATE TABLE markets (
    market_id         VARCHAR(32) PRIMARY KEY,
    event_id          VARCHAR(32) NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
    market_type       VARCHAR(64) NOT NULL,
    market_name       TEXT,
    market_start_time TIMESTAMPTZ,
    CONSTRAINT chk_market_type CHECK (market_type IN (
        'MATCH_ODDS_FT', 'OVER_UNDER_25_FT', 'HALF_TIME_RESULT', 'OVER_UNDER_05_HT', 'NEXT_GOAL'
    ))
);

CREATE INDEX idx_markets_event_id ON markets(event_id);

-- Metadata: runners (selection_id + runner_name per market)
CREATE TABLE runners (
    market_id    VARCHAR(32) NOT NULL REFERENCES markets(market_id) ON DELETE CASCADE,
    selection_id BIGINT     NOT NULL,
    runner_name  TEXT,
    PRIMARY KEY (market_id, selection_id)
);

-- High-frequency: lifecycle (OPEN / SUSPENDED / CLOSED, in_play)
CREATE TABLE market_lifecycle_events (
    market_id     VARCHAR(32)  NOT NULL,
    status        VARCHAR(32),
    in_play       BOOLEAN,
    publish_time  TIMESTAMPTZ  NOT NULL,
    received_time TIMESTAMPTZ  NOT NULL
);

CREATE INDEX idx_lifecycle_market_time ON market_lifecycle_events(market_id, publish_time DESC);

-- High-frequency: top-8 ladder snapshots (append-only)
CREATE TABLE ladder_levels (
    market_id     VARCHAR(32)  NOT NULL,
    selection_id  BIGINT       NOT NULL,
    side          CHAR(1)      NOT NULL CHECK (side IN ('B', 'L')),
    level         SMALLINT     NOT NULL CHECK (level >= 0 AND level <= 7),
    price         DOUBLE PRECISION NOT NULL,
    size          DOUBLE PRECISION NOT NULL,
    publish_time  TIMESTAMPTZ   NOT NULL,
    received_time TIMESTAMPTZ   NOT NULL,
    PRIMARY KEY (market_id, selection_id, side, level, publish_time)
);

CREATE INDEX idx_ladder_market_selection_time ON ladder_levels(market_id, selection_id, publish_time DESC);

-- High-frequency: traded volume (append-only)
CREATE TABLE traded_volume (
    market_id     VARCHAR(32)  NOT NULL,
    selection_id  BIGINT       NOT NULL,
    price         DOUBLE PRECISION NOT NULL,
    size_traded   DOUBLE PRECISION NOT NULL,
    publish_time  TIMESTAMPTZ   NOT NULL,
    received_time TIMESTAMPTZ   NOT NULL,
    PRIMARY KEY (market_id, selection_id, price, publish_time, received_time)
);

CREATE INDEX idx_traded_volume_market_time ON traded_volume(market_id, selection_id, publish_time DESC);
