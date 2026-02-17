#!/usr/bin/env bash
# Run from project root on VPS after: cd /path/to/project && git pull
# Usage: ./risk-analytics-ui/scripts/vps_deploy_replay_snapshot.sh [prod-host]
# Example: ./risk-analytics-ui/scripts/vps_deploy_replay_snapshot.sh https://158.220.83.195

set -e
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$PROJECT_ROOT"

COMPOSE_OPTS="-f docker-compose.yml -f risk-analytics-ui/docker-compose.yml"
PROD_HOST="${1:-}"

echo "=== Step 2: Create replay index ==="
docker exec -i netbet-postgres psql -U netbet -d netbet -f - < risk-analytics-ui/scripts/add_replay_snapshot_index.sql

echo "=== Verify index ==="
docker exec -i netbet-postgres psql -U netbet -d netbet -c "SELECT indexname FROM pg_indexes WHERE schemaname = 'stream_ingest' AND tablename = 'ladder_levels';" | grep -q idx_stream_ladder_market_publish && echo "Index idx_stream_ladder_market_publish present." || echo "WARN: Index not found."

echo "=== Step 3: Build ==="
docker compose $COMPOSE_OPTS build --no-cache

echo "=== Step 4: Restart ==="
docker compose $COMPOSE_OPTS down
docker compose $COMPOSE_OPTS up -d

echo "=== Containers ==="
docker ps

if [ -n "$PROD_HOST" ]; then
  echo "=== Step 5: Curl validation (host=$PROD_HOST) ==="
  echo "Meta:"
  curl -s "${PROD_HOST}/api/stream/events/1.253378204/meta" | head -c 500
  echo ""
  echo "Replay snapshot:"
  curl -s -o /dev/null -w "%{http_code}" "${PROD_HOST}/api/stream/events/1.253378204/replay_snapshot"
  echo " (HTTP status)"
else
  echo "=== Step 5: Skipped (pass prod-host to run curl validation, e.g. https://158.220.83.195) ==="
fi

echo "Done. Perform UI check on archived market."
