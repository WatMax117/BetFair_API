#!/bin/bash
# Fix schema mismatch and restart rest-client container
# Run on VPS: bash scripts/vps_fix_schema_and_restart.sh

set -e

cd /opt/netbet

echo "=== Fixing Schema Mismatch ==="
echo ""

# 1. Update docker-compose.yml to use public schema
echo "Updating docker-compose.yml..."
sed -i 's/PGOPTIONS=-c search_path=rest_ingest/PGOPTIONS=-c search_path=public/' docker-compose.yml

# Verify change
if grep -q "search_path=public" docker-compose.yml; then
    echo "✓ docker-compose.yml updated"
else
    echo "✗ Failed to update docker-compose.yml"
    exit 1
fi

echo ""

# 2. Stop and remove old containers
echo "Stopping old containers..."
docker compose stop betfair-rest-client 2>/dev/null || true
docker compose rm -f betfair-rest-client 2>/dev/null || true

# Also stop the test container if it exists
docker stop netbet-betfair-rest-client-run-* 2>/dev/null || true
docker rm netbet-betfair-rest-client-run-* 2>/dev/null || true

echo ""

# 3. Restart container with new configuration
echo "Starting container with corrected schema..."
docker compose up -d --force-recreate --no-deps betfair-rest-client

echo ""

# 4. Wait for container to start
echo "Waiting 10 seconds for container to initialize..."
sleep 10

# 5. Check container status
echo "=== Container Status ==="
docker ps --filter "name=betfair-rest-client" --format "table {{.Names}}\t{{.Status}}"

echo ""

# 6. Check logs for errors
echo "=== Recent Logs (checking for errors) ==="
docker logs --tail 30 netbet-betfair-rest-client 2>&1 | grep -i -E "(error|warning|exception|failed|postgres)" | tail -10 || echo "No errors found in recent logs"

echo ""

# 7. Wait a bit and check if new snapshots are being created
echo "Waiting 30 seconds, then checking for new snapshots..."
sleep 30

LATEST=$(docker exec netbet-postgres psql -U netbet -d netbet -t -c "SELECT MAX(snapshot_at) FROM market_book_snapshots;" 2>/dev/null | tr -d ' ')
echo "Latest snapshot timestamp: $LATEST"

echo ""
echo "=== Fix Complete ==="
echo ""
echo "Monitor logs with: docker logs -f netbet-betfair-rest-client"
echo "Check for new snapshots: docker exec netbet-postgres psql -U netbet -d netbet -c \"SELECT MAX(snapshot_at), COUNT(*) FROM market_book_snapshots;\""
