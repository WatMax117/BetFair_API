#!/usr/bin/env bash
# Final Production Deployment – Clean Slate (run on VPS after syncing code to /opt/netbet)
# Usage: from /opt/netbet run:  bash scripts/deploy_clean_slate.sh
# Or:    bash /opt/netbet/scripts/deploy_clean_slate.sh  (script will cd to /opt/netbet)

set -e
PROJECT_ROOT="${PROJECT_ROOT:-/opt/netbet}"
cd "$PROJECT_ROOT"
TELEMETRY_PORT="${TELEMETRY_PORT:-8081}"

echo "========== Step 1: Deep Clean (Legacy Removal) =========="
echo "Stopping and removing all containers..."
docker stop $(docker ps -aq) 2>/dev/null || true
docker rm $(docker ps -aq) 2>/dev/null || true
echo "Wiping all volumes..."
docker volume prune -f
echo "Removing old images and build cache..."
docker system prune -a -f
echo ""

echo "========== Step 2 & 3: Build & Launch =========="
docker compose up -d --build
echo "Waiting for Postgres to be ready..."
sleep 15
echo ""

echo "========== Step 4: Database Initialization =========="
echo "Creating today's and tomorrow's partitions..."
docker exec -i netbet-postgres psql -U netbet -d netbet -f - < scripts/manage_partitions.sql
echo ""
echo "Verifying partition structure..."
docker exec -i netbet-postgres psql -U netbet -d netbet -f - < scripts/verify_partitions.sql
echo ""

echo "========== Step 5: Final Verification =========="
echo "Tailing netbet-streaming-client logs for 20 seconds..."
timeout 20 docker logs -f netbet-streaming-client --tail 100 2>&1 || true
echo ""
echo "Telemetry (postgres_sink_inserted_rows):"
curl -s -u "admin:changeme" "http://localhost:${TELEMETRY_PORT}/metadata/telemetry" | head -100
echo ""
echo "========== Deployment script finished =========="
