# Migration 002 — stream_ingest schema on VPS (unify with dev)

## Purpose

Ensure VPS Postgres has `stream_ingest` schema and tables so `/api/stream/*` endpoints return 200 instead of `UndefinedTable: relation "stream_ingest.ladder_levels" does not exist`.

## Applied

- **Migration file:** `db/migrations/002_stream_ingest_schema_vps.sql`
- **VPS:** Applied 2026-02-16 via SSH: `cat /opt/netbet/db/migrations/002_stream_ingest_schema_vps.sql | docker exec -i netbet-postgres psql -U netbet -d netbet -f -`
- **Result:** `COMMIT` succeeded. `/stream/events/by-date-snapshots` returns **HTTP 200** (body `[]` when no data).

## What the migration does

1. **CREATE SCHEMA IF NOT EXISTS stream_ingest**
2. **CREATE TABLE stream_ingest.ladder_levels** — same columns as dev (V1 canonical): market_id, selection_id, side, level, price, size, publish_time, received_time; PK (market_id, selection_id, side, level, publish_time); index on (market_id, selection_id, publish_time DESC)
3. **CREATE TABLE stream_ingest.market_liquidity_history** — market_id, publish_time, total_matched, max_runner_ltp; indexes on market_id and publish_time DESC
4. **Data copy** — If `public.ladder_levels` or `public.market_liquidity_history` exist, copies rows into `stream_ingest.*` (ON CONFLICT DO NOTHING)
5. **Grants** — GRANT USAGE ON SCHEMA stream_ingest + GRANT SELECT on both tables to **netbet_analytics_reader** so the Risk Analytics API can read stream_ingest

## Step 1 (report findings) — optional

On VPS DB:

```sql
select table_schema, table_name
from information_schema.tables
where table_name in ('ladder_levels', 'market_liquidity_history')
order by table_schema, table_name;

select schema_name from information_schema.schemata order by schema_name;
```

## Step 3 (verification) — after migration

```sql
select table_schema, table_name
from information_schema.tables
where table_schema = 'stream_ingest'
  and table_name in ('ladder_levels', 'market_liquidity_history');

select count(*) from stream_ingest.ladder_levels;
select max(publish_time) from stream_ingest.ladder_levels;
```

Then: open `/stream` in browser; confirm `/api/stream/events/by-date-snapshots` returns 200 and events/charts load when data exists.
