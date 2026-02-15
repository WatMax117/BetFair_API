-- MVP simplification: remove Imbalance Index and Impedance Index from schema.
-- Run after API/frontend no longer depend on these fields. Idempotent (IF EXISTS).

ALTER TABLE public.market_derived_metrics DROP COLUMN IF EXISTS home_risk;
ALTER TABLE public.market_derived_metrics DROP COLUMN IF EXISTS away_risk;
ALTER TABLE public.market_derived_metrics DROP COLUMN IF EXISTS draw_risk;
ALTER TABLE public.market_derived_metrics DROP COLUMN IF EXISTS home_impedance;
ALTER TABLE public.market_derived_metrics DROP COLUMN IF EXISTS away_impedance;
ALTER TABLE public.market_derived_metrics DROP COLUMN IF EXISTS draw_impedance;
ALTER TABLE public.market_derived_metrics DROP COLUMN IF EXISTS home_impedance_norm;
ALTER TABLE public.market_derived_metrics DROP COLUMN IF EXISTS away_impedance_norm;
ALTER TABLE public.market_derived_metrics DROP COLUMN IF EXISTS draw_impedance_norm;
ALTER TABLE public.market_derived_metrics DROP COLUMN IF EXISTS home_back_stake;
ALTER TABLE public.market_derived_metrics DROP COLUMN IF EXISTS home_back_odds;
ALTER TABLE public.market_derived_metrics DROP COLUMN IF EXISTS home_lay_stake;
ALTER TABLE public.market_derived_metrics DROP COLUMN IF EXISTS home_lay_odds;
ALTER TABLE public.market_derived_metrics DROP COLUMN IF EXISTS away_back_stake;
ALTER TABLE public.market_derived_metrics DROP COLUMN IF EXISTS away_back_odds;
ALTER TABLE public.market_derived_metrics DROP COLUMN IF EXISTS away_lay_stake;
ALTER TABLE public.market_derived_metrics DROP COLUMN IF EXISTS away_lay_odds;
ALTER TABLE public.market_derived_metrics DROP COLUMN IF EXISTS draw_back_stake;
ALTER TABLE public.market_derived_metrics DROP COLUMN IF EXISTS draw_back_odds;
ALTER TABLE public.market_derived_metrics DROP COLUMN IF EXISTS draw_lay_stake;
ALTER TABLE public.market_derived_metrics DROP COLUMN IF EXISTS draw_lay_odds;
