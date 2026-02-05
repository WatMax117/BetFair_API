SELECT
    market_id,
    to_char(publish_time, 'HH24:MI:SS.MS') AS precise_time,
    total_matched
FROM market_liquidity_history
ORDER BY publish_time DESC
LIMIT 20;
