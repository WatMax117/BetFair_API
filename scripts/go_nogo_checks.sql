-- Go/No-Go: max publish_time and row counts
SELECT 'ladder_levels max(publish_time)' AS check_name, max(publish_time)::text AS value FROM stream_ingest.ladder_levels
UNION ALL
SELECT 'ladder_levels_old max(publish_time)', max(publish_time)::text FROM stream_ingest.ladder_levels_old
UNION ALL
SELECT 'ladder_levels count', count(*)::text FROM stream_ingest.ladder_levels
UNION ALL
SELECT 'ladder_levels_old count', count(*)::text FROM stream_ingest.ladder_levels_old;
