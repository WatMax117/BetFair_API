-- Add best-level (L1) size columns to market_derived_metrics for back and lay.
-- Enables backSize/laySize in UI and Size Impedance Index (L1) from real data.
-- Production-safe: ADD COLUMN IF NOT EXISTS; type DOUBLE PRECISION (consistent with existing).
-- Run once per environment: docker exec -i netbet-postgres psql -U netbet -d netbet < risk-analytics-ui/sql/migrations/2026-02-14_add_l1_size_columns.sql

ALTER TABLE market_derived_metrics
  ADD COLUMN IF NOT EXISTS home_best_back_size_l1  DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS away_best_back_size_l1  DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS draw_best_back_size_l1  DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS home_best_lay_size_l1   DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS away_best_lay_size_l1   DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS draw_best_lay_size_l1   DOUBLE PRECISION;
