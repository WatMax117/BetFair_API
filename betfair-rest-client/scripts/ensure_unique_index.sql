-- Add unique index on (market_id, snapshot_at) to prevent duplicate snapshots on retries.
-- Run against the netbet database, e.g.:
--   psql -U netbet -d netbet -f scripts/ensure_unique_index.sql
--   or: docker exec -i netbet-postgres psql -U netbet -d netbet -f - < scripts/ensure_unique_index.sql

CREATE UNIQUE INDEX IF NOT EXISTS idx_market_risk_snapshots_market_snapshot
ON market_risk_snapshots (market_id, snapshot_at);
