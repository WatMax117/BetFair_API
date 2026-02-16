# VPS Partition Investigation and Conversion Report

## Part 1 — Investigation Results

### 1. Database topology

**1.1 Databases on the VPS instance**

| datname   | datallowconn |
|-----------|--------------|
| netbet   | t            |
| postgres | t            |

There is **one Postgres instance** (container `netbet-postgres`). Two databases exist: `netbet` (production) and `postgres` (default system DB).

**1.2 API connection**

- **Effective connection:** `netbet-postgres:5432/netbet` (host from compose: `POSTGRES_HOST=netbet-postgres`, `POSTGRES_DB=netbet`).
- **Masked:** `postgresql://netbet-postgres:5432/netbet?user=<POSTGRES_ANALYTICS_READER_USER>&password=***`
- Partition provisioner uses: `POSTGRES_PARTITION_USER=netbet`, same host/port/DB.

**1.3 Streaming client connection**

- **Effective connection:** `postgres:5432/netbet` with `currentSchema=stream_ingest` (JDBC URL from compose: `jdbc:postgresql://postgres:5432/${POSTGRES_DB:-netbet}?currentSchema=stream_ingest`).
- **Masked:** `jdbc:postgresql://postgres:5432/netbet?currentSchema=stream_ingest&user=<POSTGRES_STREAM_WRITER_USER>&password=***`

**1.4 Same database?**

- **Yes.** Both use the same container (`postgres` and `netbet-postgres` are the same service on the Docker network), same port `5432`, same database name `netbet`. The API uses service name `netbet-postgres` (compose project prefix), the streaming client uses `postgres` (short name); both resolve to the same container.

**Conclusion:** One Postgres instance, one production database (`netbet`). API and streaming client both connect to `netbet`.

---

### 2. Current table type (stream_ingest.ladder_levels)

| Field         | Value |
|---------------|--------|
| **relkind**   | `r` (regular table) |
| **table_owner** | netbet |
| **row_count** | 713,282 |
| **min publish_time** | 2026-02-05 12:07:54.024+00 |
| **max publish_time** | 2026-02-06 23:57:22.957+00 |

---

### 3. Flyway migrations

**flyway_schema_history** is in **public** schema. Rows:

| installed_rank | version | description                    | script                              | installed_on           | success |
|----------------|---------|--------------------------------|-------------------------------------|------------------------|---------|
| 1              | 1       | init schema                    | V1__init_schema.sql                 | 2026-02-05 12:06:21    | t       |
| 2              | 2       | refine constraints             | V2__refine_constraints.sql          | 2026-02-05 12:06:21    | t       |
| 3              | 3       | partition ladder and views     | V3__partition_ladder_and_views.sql  | 2026-02-05 12:06:21    | t       |
| 4              | 4       | event summary tiebreaker       | V4__event_summary_tiebreaker.sql    | 2026-02-05 12:06:21    | t       |
| 5              | 5       | analytical metadata liquidity  | V5__analytical_metadata_liquidity.sql | 2026-02-05 12:06:21  | t       |

**Answers:**

- **Were streaming-client migrations applied?** Yes. V1–V5 are present and successful.
- **Is there a migration that creates ladder_levels as PARTITION BY RANGE (publish_time)?** Yes. V3 creates `ladder_levels` as a partitioned table, renames the old one to `ladder_levels_old`, copies data, drops `ladder_levels_old`.
- **Why is the production table not partitioned?** Flyway runs with `currentSchema=stream_ingest` (JDBC URL). So V1/V3 created (and should have left) `stream_ingest.ladder_levels` as partitioned. The current state (regular table) implies that after Flyway V3, something recreated or replaced `stream_ingest.ladder_levels` as a non-partitioned table. The migration `002_stream_ingest_schema_vps.sql` uses `CREATE TABLE IF NOT EXISTS stream_ingest.ladder_levels` (non-partitioned). If that script was run after a drop or in a restore/clone where the table was missing, it would create the current non-partitioned table. So the table was effectively overwritten by a later, non-partitioned definition (e.g. 002 or similar).

---

## Part 2 — Structural fix (safe conversion)

Procedure used:

1. Create partitioned parent `stream_ingest.ladder_levels_new` (same columns/constraints as current table) with `PARTITION BY RANGE (publish_time)`.
2. Create partitions: one initial partition from 2020-01-01 to today 00:00 UTC (covers existing data), plus daily partitions from today through today+30.
3. Copy data: `INSERT INTO ladder_levels_new SELECT * FROM ladder_levels`.
4. Recreate index: `idx_ladder_market_selection_time` on the new table.
5. Swap: `ladder_levels` → `ladder_levels_old`, `ladder_levels_new` → `ladder_levels`.
6. Commit. Do **not** drop `ladder_levels_old` until explicitly approved.

Script: `scripts/convert_ladder_levels_to_partitioned.sql`.

---

## Part 3 — Final report (after conversion)

Completed on VPS after running `scripts/convert_ladder_levels_to_partitioned.sql`:

1. **Database topology:** Confirmed single instance, single production DB `netbet`; API and streaming client both use it.
2. **Migration status:** Flyway V1–V5 applied; V3 defines partitioned `ladder_levels`; production had been overwritten by a non-partitioned definition (e.g. 002); conversion has been applied.
3. **Table type before conversion:** `relkind = 'r'` (regular table).
4. **Table type after conversion:** `relkind = 'p'` (partitioned table). Validation query: `ladder_levels` = `p`, `ladder_levels_old` = `r`.
5. **Row counts before and after:** Both **713,282**. Validation: `ladder_levels` 713282, `ladder_levels_old` 713282.
6. **Provisioner horizon:** `ladder_levels_partition_horizon_days` = **30** (from `GET /metrics` and `GET /health`).
7. **API and streaming client:** Both connect to the same database `netbet` on the same Postgres instance.

**Partition list after conversion (stream_ingest):**

- `ladder_levels` (parent, partitioned)
- `ladder_levels_initial` (historical data up to today 00:00 UTC)
- `ladder_levels_20260216` … `ladder_levels_20260318` (daily partitions, today through today+30)
- `ladder_levels_old` (original table; **do not drop until explicitly approved**)

**Endpoints after conversion:**

- `GET /health` → `{"status":"ok","ladder_levels_partition_horizon_days":30.0}`
- `GET /metrics` → `ladder_levels_partition_horizon_days 30.0`

**Note:** Any "partition provisioning skipped: ... is not a partitioned table" log line is from a run *before* the conversion. After conversion, the table is partitioned and the horizon is 30. On the next provisioner run (startup or 12h interval), the provisioner will see `relkind=p` and run successfully (create/ensure partitions as needed).

---

## Architectural requirement

Production uses **one single authoritative database** (`netbet`). Partition provisioning runs against that database only. No parallel production databases; no environment drift.
