-- Add impedance input columns to market_derived_metrics (backStake, backOdds, layStake, layOdds per outcome).
-- Production-safe: ADD COLUMN IF NOT EXISTS; type matches rest-client and existing table (DOUBLE PRECISION).
-- Run once per environment: docker exec -i netbet-postgres psql -U netbet -d netbet < risk-analytics-ui/sql/migrations/2026-02-13_add_impedance_input_columns.sql

ALTER TABLE market_derived_metrics
  ADD COLUMN IF NOT EXISTS home_back_stake  DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS home_back_odds   DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS home_lay_stake   DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS home_lay_odds    DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS away_back_stake  DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS away_back_odds   DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS away_lay_stake   DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS away_lay_odds    DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS draw_back_stake  DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS draw_back_odds   DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS draw_lay_stake   DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS draw_lay_odds    DOUBLE PRECISION;
