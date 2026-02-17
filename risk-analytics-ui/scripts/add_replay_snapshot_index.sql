-- Optional: index for replay_snapshot endpoint (O(log N) for max publish_time per market).
-- Run as schema owner. Idempotent.
CREATE INDEX IF NOT EXISTS idx_stream_ladder_market_publish
  ON stream_ingest.ladder_levels (market_id, publish_time DESC);
