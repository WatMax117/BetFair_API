-- Index for bulk buckets query: fetches all ladder rows for market + selections in time range.
-- Covers: WHERE market_id = ? AND selection_id = ANY(?) AND side = 'B' AND level = 0
--         AND publish_time >= ? AND publish_time <= ?
--         ORDER BY publish_time ASC
CREATE INDEX IF NOT EXISTS idx_ladder_bulk_buckets
  ON stream_ingest.ladder_levels (market_id, selection_id, side, level, publish_time);
