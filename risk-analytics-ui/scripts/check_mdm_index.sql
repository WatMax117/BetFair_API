-- Proof for validation: list indexes on market_derived_metrics.
-- Run: psql -U netbet -d netbet -f risk-analytics-ui/scripts/check_mdm_index.sql
-- Expected: row with indexname = idx_mdm_market_snapshot_desc and (market_id, snapshot_at DESC).

SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'market_derived_metrics'
ORDER BY indexname;
