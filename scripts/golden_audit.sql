-- Version: v1.2.2-liquidity-fallback (TRD summation logic)
-- Last Updated: 2026-02-05
-- Compatibility: Matches MarketCache.java with Traded Ladder Fallback
--
-- Golden audit: event_name, segment, ladder row volume, distinct snapshots, current volume.
-- Uses CTE to aggregate ladder per market first (avoids join multiplication; current_volume = actual totalMatched).
-- Targets today's data (UTC): uses parent table ladder_levels with date filter so partition is auto-pruned.

WITH today_utc AS (
    SELECT (now() AT TIME ZONE 'UTC')::date AS d
),
market_stats AS (
    SELECT
        l.market_id,
        COUNT(*) AS total_ladder_rows,
        COUNT(DISTINCT (l.publish_time, l.received_time)) AS distinct_snapshots
    FROM ladder_levels l
    CROSS JOIN today_utc t
    WHERE (l.publish_time AT TIME ZONE 'UTC')::date = t.d
    GROUP BY l.market_id
)
SELECT
    e.event_name,
    m.segment,
    SUM(ms.total_ladder_rows) AS total_ladder_rows,
    SUM(ms.distinct_snapshots) AS total_distinct_snapshots,
    SUM(COALESCE(m.total_matched, 0)) AS current_volume
FROM events e
JOIN markets m ON e.event_id = m.event_id
JOIN market_stats ms ON m.market_id = ms.market_id
GROUP BY e.event_name, m.segment
ORDER BY current_volume;
