# Database Inventory: NetBet PostgreSQL

**Extracted**: 2026-02-16  
**Database**: `netbet`  
**Schemas**: `public`, `stream_ingest`

---

## Executive Summary

- **Total tables**: 51 (excluding system tables)
- **Schemas**: 2 application schemas (`public`, `stream_ingest`)
- **Total data size**: ~400 MB (approximate)
- **Streaming ingestion**: `stream_ingest` schema (35 tables, primarily partitioned `ladder_levels`)
- **REST ingestion**: `public` schema (16 tables, including `market_book_snapshots`, `market_derived_metrics`)

---

## Top 20 Tables by Size

| Schema | Table | Kind | Approx Rows | Size (bytes) | Classification |
|--------|-------|------|-------------|--------------|----------------|
| `stream_ingest` | `ladder_levels_initial` | table | 713,282 | 138,969,088 | STREAMING |
| `public` | `traded_volume` | table | 640,308 | 130,449,408 | POSSIBLE_REST |
| `public` | `ladder_levels_20260206` | table | 374,820 | 82,444,288 | POSSIBLE_REST |
| `public` | `ladder_levels_20260205` | table | 293,190 | 57,483,264 | POSSIBLE_REST |
| `public` | `market_book_snapshots` | table | 11,893 | 14,893,056 | **REST** (has `source` column) |
| `public` | `market_derived_metrics` | table | 12,671 | 11,730,944 | **REST** (derived from snapshots) |
| `public` | `market_liquidity_history` | table | 17,266 | 2,711,552 | POSSIBLE_REST |
| `stream_ingest` | `market_liquidity_history` | table | 17,303 | 2,711,552 | STREAMING |
| `public` | `market_event_metadata` | table | 781 | 401,408 | POSSIBLE_REST |
| `public` | `market_lifecycle_events` | table | 599 | 204,800 | POSSIBLE_REST |
| `public` | `runners` | table | 1,089 | 196,608 | POSSIBLE_REST |
| `public` | `markets` | table | 433 | 172,032 | POSSIBLE_REST |
| `public` | `tracked_markets` | table | 293 | 147,456 | POSSIBLE_REST |
| `public` | `seen_markets` | table | 298 | 114,688 | POSSIBLE_REST |
| `public` | `events` | table | 200 | 73,728 | POSSIBLE_REST |
| `public` | `market_risk_snapshots` | table | -1 | 65,536 | POSSIBLE_REST |
| `public` | `flyway_schema_history` | table | -1 | 49,152 | System (migrations) |
| `stream_ingest` | `ladder_levels_20260303` | table | 0 | 16,384 | STREAMING |
| `stream_ingest` | `ladder_levels_20260304` | table | 0 | 16,384 | STREAMING |
| `stream_ingest` | `ladder_levels_20260305` | table | 0 | 16,384 | STREAMING |

---

## Schema Breakdown

### `stream_ingest` Schema (STREAMING)

**Purpose**: Java streaming API client ingestion (Betfair streaming data)

**Tables**:
- `ladder_levels` (partitioned table, parent) — 713,282 rows across partitions
- `ladder_levels_initial` — 713,282 rows (main data partition)
- `ladder_levels_20260216` through `ladder_levels_20260318` — date-partitioned tables (mostly empty, future partitions)
- `market_liquidity_history` — 17,303 rows

**Key characteristics**:
- Time-series structure (partitioned by date)
- High-volume inserts (ladder price updates)
- Columns: `market_id`, `selection_id`, `side`, `level`, `price`, `size`, `publish_time`, `received_time`
- No explicit `source` column (schema name indicates streaming)

---

### `public` Schema (REST + Mixed)

**Purpose**: REST API ingestion and application metadata

#### REST-Written Tables (Confirmed)

1. **`market_book_snapshots`** (11,893 rows)
   - **Source indicator**: `source` column (default: `'rest_listMarketBook'`)
   - Contains: `snapshot_id`, `snapshot_at`, `market_id`, `raw_payload` (JSONB), `total_matched`, `inplay`, `status`, `depth_limit`, `source`, `capture_version`
   - **Writer**: REST API client (`betfair-rest-client`)

2. **`market_derived_metrics`** (12,671 rows)
   - **Source indicator**: Derived from `market_book_snapshots` (1:1 relationship via `snapshot_id`)
   - Contains: Risk metrics, best prices (L1/L2/L3), impedance, book risk L3, impedance inputs
   - **Writer**: REST API client (computed from snapshots)

#### Possible REST Tables (Schema-based classification)

- `market_event_metadata` (781 rows) — Market/event metadata
- `market_lifecycle_events` (599 rows) — Market status changes
- `market_liquidity_history` (17,266 rows) — Liquidity tracking
- `markets` (433 rows) — Market catalog
- `events` (200 rows) — Event catalog
- `runners` (1,089 rows) — Runner/selection catalog
- `tracked_markets` (293 rows) — Market tracking state
- `seen_markets` (298 rows) — Market discovery tracking
- `traded_volume` (640,308 rows) — Trade volume history
- `market_risk_snapshots` — Risk snapshots (empty or minimal)

#### Legacy/Historical Tables

- `ladder_levels` (partitioned table, parent) — Empty parent
- `ladder_levels_20260205`, `ladder_levels_20260206` — Date partitions (374k+ rows)
- `ladder_levels_initial` — Initial partition (empty)

**Note**: These `public.ladder_levels_*` tables appear to be legacy streaming data migrated to `public` before `stream_ingest` schema was created.

---

