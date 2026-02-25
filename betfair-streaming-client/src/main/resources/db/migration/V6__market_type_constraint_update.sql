-- Update allowed market types: remove HALF_TIME_RESULT, add MATCH_ODDS_HT.
-- Streaming subscription filter is now: MATCH_ODDS_FT, OVER_UNDER_25_FT, OVER_UNDER_05_HT, MATCH_ODDS_HT, NEXT_GOAL.

ALTER TABLE public.markets DROP CONSTRAINT IF EXISTS chk_market_type;

-- Migrate existing rows before adding constraint
UPDATE public.markets SET market_type = 'MATCH_ODDS_HT' WHERE market_type = 'HALF_TIME_RESULT';
UPDATE public.markets SET market_type = 'MATCH_ODDS_FT' WHERE market_type = 'MATCH_ODDS';
UPDATE public.markets SET market_type = 'OVER_UNDER_25_FT' WHERE market_type = 'OVER_UNDER_25';
UPDATE public.markets SET market_type = 'OVER_UNDER_25_FT' WHERE market_type = 'OVER_UNDER_2_5';
UPDATE public.markets SET market_type = 'OVER_UNDER_05_HT' WHERE market_type = 'OVER_UNDER_05';
UPDATE public.markets SET market_type = 'MATCH_ODDS_HT' WHERE market_type = 'HALF_TIME';

ALTER TABLE public.markets ADD CONSTRAINT chk_market_type CHECK (market_type IN (
    'MATCH_ODDS_FT', 'OVER_UNDER_25_FT', 'OVER_UNDER_05_HT', 'MATCH_ODDS_HT', 'NEXT_GOAL'
));
