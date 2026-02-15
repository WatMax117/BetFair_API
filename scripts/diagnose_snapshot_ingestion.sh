#!/bin/bash
# Diagnostic script for snapshot ingestion issue
# Run on VPS: bash scripts/diagnose_snapshot_ingestion.sh

set -e

echo "=== Snapshot Ingestion Diagnostic ==="
echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""

# 1. Check container status
echo "--- Container Status ---"
docker ps --filter "name=betfair-rest-client" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" || echo "Container not found or Docker not accessible"
echo ""

# 2. Check container logs (last 100 lines)
echo "--- Container Logs (last 100 lines) ---"
docker logs --tail 100 netbet-betfair-rest-client 2>&1 | tail -50 || echo "Could not fetch logs"
echo ""

# 3. Check heartbeat files
echo "--- Heartbeat Files ---"
if docker exec netbet-betfair-rest-client test -f /app/data/heartbeat_alive 2>/dev/null; then
    echo "heartbeat_alive exists:"
    docker exec netbet-betfair-rest-client cat /app/data/heartbeat_alive 2>/dev/null || echo "Could not read heartbeat_alive"
    echo ""
    ALIVE_TS=$(docker exec netbet-betfair-rest-client stat -c %Y /app/data/heartbeat_alive 2>/dev/null || echo "0")
    NOW=$(date +%s)
    AGE=$((NOW - ALIVE_TS))
    echo "Age: ${AGE} seconds ($(($AGE / 60)) minutes)"
else
    echo "heartbeat_alive file NOT FOUND"
fi
echo ""

if docker exec netbet-betfair-rest-client test -f /app/data/heartbeat_success 2>/dev/null; then
    echo "heartbeat_success exists:"
    docker exec netbet-betfair-rest-client cat /app/data/heartbeat_success 2>/dev/null || echo "Could not read heartbeat_success"
    echo ""
    SUCCESS_TS=$(docker exec netbet-betfair-rest-client stat -c %Y /app/data/heartbeat_success 2>/dev/null || echo "0")
    NOW=$(date +%s)
    AGE=$((NOW - SUCCESS_TS))
    echo "Age: ${AGE} seconds ($(($AGE / 60)) minutes)"
else
    echo "heartbeat_success file NOT FOUND"
fi
echo ""

# 4. Check database: latest snapshot timestamps
echo "--- Database: Latest Snapshots ---"
docker exec netbet-postgres psql -U netbet -d netbet -c "
SELECT 
    COUNT(*) as total_snapshots,
    MAX(snapshot_at) as latest_snapshot_at,
    MIN(snapshot_at) as earliest_snapshot_at,
    COUNT(DISTINCT market_id) as distinct_markets,
    NOW() as current_time,
    EXTRACT(EPOCH FROM (NOW() - MAX(snapshot_at))) as seconds_since_latest
FROM rest_ingest.market_book_snapshots;
" 2>/dev/null || echo "Could not query database"
echo ""

# 5. Check recent snapshots (last 10)
echo "--- Recent Snapshots (last 10) ---"
docker exec netbet-postgres psql -U netbet -d netbet -c "
SELECT 
    snapshot_id,
    snapshot_at,
    market_id,
    total_matched,
    inplay,
    status
FROM rest_ingest.market_book_snapshots
ORDER BY snapshot_at DESC
LIMIT 10;
" 2>/dev/null || echo "Could not query database"
echo ""

# 6. Check derived metrics (latest)
echo "--- Latest Derived Metrics ---"
docker exec netbet-postgres psql -U netbet -d netbet -c "
SELECT 
    COUNT(*) as total_metrics,
    MAX(snapshot_at) as latest_metric_at,
    COUNT(DISTINCT market_id) as distinct_markets_with_metrics
FROM rest_ingest.market_derived_metrics;
" 2>/dev/null || echo "Could not query database"
echo ""

# 7. Check for errors in logs (grep for ERROR, WARNING, Exception)
echo "--- Recent Errors/Warnings in Logs ---"
docker logs --tail 500 netbet-betfair-rest-client 2>&1 | grep -i -E "(error|warning|exception|failed|fail)" | tail -20 || echo "No errors found or could not fetch logs"
echo ""

echo "=== Diagnostic Complete ==="
