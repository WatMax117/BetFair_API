-- V8: View for stream subscription from REST discovery.
-- REST discovery (discovery_hourly.py) populates rest_events, rest_markets; stream client reads active_markets_to_stream.
-- chk_market_type stays 5-type (V6): MATCH_ODDS_FT, OVER_UNDER_25_FT, OVER_UNDER_05_HT, MATCH_ODDS_HT, NEXT_GOAL.

-- Tables for REST discovery (metadata only). Created here so view exists before first REST run.
CREATE TABLE IF NOT EXISTS public.rest_events (
    event_id     VARCHAR(32) PRIMARY KEY,
    event_name   TEXT,
    home_team    VARCHAR(255),
    away_team    VARCHAR(255),
    open_date    TIMESTAMPTZ,
    competition_name TEXT,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.rest_markets (
    market_id         VARCHAR(32) PRIMARY KEY,
    event_id          VARCHAR(32) NOT NULL,
    market_type       VARCHAR(64) NOT NULL,
    market_name       TEXT,
    market_start_time TIMESTAMPTZ,
    last_seen_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rest_markets_event_id ON public.rest_markets(event_id);
CREATE INDEX IF NOT EXISTS idx_rest_markets_market_type ON public.rest_markets(market_type);

CREATE OR REPLACE VIEW public.active_markets_to_stream AS
SELECT market_id, event_id, market_type, market_name, market_start_time
FROM public.rest_markets
WHERE market_type IN ('MATCH_ODDS_FT', 'OVER_UNDER_25_FT', 'NEXT_GOAL')
   OR (market_type LIKE 'OVER_UNDER_%' AND market_type NOT LIKE '%HT%');
