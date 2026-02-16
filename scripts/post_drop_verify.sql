SELECT to_regclass('stream_ingest.ladder_levels_old') AS old_table_oid;
SELECT max(publish_time) AS ladder_levels_max_ts FROM stream_ingest.ladder_levels;
ANALYZE stream_ingest.ladder_levels;