## Overlap Analysis: Same Logical Object Across Schemas

### 1. `ladder_levels` — Streaming vs Legacy

| Schema | Table | Rows | Classification |
|--------|-------|------|----------------|
| `stream_ingest` | `ladder_levels` | 713,282 | **STREAMING** (active) |
| `public` | `ladder_levels` | -1 (empty parent) | Legacy |
| `public` | `ladder_levels_20260205` | 293,190 | Legacy (historical) |
| `public` | `ladder_levels_20260206` | 374,820 | Legacy (historical) |

**Conclusion**: `stream_ingest.ladder_levels` is the active streaming ingestion table. `public.ladder_levels_*` are legacy partitions from before schema isolation.

### 2. `market_liquidity_history` — Dual Schema

| Schema | Table | Rows | Classification |
|--------|-------|------|----------------|
| `public` | `market_liquidity_history` | 17,266 | POSSIBLE_REST |
| `stream_ingest` | `market_liquidity_history` | 17,303 | **STREAMING** |

**Conclusion**: Both schemas have this table. Row counts are similar (~17k), suggesting both APIs may write liquidity history, or one is a copy/mirror. **Needs code review** to confirm writer.

**Columns** (both schemas):
- `market_id`, `publish_time`, `total_matched`, `max_runner_ltp`

**Differentiation**: No explicit `source` column. Schema name is the only indicator.

---

## Key Parameters Stored

### REST Ingestion (`public` schema)

**Market Snapshots** (`market_book_snapshots`):
- Raw JSON payload (`raw_payload` JSONB)
- Market state: `total_matched`, `inplay`, `status`, `depth_limit`
- Source metadata: `source` (default: `'rest_listMarketBook'`), `capture_version`

**Derived Metrics** (`market_derived_metrics`):
- **Risk**: `home_risk`, `away_risk`, `draw_risk`
- **Best prices L1**: `home_best_back`, `away_best_back`, `draw_best_back`, `home_best_lay`, etc.
- **Best prices L2/L3**: `home_back_odds_l2`, `home_back_size_l2`, `home_back_odds_l3`, `home_back_size_l3` (and away/draw)
- **L1 sizes**: `home_best_back_size_l1`, `away_best_back_size_l1`, etc.
- **Book Risk L3**: `home_book_risk_l3`, `away_book_risk_l3`, `draw_book_risk_l3`
- **Impedance**: `home_impedance`, `away_impedance`, `draw_impedance` (raw and normalized)
- **Impedance inputs**: `home_back_stake`, `home_back_odds`, `home_lay_stake`, `home_lay_odds` (and away/draw)

**Metadata** (`market_event_metadata`):
- Event/market names, competition, country, timezone
- Selection IDs: `home_selection_id`, `away_selection_id`, `draw_selection_id`
- Runner names: `home_runner_name`, `away_runner_name`, `draw_runner_name`
- Timestamps: `first_seen_at`, `last_seen_at`

### Streaming Ingestion (`stream_ingest` schema)

**Ladder Levels** (`stream_ingest.ladder_levels`):
- `market_id`, `selection_id`, `side` (B/L), `level` (0-N), `price`, `size`
- Timestamps: `publish_time`, `received_time`

**Liquidity History** (`stream_ingest.market_liquidity_history`):
- `market_id`, `publish_time`, `total_matched`, `max_runner_ltp`

---

## Classification Refinement

### Confirmed REST-Written

1. `public.market_book_snapshots` — Has `source` column = `'rest_listMarketBook'`
2. `public.market_derived_metrics` — Derived from `market_book_snapshots` (1:1 FK)

### Confirmed STREAMING-Written

1. `stream_ingest.ladder_levels` — Schema name + high-volume time-series pattern
2. `stream_ingest.ladder_levels_*` partitions — Date-partitioned streaming data

### Needs Code Review

1. `public.market_liquidity_history` vs `stream_ingest.market_liquidity_history` — Which API writes which?
2. `public.traded_volume` — Large table (640k rows), no `source` column
3. `public.market_event_metadata` — Metadata source unclear (REST catalog vs streaming)
4. `public.market_lifecycle_events` — Has `publish_time`/`received_time` (streaming-like), but in `public` schema

---

## Candidate Overlap Pairs

1. **`ladder_levels`**: `stream_ingest.ladder_levels` (active) vs `public.ladder_levels_*` (legacy)
2. **`market_liquidity_history`**: `public.market_liquidity_history` vs `stream_ingest.market_liquidity_history` (similar row counts, needs verification)

---

## Views

- `public.v_event_summary` — Event aggregation view
- `public.v_golden_audit` — Audit/summary view
- `public.v_market_top_prices` — Top prices view

---

## Recommendations

1. **Verify writers**: Check application code/config to confirm which API writes `public.market_liquidity_history` vs `stream_ingest.market_liquidity_history`
2. **Add source metadata**: Consider adding `source` or `ingested_by` columns to ambiguous tables
3. **Archive legacy**: Consider archiving `public.ladder_levels_*` partitions if no longer used
4. **Schema migration**: If `public` tables are REST-only, consider moving to `rest_ingest` schema (per DB_ARCHITECTURE.md)

---

## Files Generated

- `db_tables.csv` — Table inventory with sizes
- `db_dictionary.csv` — Column-level data dictionary
- `db_dictionary_with_comments.csv` — Dictionary with column comments (if any)
- `streaming_vs_rest_classification.csv` — Initial classification
- `schema_only.sql` — Schema-only SQL extract (3,091 lines)
