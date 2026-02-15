#!/bin/bash
cd /opt/netbet
set -a
[ -f .env ] && source .env 2>/dev/null
[ -f auth-service/.env ] && source auth-service/.env 2>/dev/null
set +a
export POSTGRES_HOST=netbet-postgres POSTGRES_DB=netbet POSTGRES_USER=netbet_rest_writer POSTGRES_PASSWORD=$POSTGRES_REST_WRITER_PASSWORD PGOPTIONS="-c search_path=public"
docker run --rm --network netbet_default -e POSTGRES_HOST -e POSTGRES_DB -e POSTGRES_USER -e POSTGRES_PASSWORD -e PGOPTIONS -v /opt/netbet:/opt/netbet -w /opt/netbet python:3.11-slim bash -c 'pip install psycopg2-binary -q && python scripts/debug_export_query.py'
