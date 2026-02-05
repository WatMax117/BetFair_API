-- NetBet – Audit ladder partition by market type (ladder_levels has no market_type; join with markets).
-- Usage: docker exec -i netbet-postgres psql -U netbet -d netbet -f - < scripts/audit_partition_market_types.sql
-- Or:    docker exec netbet-postgres psql -U netbet -d netbet -c "SELECT m.market_type, count(*) FROM ladder_levels_20260205 l JOIN markets m ON l.market_id = m.market_id GROUP BY m.market_type ORDER BY m.market_type;"
-- Replace 20260205 with current UTC date (YYYYMMDD) if different.

SELECT m.market_type, count(*) AS row_count
FROM ladder_levels_20260205 l
JOIN markets m ON l.market_id = m.market_id
GROUP BY m.market_type
ORDER BY m.market_type;
