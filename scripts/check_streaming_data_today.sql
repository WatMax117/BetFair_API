-- Check streaming data freshness and active markets today

-- A1) Fresh ladder ticks exist today
SELECT count(*) AS ticks_last_30m, max(publish_time) AS max_pt
FROM stream_ingest.ladder_levels
WHERE publish_time > now() - interval '30 minutes';

-- A2) How many distinct markets produced ticks today?
SELECT count(DISTINCT market_id) AS active_markets_today
FROM stream_ingest.ladder_levels
WHERE publish_time >= date_trunc('day', now() at time zone 'utc')
  AND publish_time <  date_trunc('day', now() at time zone 'utc') + interval '1 day';

-- B1) Sample market - does it have ticks in the last 24h?
-- Replace '1.253494929' with an actual market_id from the list
SELECT count(*) AS ticks_24h, min(publish_time), max(publish_time)
FROM stream_ingest.ladder_levels
WHERE market_id = '1.253494929'
  AND publish_time > now() - interval '24 hours';

-- B2) Sample market - does it have ticks today?
SELECT count(*) AS ticks_today, min(publish_time), max(publish_time)
FROM stream_ingest.ladder_levels
WHERE market_id = '1.253494929'
  AND publish_time >= date_trunc('day', now() at time zone 'utc')
  AND publish_time <  date_trunc('day', now() at time zone 'utc') + interval '1 day';

-- Check: markets with streaming data today but event_open_date is NOT today
SELECT DISTINCT m.market_id, m.event_name, m.event_open_date, 
       COUNT(l.publish_time) AS tick_count_today
FROM market_event_metadata m
INNER JOIN stream_ingest.ladder_levels l ON l.market_id = m.market_id
WHERE l.publish_time >= date_trunc('day', now() at time zone 'utc')
  AND l.publish_time < date_trunc('day', now() at time zone 'utc') + interval '1 day'
  AND (m.event_open_date IS NULL OR m.event_open_date::date != CURRENT_DATE)
GROUP BY m.market_id, m.event_name, m.event_open_date
ORDER BY tick_count_today DESC
LIMIT 10;
