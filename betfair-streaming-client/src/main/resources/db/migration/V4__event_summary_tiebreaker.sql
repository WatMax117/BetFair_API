-- NetBet Betfair Streaming – v_event_summary tie-breaker: add market_id ASC to DISTINCT ON ordering.
-- Ensures deterministic primary market per type when market_start_time ties.

CREATE OR REPLACE VIEW v_event_summary AS
SELECT
    e.event_id,
    e.event_name,
    e.home_team,
    e.away_team,
    m1.market_id   AS match_odds_market_id,
    m1.market_name AS match_odds_market_name,
    m2.market_id   AS over_under_25_market_id,
    m2.market_name AS over_under_25_market_name,
    m3.market_id   AS half_time_market_id,
    m3.market_name AS half_time_market_name,
    m4.market_id   AS over_under_05_ht_market_id,
    m4.market_name AS over_under_05_ht_market_name,
    m5.market_id   AS next_goal_market_id,
    m5.market_name AS next_goal_market_name
FROM events e
LEFT JOIN (
    SELECT DISTINCT ON (event_id) event_id, market_id, market_name
    FROM markets WHERE market_type = 'MATCH_ODDS_FT'
    ORDER BY event_id, market_start_time ASC NULLS LAST, market_id ASC
) m1 ON m1.event_id = e.event_id
LEFT JOIN (
    SELECT DISTINCT ON (event_id) event_id, market_id, market_name
    FROM markets WHERE market_type = 'OVER_UNDER_25_FT'
    ORDER BY event_id, market_start_time ASC NULLS LAST, market_id ASC
) m2 ON m2.event_id = e.event_id
LEFT JOIN (
    SELECT DISTINCT ON (event_id) event_id, market_id, market_name
    FROM markets WHERE market_type = 'HALF_TIME_RESULT'
    ORDER BY event_id, market_start_time ASC NULLS LAST, market_id ASC
) m3 ON m3.event_id = e.event_id
LEFT JOIN (
    SELECT DISTINCT ON (event_id) event_id, market_id, market_name
    FROM markets WHERE market_type = 'OVER_UNDER_05_HT'
    ORDER BY event_id, market_start_time ASC NULLS LAST, market_id ASC
) m4 ON m4.event_id = e.event_id
LEFT JOIN (
    SELECT DISTINCT ON (event_id) event_id, market_id, market_name
    FROM markets WHERE market_type = 'NEXT_GOAL'
    ORDER BY event_id, market_start_time ASC NULLS LAST, market_id ASC
) m5 ON m5.event_id = e.event_id;
