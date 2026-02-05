-- Liquidity v1.2.1 – Bulletproof Pulse Check (COALESCE for NULL-safe interpretation)
-- Run on VPS: docker exec -i netbet-postgres psql -U netbet -d netbet -f /opt/netbet/scripts/pulse_check_v1.2.sql
-- Or with -c and the query below (use coalesce so NULL total_matched is handled identically).

SELECT
    (SELECT count(*) FROM market_liquidity_history) AS history_rows,
    (SELECT count(*) FROM markets WHERE coalesce(total_matched, 0) > 0) AS markets_with_vol,
    (SELECT max(total_matched) FROM markets) AS max_vol;
