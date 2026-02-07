SELECT 
    COUNT(*) as total_rows,
    MIN(publish_time) as first_record,
    MAX(publish_time) as last_record,
    COUNT(DISTINCT market_id) as active_markets,
    ROUND(CAST(COUNT(*) AS DECIMAL) / 
        EXTRACT(EPOCH FROM (MAX(publish_time) - MIN(publish_time))) * 60, 2) as records_per_minute
FROM market_liquidity_history
WHERE publish_time > NOW() - INTERVAL '1 hour';
