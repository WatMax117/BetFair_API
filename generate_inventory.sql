-- Generate db_tables.csv
\copy (SELECT n.nspname AS schema, c.relname AS "table", c.relkind AS kind, c.reltuples::bigint AS approx_rows, pg_total_relation_size(c.oid) AS total_bytes FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE c.relkind IN ('r','p') AND n.nspname NOT IN ('pg_catalog','information_schema') ORDER BY pg_total_relation_size(c.oid) DESC) TO '/tmp/db_tables.csv' CSV HEADER;

-- Generate db_dictionary.csv
\copy (SELECT table_schema, table_name, ordinal_position, column_name, data_type, udt_name, is_nullable, column_default FROM information_schema.columns WHERE table_schema NOT IN ('pg_catalog','information_schema') ORDER BY table_schema, table_name, ordinal_position) TO '/tmp/db_dictionary.csv' CSV HEADER;

-- Generate db_dictionary_with_comments.csv
\copy (SELECT n.nspname AS table_schema, c.relname AS table_name, a.attnum AS ordinal_position, a.attname AS column_name, pg_catalog.format_type(a.atttypid, a.atttypmod) AS formatted_type, col_description(a.attrelid, a.attnum) AS column_comment FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid JOIN pg_namespace n ON n.oid = c.relnamespace WHERE a.attnum > 0 AND NOT a.attisdropped AND n.nspname NOT IN ('pg_catalog','information_schema') AND c.relkind IN ('r','p') ORDER BY n.nspname, c.relname, a.attnum) TO '/tmp/db_dictionary_with_comments.csv' CSV HEADER;

-- Generate streaming_vs_rest_classification.csv
\copy (WITH tables AS (SELECT n.nspname AS schema, c.relname AS "table" FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE c.relkind IN ('r','p') AND n.nspname NOT IN ('pg_catalog','information_schema')) SELECT schema, "table", CASE WHEN schema = 'stream_ingest' THEN 'STREAMING' WHEN schema IN ('public') THEN 'POSSIBLE_REST' ELSE 'UNKNOWN' END AS initial_classification, CASE WHEN schema = 'stream_ingest' THEN 'Schema-based rule: stream_ingest' WHEN schema IN ('public') THEN 'Schema-based rule: public' ELSE 'Needs review' END AS rationale FROM tables ORDER BY schema, "table") TO '/tmp/streaming_vs_rest_classification.csv' CSV HEADER;
