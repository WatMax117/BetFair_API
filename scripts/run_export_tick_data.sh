#!/bin/bash
# Run tick-level streaming data export (Parquet or JSONL per market + index + report).
# Usage: ./scripts/run_export_tick_data.sh [--output-dir path] [--format parquet|jsonl] [--resume]

set -e
cd "$(dirname "$0")/.."
set -a
[ -f .env ] && source .env 2>/dev/null || true
set +a

export POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
export POSTGRES_DB="${POSTGRES_DB:-netbet}"
export POSTGRES_USER="${POSTGRES_USER:-netbet}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-}"
export PGOPTIONS="${PGOPTIONS:--c search_path=public,stream_ingest}"

OUTPUT_DIR="${EXPORT_TICK_OUTPUT_DIR:-data_exports/tick_export}"
ARGS=("--output-dir" "$OUTPUT_DIR" "$@")

python scripts/export_tick_data.py "${ARGS[@]}"
