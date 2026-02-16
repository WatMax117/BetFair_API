-- Check source column values in market_book_snapshots
SELECT DISTINCT source FROM public.market_book_snapshots LIMIT 10;

-- Check data volume
SELECT COUNT(*) as total_snapshots, COUNT(DISTINCT market_id) as markets, MIN(snapshot_at) as min_time, MAX(snapshot_at) as max_time 
FROM public.market_book_snapshots;
