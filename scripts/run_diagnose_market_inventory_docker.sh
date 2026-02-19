#!/bin/bash
# Run diagnose_market_inventory.py inside Docker container (VPS).
# Generates comprehensive market inventory diagnostics.

set -e
cd "$(dirname "$0")/.."
set -a
[ -f .env ] && source .env 2>/dev/null || true
set +a

DATE="${1:-2026-02-16}"
OUTPUT_DIR="${DIAGNOSTICS_OUTPUT_DIR:-/opt/netbet/data_exports/diagnostics}"

export POSTGRES_HOST="${POSTGRES_HOST:-netbet-postgres}"
export POSTGRES_DB="${POSTGRES_DB:-netbet}"
export POSTGRES_USER="${POSTGRES_USER:-netbet}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-}"
export PGOPTIONS="${PGOPTIONS:--c search_path=public,stream_ingest}"

if [ -z "$POSTGRES_PASSWORD" ]; then
  echo "ERROR: POSTGRES_PASSWORD not set in .env"
  exit 1
fi

echo "Running market inventory diagnostics for date: $DATE"
echo "Output directory: $OUTPUT_DIR"

docker run --rm --network netbet_default \
  -e POSTGRES_HOST -e POSTGRES_DB -e POSTGRES_USER -e POSTGRES_PASSWORD -e PGOPTIONS \
  -v "$(pwd)/data_exports:/opt/netbet/data_exports" \
  -v "$(pwd)/scripts:/opt/netbet/scripts" \
  -w /opt/netbet \
  python:3.11-slim \
  bash -c "
    pip install psycopg2-binary pandas -q && \
    python scripts/diagnose_market_inventory.py --date $DATE --output-dir $OUTPUT_DIR
  "
