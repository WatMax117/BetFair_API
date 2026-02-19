-- Update allowed market types: remove HALF_TIME_RESULT, add MATCH_ODDS_HT.
-- Streaming subscription filter is now: MATCH_ODDS_FT, OVER_UNDER_25_FT, OVER_UNDER_05_HT, MATCH_ODDS_HT, NEXT_GOAL.

ALTER TABLE public.markets DROP CONSTRAINT IF EXISTS chk_market_type;

ALTER TABLE public.markets ADD CONSTRAINT chk_market_type CHECK (market_type IN (
    'MATCH_ODDS_FT', 'OVER_UNDER_25_FT', 'OVER_UNDER_05_HT', 'MATCH_ODDS_HT', 'NEXT_GOAL'
));
