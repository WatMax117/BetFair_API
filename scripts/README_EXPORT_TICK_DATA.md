# Tick-level streaming data export

Full export of all tick-level price and liquidity data from the Betfair Streaming API for every market stored in `stream_ingest.ladder_levels` (and optionally all markets in `public.markets`).

## Data source

- **Tick data:** `stream_ingest.ladder_levels` (back/lay ladder levels 0–7 per snapshot) and `stream_ingest.traded_volume`
- **Metadata:** `public.markets`, `public.events`, `public.runners`, `stream_ingest.market_lifecycle_events` (for market status / in_play)

All timestamps are normalized to UTC.

## Requirements

```bash
pip install psycopg2-binary pandas pyarrow
```

- **psycopg2-binary** – required
- **pandas** – required for index CSV and Parquet
- **pyarrow** – required for Parquet output

## Usage

```bash
# Default: Parquet under data_exports/tick_export/
python scripts/export_tick_data.py --output-dir data_exports/tick_export

# JSONL per market
python scripts/export_tick_data.py --output-dir data_exports/tick_export --format jsonl

# Resume after interruption (checkpoint by last processed market_id)
python scripts/export_tick_data.py --output-dir data_exports/tick_export --resume

# Include in index all stored markets (even with zero ticks)
python scripts/export_tick_data.py --output-dir data_exports/tick_export --include-markets-without-ticks
```

## Database connection

Set environment variables (same pattern as other export scripts):

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_HOST` | localhost | PostgreSQL host |
| `POSTGRES_PORT` | 5432 | Port |
| `POSTGRES_DB` | netbet | Database name |
| `POSTGRES_USER` | netbet | User |
| `POSTGRES_PASSWORD` | (empty) | Password |
| `PGOPTIONS` | `-c search_path=public,stream_ingest` | Must include `stream_ingest` for ladder/traded tables |

Example (VPS / Docker):

```bash
export POSTGRES_HOST=netbet-postgres
export POSTGRES_DB=netbet
export POSTGRES_USER=netbet
export POSTGRES_PASSWORD=your_password
export PGOPTIONS="-c search_path=public,stream_ingest"
python scripts/export_tick_data.py --output-dir data_exports/tick_export
```

Or using the run script (reads `.env` for credentials):

```bash
./scripts/run_export_tick_data.sh
# With options:
./scripts/run_export_tick_data.sh --format jsonl --resume --include-markets-without-ticks
```

Docker one-off (e.g. from host where DB is in Docker):

```bash
docker run --rm --network netbet_default \
  -e POSTGRES_HOST=netbet-postgres -e POSTGRES_DB=netbet -e POSTGRES_USER=netbet -e POSTGRES_PASSWORD \
  -e PGOPTIONS="-c search_path=public,stream_ingest" \
  -v "$(pwd)/data_exports:/opt/netbet/data_exports" -w /opt/netbet \
  python:3.11-slim \
  bash -c 'pip install pandas pyarrow psycopg2-binary -q && python scripts/export_tick_data.py --output-dir data_exports/tick_export'
```

## Output layout

```
<output-dir>/
  index.csv                 # Mandatory index (see below)
  execution_report.txt      # Markets count, total ticks, period, size
  markets/
    marketId=1.23456789.parquet   # or .jsonl
    marketId=1.23456789_metadata.json   # if --export-metadata (default)
  .export_tick_checkpoint   # Last processed market_id (for --resume)
