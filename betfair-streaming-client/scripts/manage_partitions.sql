-- NetBet Betfair Streaming – Create daily partitions for ladder_levels (today and tomorrow, UTC).
-- Ensures no gap/overlap with ladder_levels_initial (which ends at start of current day).
-- All date calculations use AT TIME ZONE 'UTC'. Run daily, e.g. via cron.
-- Usage: psql -U netbet -d netbet -f scripts/manage_partitions.sql

DO $$
DECLARE
    today_utc   date := (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date;
    tomorrow_utc date := today_utc + 1;
    part_name   text;
    range_from  timestamptz;
    range_to    timestamptz;
BEGIN
    -- Create today's partition (FROM today 00:00 UTC TO tomorrow 00:00 UTC)
    part_name  := 'ladder_levels_' || to_char(today_utc, 'YYYYMMDD');
    range_from := (today_utc::timestamp AT TIME ZONE 'UTC');
    range_to   := (tomorrow_utc::timestamp AT TIME ZONE 'UTC');
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I PARTITION OF ladder_levels FOR VALUES FROM (%L) TO (%L)',
        part_name, range_from, range_to
    );
    RAISE NOTICE 'Partition % created (FROM % TO %)', part_name, range_from, range_to;

    -- Create tomorrow's partition (FROM tomorrow 00:00 UTC TO day+2 00:00 UTC)
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
