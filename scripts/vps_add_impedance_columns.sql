ALTER TABLE public.market_derived_metrics ADD COLUMN IF NOT EXISTS home_impedance double precision;
ALTER TABLE public.market_derived_metrics ADD COLUMN IF NOT EXISTS away_impedance double precision;
ALTER TABLE public.market_derived_metrics ADD COLUMN IF NOT EXISTS draw_impedance double precision;
ALTER TABLE public.market_derived_metrics ADD COLUMN IF NOT EXISTS home_impedance_norm double precision;
ALTER TABLE public.market_derived_metrics ADD COLUMN IF NOT EXISTS away_impedance_norm double precision;
ALTER TABLE public.market_derived_metrics ADD COLUMN IF NOT EXISTS draw_impedance_norm double precision;
