-- Check side values
SELECT DISTINCT side FROM stream_ingest.ladder_levels LIMIT 10;

-- Check data volume
SELECT COUNT(*) as total_rows, COUNT(DISTINCT market_id) as markets, COUNT(DISTINCT selection_id) as selections 
FROM stream_ingest.ladder_levels 
WHERE side = 'B' AND level BETWEEN 1 AND 8;

-- Check selection mapping availability
SELECT COUNT(*) as markets_with_selections 
FROM public.market_event_metadata 
WHERE home_selection_id IS NOT NULL AND away_selection_id IS NOT NULL AND draw_selection_id IS NOT NULL;

-- Check market types
SELECT DISTINCT market_type FROM public.markets LIMIT 20;

-- Sample ladder data
SELECT market_id, selection_id, side, level, price, size, publish_time 
FROM stream_ingest.ladder_levels 
WHERE side = 'B' AND level BETWEEN 1 AND 3 
LIMIT 10;
