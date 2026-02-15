#!/bin/bash
# Run Book Risk L3 export on VPS (Docker + Python 3.11 with pandas/pyarrow)
# Usage: ./run_export_book_risk_l3_vps.sh [--market-ids 1.253489253] [--date-from YYYY-MM-DD] [--date-to YYYY-MM-DD]

cd /opt/netbet
set -a
[ -f .env ] && source .env 2>/dev/null
[ -f auth-service/.env ] && source auth-service/.env 2>/dev/null || true
set +a

export POSTGRES_HOST=netbet-postgres
export PGOPTIONS="-c search_path=public"
export POSTGRES_USER="${POSTGRES_REST_WRITER_USER:-netbet_rest_writer}"
export POSTGRES_PASSWORD="${POSTGRES_REST_WRITER_PASSWORD}"
export POSTGRES_DB="${POSTGRES_DB:-netbet}"

if [ -z "$POSTGRES_PASSWORD" ]; then
  echo "ERROR: POSTGRES_REST_WRITER_PASSWORD not set in .env or auth-service/.env"
  exit 1
fi

# One-off Python container with pandas/pyarrow; output to /opt/netbet/data_exports/book_risk_l3
# Pass date range and env; user can override with --date-from, --date-to, --market-ids
ARGS=("--date-from" "${EXPORT_DATE_FROM:-2026-02-01}" "--date-to" "${EXPORT_DATE_TO:-2026-02-03}" "--env" "${EXPORT_ENV:-vps}")
# If user passed args, append (last wins for overlapping keys)
ARGS+=("$@")

docker run --rm --network netbet_default \
  -e POSTGRES_HOST -e POSTGRES_DB -e POSTGRES_USER -e POSTGRES_PASSWORD -e PGOPTIONS \
  -v /opt/netbet:/opt/netbet -w /opt/netbet \
  python:3.11-slim \
  bash -c 'pip install pandas pyarrow psycopg2-binary -q && python scripts/export_book_risk_l3.py "$@"' \
  -- "${ARGS[@]}"
