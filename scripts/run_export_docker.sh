#!/bin/bash
# Run Book Risk L3 export inside a Docker container (mounts /opt/netbet).
# Usage on VPS: bash scripts/run_export_docker.sh [--date-from YYYY-MM-DD] [--date-to YYYY-MM-DD] [--market-ids ID...] [--env vps]
# Default: 2026-02-06..2026-02-08, env=vps

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

docker run --rm --network netbet_default \
  -e POSTGRES_HOST -e POSTGRES_DB -e POSTGRES_USER -e POSTGRES_PASSWORD -e PGOPTIONS \
  -v /opt/netbet:/opt/netbet -w /opt/netbet \
  python:3.11-slim \
  bash -c 'pip install pandas pyarrow psycopg2-binary -q && python scripts/export_book_risk_l3.py --date-from 2026-02-06 --date-to 2026-02-08 --env vps "$@"' -- "$@"
