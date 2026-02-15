-- Validate that an id exists in market_event_metadata (same DB as Risk Analytics API).
-- Replace '1.251575028' with the id you are checking.
--
-- Run (Docker, from repo root):
--   docker exec -i netbet-postgres psql -U netbet -d netbet -c "SELECT market_id, event_id FROM market_event_metadata WHERE market_id = '1.251575028' OR event_id = '1.251575028';"
--
-- No rows => 404 is expected (missing ingestion or API using different DB).

SELECT market_id, event_id
FROM market_event_metadata
WHERE market_id = '1.251575028' OR event_id = '1.251575028';
