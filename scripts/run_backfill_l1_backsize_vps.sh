#!/bin/bash
# Run L1 backsize backfill on VPS
# Usage: ./run_backfill_l1_backsize_vps.sh [--dry-run] [--limit N] [--batch-size N]

cd /opt/netbet
set -a
[ -f .env ] && source .env
[ -f auth-service/.env ] && source auth-service/.env
set +a

export POSTGRES_HOST=netbet-postgres
export PGOPTIONS="-c search_path=public"
export POSTGRES_USER="${POSTGRES_REST_WRITER_USER:-netbet_rest_writer}"
export POSTGRES_PASSWORD="${POSTGRES_REST_WRITER_PASSWORD}"
export POSTGRES_DB="${POSTGRES_DB:-netbet}"

docker run --rm --network netbet_default \
  -v /opt/netbet/betfair-rest-client/backfill_l1_backsize.py:/app/backfill_l1_backsize.py:ro \
  -e POSTGRES_HOST -e POSTGRES_DB -e POSTGRES_USER -e POSTGRES_PASSWORD -e PGOPTIONS \
  netbet-betfair-rest-client:latest \
  python backfill_l1_backsize.py "$@"
