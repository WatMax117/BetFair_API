-- Layer 0: Event / market metadata (from listMarketCatalogue).
-- Run once: psql -U netbet -d netbet -f create_market_event_metadata.sql

CREATE TABLE IF NOT EXISTS market_event_metadata (
    market_id TEXT PRIMARY KEY,
    market_name TEXT NULL,
    market_start_time TIMESTAMPTZ NULL,
    sport_id TEXT NULL,
    sport_name TEXT NULL,
    event_id TEXT NULL,
    event_name TEXT NULL,
    event_open_date TIMESTAMPTZ NULL,
    country_code TEXT NULL,
    competition_id TEXT NULL,
    competition_name TEXT NULL,
    timezone TEXT NULL,
    home_selection_id BIGINT NULL,
    away_selection_id BIGINT NULL,
    draw_selection_id BIGINT NULL,
    home_runner_name TEXT NULL,
    away_runner_name TEXT NULL,
    draw_runner_name TEXT NULL,
    metadata_version TEXT NULL DEFAULT 'v1',
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mem_event_open_date ON market_event_metadata (event_open_date);
CREATE INDEX IF NOT EXISTS idx_mem_competition_name ON market_event_metadata (competition_name);
CREATE INDEX IF NOT EXISTS idx_mem_market_start_time ON market_event_metadata (market_start_time);
