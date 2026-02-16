-- Safe conversion: stream_ingest.ladder_levels from regular table to partitioned.
-- Non-destructive: renames original to ladder_levels_old (do not drop until approved).
-- Run as netbet (table owner). Run during low write activity.
-- Usage: cat scripts/convert_ladder_levels_to_partitioned.sql | docker exec -i netbet-postgres psql -U netbet -d netbet -v ON_ERROR_STOP=1

-- Pre-check: abort if already partitioned
DO $$
DECLARE
    k char;
BEGIN
    SELECT c.relkind INTO k FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'stream_ingest' AND c.relname = 'ladder_levels';
    IF k = 'p' THEN
        RAISE EXCEPTION 'ladder_levels is already partitioned (relkind=p). No conversion needed.';
    END IF;
    IF k IS NULL THEN
        RAISE EXCEPTION 'stream_ingest.ladder_levels does not exist.';
    END IF;
END
$$;

BEGIN;

-- 1) Create partitioned parent (same structure as current table)
CREATE TABLE stream_ingest.ladder_levels_new (
    market_id     VARCHAR(32)  NOT NULL,
    selection_id  BIGINT       NOT NULL,
    side          CHAR(1)      NOT NULL CHECK (side IN ('B', 'L')),
    level         SMALLINT     NOT NULL CHECK (level >= 0 AND level <= 7),
    price         DOUBLE PRECISION NOT NULL,
    size          DOUBLE PRECISION NOT NULL,
    publish_time  TIMESTAMPTZ  NOT NULL,
    received_time TIMESTAMPTZ  NOT NULL,
    PRIMARY KEY (market_id, selection_id, side, level, publish_time)
) PARTITION BY RANGE (publish_time);

-- 2) Initial partition: from epoch to start of today (UTC) - holds all existing data
DO $$
DECLARE
    today_start timestamptz := ((CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date::timestamp AT TIME ZONE 'UTC');
BEGIN
    EXECUTE format(
        'CREATE TABLE stream_ingest.ladder_levels_initial PARTITION OF stream_ingest.ladder_levels_new FOR VALUES FROM (%L) TO (%L)',
        '2020-01-01 00:00:00+00',
        today_start
    );
END
$$;

-- 3) Daily partitions: today through today+30 (UTC)
DO $$
DECLARE
    d date := (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date;
    end_date date := d + 30;
    part_name text;
    range_from timestamptz;
    range_to timestamptz;
BEGIN
    WHILE d <= end_date LOOP
        part_name := 'ladder_levels_' || to_char(d, 'YYYYMMDD');
        range_from := (d::timestamp AT TIME ZONE 'UTC');
        range_to := ((d + 1)::timestamp AT TIME ZONE 'UTC');
        EXECUTE format(
            'CREATE TABLE stream_ingest.%I PARTITION OF stream_ingest.ladder_levels_new FOR VALUES FROM (%L) TO (%L)',
            part_name, range_from, range_to
        );
        d := d + 1;
    END LOOP;
END
$$;

-- 4) Copy data
INSERT INTO stream_ingest.ladder_levels_new
SELECT * FROM stream_ingest.ladder_levels;

-- 5) Recreate index
CREATE INDEX idx_ladder_market_selection_time ON stream_ingest.ladder_levels_new(market_id, selection_id, publish_time DESC);

-- 6) Swap tables (keep old for validation)
ALTER TABLE stream_ingest.ladder_levels RENAME TO ladder_levels_old;
ALTER TABLE stream_ingest.ladder_levels_new RENAME TO ladder_levels;

COMMIT;

-- Validation (run after COMMIT)
SELECT 'ladder_levels row count' AS check_name, COUNT(*) AS cnt FROM stream_ingest.ladder_levels
UNION ALL
SELECT 'ladder_levels_old row count', COUNT(*) FROM stream_ingest.ladder_levels_old;

SELECT relkind, relname FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'stream_ingest' AND relname IN ('ladder_levels', 'ladder_levels_old');
