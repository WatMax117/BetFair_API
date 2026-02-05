SELECT m.market_type, count(*)
FROM ladder_levels_20260205 l
JOIN markets m ON l.market_id = m.market_id
GROUP BY m.market_type;
