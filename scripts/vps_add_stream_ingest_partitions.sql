-- Add missing daily partitions to stream_ingest.ladder_levels (VPS).
-- Run: psql -U netbet -d netbet -f scripts/vps_add_stream_ingest_partitions.sql
-- Or: cat scripts/vps_add_stream_ingest_partitions.sql | docker exec -i netbet-postgres psql -U netbet -d netbet -f -

SET search_path = stream_ingest;

DO $$
DECLARE
    today_utc   date := (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date;
    tomorrow_utc date := today_utc + 1;
    part_name   text;
    range_from  timestamptz;
    range_to    timestamptz;
BEGIN
    part_name  := 'ladder_levels_' || to_char(today_utc, 'YYYYMMDD');
    range_from := (today_utc::timestamp AT TIME ZONE 'UTC');
    range_to   := (tomorrow_utc::timestamp AT TIME ZONE 'UTC');
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I PARTITION OF ladder_levels FOR VALUES FROM (%L) TO (%L)',
        part_name, range_from, range_to
    );
    RAISE NOTICE 'Partition % created (FROM % TO %)', part_name, range_from, range_to;

    part_name  := 'ladder_levels_' || to_char(tomorrow_utc, 'YYYYMMDD');
    range_from := (tomorrow_utc::timestamp AT TIME ZONE 'UTC');
    range_to   := ((tomorrow_utc + 1)::timestamp AT TIME ZONE 'UTC');
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I PARTITION OF ladder_levels FOR VALUES FROM (%L) TO (%L)',
        part_name, range_from, range_to
    );
    RAISE NOTICE 'Partition % created (FROM % TO %)', part_name, range_from, range_to;
END
$$;
