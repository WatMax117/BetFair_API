# Data retention matrix — stream ingest and REST

**Purpose:** Document which datasets are stored, for how long, and what deletes/TTL jobs exist. Use DB queries in `scripts/confirm_stream_data_retention.sql` to confirm current state (no assumptions).

---

## 1. Datasets

| Dataset | Where stored | Description | Raw vs aggregate |
|--------|----------------|-------------|------------------|
| **Ticks (ladder levels)** | `stream_ingest.ladder_levels` | Per-tick level=0..7 back/lay (price, size) per selection; `publish_time`, `received_time`. Written by **stream API client** only. | Raw (tick-level) |
| **Liquidity snapshots** | `stream_ingest.market_liquidity_history` | One row per stream snapshot: `market_id`, `publish_time`, `total_matched`, `max_runner_ltp`. | Per-snapshot (not full book) |
| **15‑min aggregates** | Not stored | Derived at read time by Risk Analytics API from `stream_ingest.ladder_levels` (time-weighted medians, Book Risk, Impedance). | Derived only |
| **Raw REST snapshots** | `public.market_book_snapshots` | Full `raw_payload` (JSON) from REST `listMarketBook`. Written by **REST client** only. Stream API does **not** write here. | Raw (full snapshot) |

**Important:** The stream UI shows “No raw snapshot” for the **stream** source because the stream pipeline does not persist full raw payloads—only ladder_levels and market_liquidity_history. That is by design; it must **not** be conflated with “data is lost.”

---

## 2. Retention and TTL

| Dataset | Table(s) | Retention | Deletes / TTL / partition drops |
|--------|----------|-----------|----------------------------------|
| **Stream ticks** | `stream_ingest.ladder_levels` | **VPS (stream_ingest, non‑partitioned):** No automatic purge in current migration (002). Data retained until manual cleanup or future TTL. **Legacy (public, partitioned):** `scripts/purge_partitions.sql` drops **public** daily partitions older than **30 days** (UTC). | `betfair-streaming-client/scripts/purge_partitions.sql` — only affects **public.ladder_levels_YYYYMMDD**. Not applied to `stream_ingest.ladder_levels` if that table is non‑partitioned. |
| **Stream liquidity** | `stream_ingest.market_liquidity_history` | No documented TTL or cleanup in repo. | None found. |
| **REST raw snapshots** | `public.market_book_snapshots` | Not defined in this matrix; check REST client / cron. | Not in stream codebase. |
| **15‑min aggregates** | — | N/A (not stored). | — |

**Cron / cleanup tasks:** No cron or scheduled job is defined in this repo for `stream_ingest`. If production uses **partitioned** `stream_ingest.ladder_levels`, a purge equivalent to `purge_partitions.sql` would need to target that schema/table explicitly.

---

## 3. Confirmation queries

Run **database** queries to confirm, not assumptions:

- **Script:** `scripts/confirm_stream_data_retention.sql`
- Confirms: existence of stream_ingest tables, row counts, min/max publish_time and received_time, whether **completed events** (event_open_date in the past) have any tick data, REST snapshot existence, partition list (if any), and presence of provenance columns.

---

## 4. If only aggregates after event completion

If the system is designed to **keep only aggregates** (or drop raw/tick data) after event completion:

- This must be **explicit** in API/meta: e.g. `has_raw_stream`, `is_archived`, `retention_policy` (see API/meta section below).
- The UI must **adapt**: e.g. show “Tick data not retained after event close” instead of implying data loss.

---

## 5. Severity‑1 data loss (raw/tick should be retained but missing)

If raw/tick data is **supposed** to be retained but is **missing** for yesterday’s events:

1. Treat as **severity‑1 data loss**.
2. Identify: **first missing time**, **last successful ingest**, **failure mode** (client stopped, auth/rate limit, schema error, cleanup job, partition drop).
3. Runbook: `docs/DATA_LOSS_RUNBOOK_STREAM_INGEST.md`.

---

## 6. Provenance (ingest_source / client_version)

- **Goal:** Attribute writes to the **new stream API client** and audit ingestion health.
- **Add/confirm** in DB:
  - `stream_ingest.ladder_levels`: `ingest_source`, `client_version` (nullable; backfill optional).
  - `stream_ingest.market_liquidity_history`: `ingest_source`, `client_version` (nullable; backfill optional).
- **Migration:** `scripts/add_stream_ingest_provenance.sql`
- **Ingestion stats:** Use `ingest_source = 'stream_api'` (or agreed value) to report total records, distinct events, min/max event time, min/max ingest time for the new client only.
