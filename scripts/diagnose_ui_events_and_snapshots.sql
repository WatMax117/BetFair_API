-- Part 1 diagnostic: confirm current events and snapshot recency.
-- Run on Postgres (e.g. docker exec netbet-postgres psql -U netbet -d netbet -f - < this file).
-- Schema: event_open_date and event_name live in market_event_metadata; market_derived_metrics has market_id, snapshot_at.

-- A) Events with latest snapshot (by event_open_date)
SELECT e.event_name,
       e.event_open_date AS event_start_utc,
       MAX(d.snapshot_at) AS last_snapshot
FROM market_derived_metrics d
JOIN market_event_metadata e ON e.market_id = d.market_id
GROUP BY e.event_name, e.event_open_date
ORDER BY e.event_open_date DESC
LIMIT 20;

-- B) Are there events with event_open_date >= NOW()?
SELECT COUNT(*) AS future_event_count
FROM market_event_metadata e
WHERE e.event_open_date IS NOT NULL
  AND e.event_open_date >= NOW();

-- C) Snapshots in last 24h (any market)
SELECT COUNT(*) AS snapshots_last_24h
FROM market_derived_metrics
WHERE snapshot_at >= NOW() - INTERVAL '24 hours';

-- D) Most recent snapshot time (any market)
SELECT MAX(snapshot_at) AS most_recent_snapshot_utc
FROM market_derived_metrics;
