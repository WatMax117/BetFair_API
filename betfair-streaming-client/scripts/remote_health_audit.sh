#!/usr/bin/env bash
# Remote Server Health Audit – NetBet Betfair Streaming
# Run on the VPS (e.g. after SSH) from the project root, or set PROJECT_DIR.
# Usage: ./scripts/remote_health_audit.sh   OR   bash scripts/remote_health_audit.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-netbet-postgres}"
# Set STREAMING_CONTAINER if your container name differs (e.g. netbet_streaming-client_1)
STREAMING_CONTAINER="${STREAMING_CONTAINER:-$(docker ps -a --format '{{.Names}}' | grep -E 'stream|client|app' | grep -v postgres | head -1)}"

echo "========== 1. Docker Container Status =========="
docker ps -a
echo ""
echo "Expected active: netbet-streaming-client (or similar), netbet-postgres. Any 'ghost' containers above should be pruned."
echo ""

echo "========== 2. Database Size & Table Metrics =========="
docker exec "$POSTGRES_CONTAINER" psql -U netbet -d netbet -t -c "SELECT pg_size_pretty(pg_database_size('netbet'));"
echo "Table sizes (top tables):"
docker exec "$POSTGRES_CONTAINER" psql -U netbet -d netbet -c "
SELECT relname AS table_name, pg_size_pretty(pg_total_relation_size(relid)) AS total_size
FROM pg_catalog.pg_statio_user_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(relid) DESC;
"
echo ""

echo "========== 3. Partition Verification =========="
docker exec -i "$POSTGRES_CONTAINER" psql -U netbet -d netbet -f - < "$SCRIPT_DIR/verify_partitions.sql"
echo ""

echo "========== 4. Disk & Resource Usage =========="
echo "--- Disk (df -h) ---"
df -h
echo ""
echo "--- RAM (free -m) ---"
free -m
echo ""

echo "========== 5. Log Inspection (last 100 lines, WARN/ERROR) =========="
if [ -n "$STREAMING_CONTAINER" ]; then
  echo "--- Last 100 lines of $STREAMING_CONTAINER ---"
  docker logs "$STREAMING_CONTAINER" --tail 100 2>&1
  echo ""
  echo "--- WARN/ERROR lines ---"
  docker logs "$STREAMING_CONTAINER" --tail 500 2>&1 | grep -E 'WARN|ERROR' || true
else
  echo "STREAMING_CONTAINER not set or not found. Set it and re-run, or run: docker logs <streaming-container-name> --tail 100"
fi
echo ""

echo "========== Summary =========="
echo "Review above: (1) Prune any old/ghost containers with: docker container prune -f"
echo "             (2) Confirm ladder_levels_initial and daily partitions (ladder_levels_YYYYMMDD) with no overlaps"
echo "             (3) Confirm logs show no persistent batchUpdate/connection/telemetry failures"
