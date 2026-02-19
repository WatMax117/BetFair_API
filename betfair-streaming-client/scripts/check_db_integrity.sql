-- NetBet Betfair Streaming – Database integrity checks (run after 10+ min live data)
-- Expect: Top-8 guard = 0; Market type guard = 5 distinct allowed values; metadata/lifecycle/latency as described.

-- 1) Top-8 Guard: ladder_levels must only contain level 0–7. Result must be 0.
SELECT COUNT(*) AS ladder_levels_above_7
FROM ladder_levels
WHERE level > 7;

-- 2) Market Type Guard: only the 5 allowed market types. Result should list exactly: MATCH_ODDS_FT, OVER_UNDER_25_FT, OVER_UNDER_05_HT, MATCH_ODDS_HT, NEXT_GOAL
SELECT DISTINCT market_type
FROM markets
ORDER BY market_type;

-- 3) Metadata Hydration Check: events with home_team populated (from "Home v Away" parsing)
SELECT COUNT(*) AS events_with_home_team
FROM events
WHERE home_team IS NOT NULL;

-- 4) Lifecycle Presence: should be > 0 during live matches
SELECT COUNT(*) AS lifecycle_events_count
FROM market_lifecycle_events;

-- 5) Latency Sanity: average (received_time - publish_time) for ladder_levels (should be positive, small)
--    Only rows with non-null publish_time to avoid null results.
SELECT AVG(received_time - publish_time) AS avg_latency_interval
FROM ladder_levels
WHERE publish_time IS NOT NULL;

-- 6) No duplicate keys in traded_volume (PK: market_id, selection_id, price, publish_time). Result must be 0.
SELECT COUNT(*) AS traded_volume_duplicate_key_count
FROM (
    SELECT market_id, selection_id, price, publish_time
    FROM traded_volume
    GROUP BY market_id, selection_id, price, publish_time
    HAVING COUNT(*) > 1
) t;

-- 7) No duplicate keys in market_lifecycle_events (unique: market_id, publish_time, status, in_play). Result must be 0.
SELECT COUNT(*) AS lifecycle_duplicate_key_count
FROM (
    SELECT market_id, publish_time, status, in_play
    FROM market_lifecycle_events
    GROUP BY market_id, publish_time, status, in_play
    HAVING COUNT(*) > 1
) t;
