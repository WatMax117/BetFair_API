#!/bin/bash
# Run consolidate_tick_data_direct.py inside Docker container (VPS).
# Generates one-day consolidated CSV directly from PostgreSQL.

set -e
cd "$(dirname "$0")/.."
set -a
[ -f .env ] && source .env 2>/dev/null || true
set +a

DATE="${1:-2026-02-16}"
OUTPUT_DIR="${CONSOLIDATE_OUTPUT_DIR:-/data_exports}"

export POSTGRES_HOST="${POSTGRES_HOST:-netbet-postgres}"
export POSTGRES_DB="${POSTGRES_DB:-netbet}"
export POSTGRES_USER="${POSTGRES_USER:-netbet}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-}"
export PGOPTIONS="${PGOPTIONS:--c search_path=public,stream_ingest}"

if [ -z "$POSTGRES_PASSWORD" ]; then
  echo "ERROR: POSTGRES_PASSWORD not set in .env"
  exit 1
fi

echo "Running consolidation for date: $DATE"
echo "Output directory: $OUTPUT_DIR"

docker run --rm --network netbet_default \
  -e POSTGRES_HOST -e POSTGRES_DB -e POSTGRES_USER -e POSTGRES_PASSWORD -e PGOPTIONS \
  -v "$(pwd)/data_exports:/data_exports" \
  -v "$(pwd)/scripts:/opt/netbet/scripts" \
  -w /opt/netbet \
  python:3.11-slim \
  bash -c "
    pip install psycopg2-binary -q && \
    python scripts/consolidate_tick_data_direct.py --date $DATE --output-dir $OUTPUT_DIR
  "
