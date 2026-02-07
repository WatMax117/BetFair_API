-- Ensure index exists for (market_id, snapshot_at DESC) for latest-first queries.
-- Run once: psql -U netbet -d netbet -f ensure_mdm_index_desc.sql
-- Idempotent: CREATE INDEX IF NOT EXISTS.

CREATE INDEX IF NOT EXISTS idx_mdm_market_snapshot_desc
ON market_derived_metrics (market_id, snapshot_at DESC);
