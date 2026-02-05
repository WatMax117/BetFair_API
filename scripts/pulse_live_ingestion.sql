-- Live data ingestion pulse: history, markets with volume, max_volume, ladder rows today (UTC)
SELECT
    (SELECT count(*) FROM market_liquidity_history) AS history_rows,
    (SELECT count(*) FROM markets WHERE coalesce(total_matched, 0) > 0) AS markets_with_vol,
    (SELECT max(total_matched) FROM markets) AS max_volume,
    (SELECT count(*) FROM ladder_levels WHERE (publish_time AT TIME ZONE 'UTC')::date = (now() AT TIME ZONE 'UTC')::date) AS ladder_rows_today;
