# Database Schema Report (VPS Live Inspection)

**Date:** Generated from live VPS diagnostic queries.  
**Target:** `netbet-postgres` @ netbet DB, schema `public`.

---

## Step 1: Comprehensive Schema Inspection (Results)

Tables queried: `events`, `markets`, `market_liquidity_history`, `ladder_levels`.

### Actual structure returned from VPS

| table_name | column_name      | data_type                  | is_nullable | key_type |
|------------|------------------|----------------------------|-------------|----------|
| events     | event_id         | character varying          | NO          | PK       |
| events     | event_name       | text                       | YES         |          |
| events     | home_team        | character varying          | YES         |          |
| events     | away_team        | character varying          | YES         |          |
| events     | open_date        | timestamp with time zone   | YES         |          |
| ladder_levels | market_id      | character varying          | NO          | PK       |
| ladder_levels | selection_id   | bigint                     | NO          | PK       |
| ladder_levels | side           | character                  | NO          | PK       |
| ladder_levels | level          | smallint                   | NO          | PK       |
| ladder_levels | price          | double precision           | NO          |          |
| ladder_levels | size           | double precision           | NO          |          |
| ladder_levels | publish_time   | timestamp with time zone   | NO          | PK       |
| ladder_levels | received_time  | timestamp with time zone   | NO          |          |
| markets    | market_id        | character varying          | NO          | PK       |
| markets    | event_id         | character varying          | NO          |          |
| markets    | market_type      | character varying          | NO          |          |
| markets    | market_name      | text                       | YES         |          |
| markets    | market_start_time| timestamp with time zone   | YES         |          |

**Note:** `market_liquidity_history` did not appear in the result set because it **does not exist** on the VPS at inspection time (V5 migration not yet applied).

---

## Step 2: Partition Verification (Results)

**Parent table:** `ladder_levels`

| partition_name         | partition_range                                                                 |
|------------------------|-----------------------------------------------------------------------------------|
| ladder_levels_initial  | FOR VALUES FROM ('2020-01-01 00:00:00+00') TO ('2026-02-05 00:00:00+00')        |
| ladder_levels_20260205 | FOR VALUES FROM ('2026-02-05 00:00:00+00') TO ('2026-02-06 00:00:00+00')        |
| ladder_levels_20260206 | FOR VALUES FROM ('2026-02-06 00:00:00+00') TO ('2026-02-07 00:00:00+00')        |

Partitioning is correctly attached; daily partitions exist for the inspected dates.

---

## Step 3: Summary vs V5 Expectations

| Check | Expected (V5) | Actual on VPS | Status |
|-------|----------------|---------------|--------|
| **markets.segment** | VARCHAR(32) | Column **missing** | ❌ V5 not applied |
| **markets.total_matched** | NUMERIC(20,2) | Column **missing** | ❌ V5 not applied |
| **market_liquidity_history** | Exists with market_id, publish_time, total_matched, **max_runner_ltp** | Table **does not exist** | ❌ V5 not applied |
| **v_golden_audit** | View active with event_name, segment, total_ladder_rows, total_distinct_snapshots, current_volume | View **does not exist** | ❌ V5 not applied |

**Conclusion:** The VPS database is at a pre–V5 state (V1–V4). To get the V5 analytical layer:

1. Deploy the latest code (including `V5__analytical_metadata_liquidity.sql`).
2. Run `docker compose up -d --build` so Flyway runs and applies V5.
3. Re-run the schema inspection and this report.

---

## V5 Schema (Reference – After Migration)

Once V5 is applied you should see:

- **markets:** existing columns **plus** `segment` (VARCHAR(32)), `total_matched` (NUMERIC(20,2)).
- **market_liquidity_history:**  
  `market_id` (PK), `publish_time` (PK), `total_matched`, `max_runner_ltp`.
- **v_golden_audit (view):**  
  `event_name`, `segment`, `total_ladder_rows`, `total_distinct_snapshots`, `current_volume`.

---

## How to Re-run This Report

From the project root (scripts present):

```bash
# Schema inspection
Get-Content scripts/schema_inspection.sql -Raw | ssh WatMax-api "docker exec -i netbet-postgres psql -U netbet -d netbet -f -"

# Partition verification
Get-Content scripts/partition_verify.sql -Raw | ssh WatMax-api "docker exec -i netbet-postgres psql -U netbet -d netbet -f -"
```

Or on the VPS:

```bash
docker exec -i netbet-postgres psql -U netbet -d netbet -f - < /path/to/schema_inspection.sql
docker exec -i netbet-postgres psql -U netbet -d netbet -f - < /path/to/partition_verify.sql
```
