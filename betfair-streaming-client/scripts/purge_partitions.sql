-- NetBet Betfair Streaming – Drop ladder_levels daily partitions older than 30 days (run periodically, e.g. weekly).
-- Strictly matches daily pattern ladder_levels_YYYYMMDD only (regex ^ladder_levels_[0-9]{8}$). All dates in UTC.
-- Usage: psql -U netbet -d netbet -f scripts/purge_partitions.sql
-- RAISE NOTICE logs exactly which partition is being dropped for operational visibility.

DO $$
DECLARE
    cutoff_date date := (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date - 30;
    cutoff_ymd  text := to_char(cutoff_date, 'YYYYMMDD');
    dropped_cnt int := 0;
    r           record;
BEGIN
    RAISE NOTICE 'Purging ladder_levels partitions older than % (cutoff_ymd=%)', cutoff_date, cutoff_ymd;
    FOR r IN
        SELECT child.relname AS part_name
        FROM pg_inherits
        JOIN pg_class parent ON parent.oid = pg_inherits.inhparent
        JOIN pg_class child  ON child.oid = pg_inherits.inhrelid
        WHERE parent.relname = 'ladder_levels'
          AND child.relname ~ '^ladder_levels_[0-9]{8}$'
          AND child.relname < 'ladder_levels_' || cutoff_ymd
    LOOP
        EXECUTE format('DROP TABLE IF EXISTS %I', r.part_name);
        RAISE NOTICE 'Dropped partition: %', r.part_name;
        dropped_cnt := dropped_cnt + 1;
    END LOOP;
    RAISE NOTICE 'Purge complete: % partition(s) dropped', dropped_cnt;
END
$$;
