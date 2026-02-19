#!/usr/bin/env bash
# Deploy time-ordering fix (buckets ASC, chart left→right, bucket list top→bottom) to VPS.
# Run from project root on VPS after: cd /path/to/project && git pull
# Usage: ./risk-analytics-ui/scripts/vps_deploy_time_ordering.sh

set -e
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$PROJECT_ROOT"

COMPOSE_OPTS="-f docker-compose.yml -f risk-analytics-ui/docker-compose.yml"
MARKET_ID="${1:-1.253378204}"

echo "=== Build API + Web (time-ordering: buckets ASC, latest=last) ==="
docker compose $COMPOSE_OPTS build --no-cache risk-analytics-ui-api risk-analytics-ui-web

echo "=== Stop and start ==="
docker compose $COMPOSE_OPTS up -d --force-recreate risk-analytics-ui-api risk-analytics-ui-web

echo "=== Wait for API ==="
for i in 1 2 3 4 5 6 7 8 9 10; do
  if curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/stream/events/${MARKET_ID}/buckets" | grep -q 200; then
    echo "API ready."
    break
  fi
  if [ "$i" -eq 10 ]; then
    echo "WARN: API did not return 200 in time."
    exit 1
  fi
  sleep 2
done

echo "=== Validate buckets ASC (oldest first, latest = last) ==="
BUCKETS=$(curl -s "http://localhost:8000/stream/events/${MARKET_ID}/buckets")
if [ -z "$BUCKETS" ] || [ "$BUCKETS" = "[]" ]; then
  echo "No buckets returned (market may have no data). Order check skipped."
else
  FIRST=$(echo "$BUCKETS" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0]['bucket_start'] if d else '')" 2>/dev/null || true)
  LAST=$(echo "$BUCKETS" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[-1]['bucket_start'] if d else '')" 2>/dev/null || true)
  echo "  First (oldest): $FIRST"
  echo "  Last (latest):  $LAST"
  if [ -n "$FIRST" ] && [ -n "$LAST" ] && [ "$FIRST" \> "$LAST" ]; then
    echo "ERROR: Order is DESC (first > last). Expected ASC."
    exit 1
  fi
  echo "  Order OK (ASC)."
fi

echo "=== Containers ==="
docker ps --filter name=risk-analytics-ui

echo "Done. Perform UI check: chart left→right, bucket list top→bottom, last bucket = latest."
