-- V8: Full-Time only; no Half-Time. View for stream subscription from REST discovery.
-- REST discovery (discovery_hourly.py) populates rest_events, rest_markets; stream client reads active_markets_to_stream.

ALTER TABLE public.markets DROP CONSTRAINT IF EXISTS chk_market_type;

ALTER TABLE public.markets ADD CONSTRAINT chk_market_type CHECK (market_type IN (
    'MATCH_ODDS_FT', 'OVER_UNDER_25_FT', 'NEXT_GOAL'
));

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
