-- Check date range in streaming data
SELECT 
  MIN(publish_time) as min_time, 
  MAX(publish_time) as max_time, 
  COUNT(*) as total_rows,
  COUNT(DISTINCT market_id) as markets
FROM stream_ingest.ladder_levels 
WHERE side = 'B' 
  AND level BETWEEN 1 AND 8;