```

### index.csv columns

| Column | Description |
|--------|-------------|
| market_id | Betfair market ID |
| event_id | Event ID |
| first_tick_timestamp | First tick publish_time (UTC ISO) |
| last_tick_timestamp | Last tick publish_time (UTC ISO) |
| total_tick_records | Number of tick rows in the file |
| total_messages | Distinct publish_time count |
| file_path | Path relative to output dir (e.g. markets/marketId=1.2.parquet) |
| file_size_bytes | File size |
| checksum | SHA-256 hex of file |

### Tick record shape (normalized)

Each tick row (Parquet column / JSONL field) has:

| Field | Description |
|-------|-------------|
| received_at | Ingestion time (UTC) |
| publish_time | Betfair stream publish time (UTC) |
| market_id | Market ID |
| selection_id | Runner selection ID |
| side | BACK or LAY (null for traded-only rows) |
| price | Odds (price level) |
| size | Available liquidity at that price (or traded size for record_type=traded) |
| traded_volume | Filled for traded updates; null for ladder |
| change_type | "update" (snapshot/delta not distinguished in DB) |
| level | Ladder level 0–7 (null for traded) |
| record_type | "ladder" or "traded" |
| in_play | Null (not stored per-tick) |
| sequence | Level for ladder; ordering sequence |

Uniqueness of tick rows: `(market_id, selection_id, side, price, publish_time, level)` for ladder; `(market_id, selection_id, price, publish_time)` for traded. Order: ascending `publish_time`, then record_type, then level.

### Metadata JSON (per market)

When `--export-metadata` (default): for each market with tick data, `marketId=<id>_metadata.json` contains:

- marketId, eventId, eventTypeId, marketName, marketType, marketStartTime, marketStatus, inPlay, numberOfRunners
- runners: list of { selectionId, runnerName, handicap }

## Resume behaviour

- `--resume` reads `.export_tick_checkpoint` and skips all markets up to and including the last written market_id, then continues.
- Checkpoint is updated after each market. Safe to re-run with `--resume` after a crash or Ctrl+C.

## Completeness

- By default, only markets that have at least one row in `stream_ingest.ladder_levels` are exported.
- Use `--include-markets-without-ticks` to include every market in `public.markets` in the index; those with no ticks get an empty data file and zero counts.
- Every market that has tick data is written to the index with a valid file_path and checksum.

## Execution report

`execution_report.txt` contains:

- Markets count
- Total tick records
- Total messages (distinct publish_time)
- Period covered (first/last tick timestamps)
- Total size of data files (bytes)
- Output format and directory

## Consolidated CSV (single flat file)

After exporting per-market Parquet/JSONL, you can produce one flat CSV for analysis:

```bash
python scripts/consolidate_tick_data.py --export-dir data_exports/tick_export
```

This reads all `markets/*.parquet` or `markets/*.jsonl` and the index, joins metadata from `marketId=<id>_metadata.json`, deduplicates (by market_id + selection_id + side + level + publish_time + sequence), sorts globally (publish_time, market_id, selection_id, side, level, sequence), and writes:

- **consolidated_ticks.csv** – UTF-8, header, strict column schema (received_at, publish_time, market_id, event_id, selection_id, side, level, price, size, traded_volume, in_play, change_type, sequence, record_type, market_status, market_start_time, market_type, runner_name).
- **consolidation_report.txt** – markets processed, rows written, duplicates removed, earliest/latest publish_time, file size, duration.

**Single-day trial (recommended first):** limit output to one UTC calendar day for a small, reviewable file:

```bash
python scripts/consolidate_tick_data.py --export-dir data_exports/tick_export --date 2024-01-15
```

- **Output:** `consolidated_ticks_2024_01_15.csv` (only ticks with `publish_time` in `[2024-01-15T00:00:00Z, 2024-01-16T00:00:00Z)`).
- **Report:** `consolidation_report_2024_01_15.txt` with: selected UTC date, markets included, total rows read (after date filter), rows before dedupe, duplicates removed, final rows written, earliest/latest publish_time, file size, duration, distinct market_id count, and date validation (all rows in range).
- Same schema, sort order, and deduplication as the full run. Use this to validate structure and quality before running a full or week-long consolidation.

Options:

- `--date YYYY-MM-DD` – single UTC day only (output and report use that date in the filename).
- `--chunk-rows N` – process in chunks of N rows to limit memory (default 1.5M).
- `--partition-by-month` – if the final CSV is larger than 8 GB, also write year-month files (e.g. `consolidated_ticks_2024_01.csv`).

Validation: total rows in the consolidated CSV should equal the sum of `total_tick_records` in index.csv (excluding zero-tick markets); any mismatch is logged.

## Direct consolidation from PostgreSQL (one-day validation)

For quick validation without filesystem export, generate a consolidated CSV directly from PostgreSQL:

```bash
# Inside Docker container (VPS)
python scripts/consolidate_tick_data_direct.py --date 2026-02-16 --output-dir /data_exports
```

Or using the Docker wrapper script:

```bash
./scripts/run_consolidate_direct_docker.sh 2026-02-16
```

**What it does:**
- Single SQL query (UNION of `stream_ingest.ladder_levels` + `stream_ingest.traded_volume`)
- Filters by `publish_time` for one UTC calendar day
- Joins metadata (event_id, runner_name, market_status, etc.)
- Server-side cursor for chunked extraction (avoids loading all rows into memory)
- Deduplicates and sorts in Python
- Writes CSV + report directly

**Output:**
- `consolidated_ticks_YYYY_MM_DD.csv` – same schema as filesystem-based consolidation
- `consolidation_report_YYYY_MM_DD.txt` – date window, rows written, duplicates removed, distinct markets, earliest/latest publish_time, file size, duration, date validation

**Use case:** Validation run to check data quality and structure before running the full export→consolidate pipeline.

**Performance:** Uses PostgreSQL server-side cursor (`DECLARE CURSOR`) with `itersize` for chunked streaming. Suitable for large datasets without memory issues.

## Compressed archive

After a run, create a compressed archive for delivery, e.g.:

```bash
cd data_exports
tar -czvf tick_export_$(date +%Y%m%d).tar.gz tick_export/
# or
zip -r tick_export_$(date +%Y%m%d).zip tick_export/
```
