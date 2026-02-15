#!/bin/bash
# Master diagnostic script for VPS - Snapshot Ingestion & Impedance Issues
# Run on VPS via SSH: bash scripts/vps_diagnose_both_issues.sh
# Or: ssh user@vps "cd /opt/netbet && bash scripts/vps_diagnose_both_issues.sh"

set -e

echo "=========================================="
echo "Backend Issues Diagnostic - VPS Production"
echo "=========================================="
echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""

# Change to project directory if needed
cd "$(dirname "$0")/.." 2>/dev/null || true
PROJECT_DIR="${PROJECT_DIR:-/opt/netbet}"
cd "$PROJECT_DIR" 2>/dev/null || true

echo "Working directory: $(pwd)"
echo ""

# ============================================================================
# ISSUE 1: SNAPSHOT INGESTION
# ============================================================================

echo "=========================================="
echo "ISSUE 1: Snapshot Ingestion Status"
echo "=========================================="
echo ""

# 1. Container status
echo "--- Container Status ---"
if docker ps --filter "name=betfair-rest-client" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null; then
    echo ""
    CONTAINER_STATUS=$(docker inspect netbet-betfair-rest-client --format='{{.State.Status}}' 2>/dev/null || echo "not_found")
    echo "Container state: $CONTAINER_STATUS"
    if [ "$CONTAINER_STATUS" != "running" ]; then
        echo "⚠️  WARNING: Container is not running!"
        echo "Last exit code: $(docker inspect netbet-betfair-rest-client --format='{{.State.ExitCode}}' 2>/dev/null || echo 'N/A')"
    fi
else
    echo "⚠️  ERROR: Container 'netbet-betfair-rest-client' not found or Docker not accessible"
fi
echo ""

# 2. Heartbeat files
echo "--- Heartbeat Files ---"
if docker exec netbet-betfair-rest-client test -f /app/data/heartbeat_alive 2>/dev/null; then
    echo "✓ heartbeat_alive exists"
    ALIVE_CONTENT=$(docker exec netbet-betfair-rest-client cat /app/data/heartbeat_alive 2>/dev/null || echo "")
    echo "  Content: $ALIVE_CONTENT"
    ALIVE_TS=$(docker exec netbet-betfair-rest-client stat -c %Y /app/data/heartbeat_alive 2>/dev/null || echo "0")
    NOW=$(date +%s)
    AGE=$((NOW - ALIVE_TS))
    AGE_MIN=$((AGE / 60))
    echo "  Age: ${AGE} seconds (${AGE_MIN} minutes)"
    if [ $AGE -gt 1800 ]; then
        echo "  ⚠️  WARNING: Heartbeat is stale (>30 minutes)"
    elif [ $AGE -gt 900 ]; then
        echo "  ⚠️  CAUTION: Heartbeat is old (>15 minutes)"
    else
        echo "  ✓ Heartbeat is recent"
    fi
else
    echo "✗ heartbeat_alive file NOT FOUND"
fi

if docker exec netbet-betfair-rest-client test -f /app/data/heartbeat_success 2>/dev/null; then
    echo "✓ heartbeat_success exists"
    SUCCESS_CONTENT=$(docker exec netbet-betfair-rest-client cat /app/data/heartbeat_success 2>/dev/null || echo "")
    echo "  Content: $SUCCESS_CONTENT"
    SUCCESS_TS=$(docker exec netbet-betfair-rest-client stat -c %Y /app/data/heartbeat_success 2>/dev/null || echo "0")
    NOW=$(date +%s)
    AGE=$((NOW - SUCCESS_TS))
    AGE_MIN=$((AGE / 60))
    echo "  Age: ${AGE} seconds (${AGE_MIN} minutes)"
    if [ $AGE -gt 1800 ]; then
        echo "  ⚠️  WARNING: Success heartbeat is stale (>30 minutes)"
    fi
else
    echo "✗ heartbeat_success file NOT FOUND"
fi
echo ""

# 3. Database: Latest snapshot
echo "--- Database: Latest Snapshot Timestamp ---"
docker exec netbet-postgres psql -U netbet -d netbet -c "
SELECT 
    MAX(snapshot_at) as latest_snapshot_at,
    COUNT(*) as total_snapshots,
    COUNT(DISTINCT market_id) as distinct_markets,
    NOW() as current_time,
    EXTRACT(EPOCH FROM (NOW() - MAX(snapshot_at)))::int as seconds_since_latest,
    CASE 
        WHEN EXTRACT(EPOCH FROM (NOW() - MAX(snapshot_at))) > 1800 THEN 'STALE (>30 min)'
        WHEN EXTRACT(EPOCH FROM (NOW() - MAX(snapshot_at))) > 900 THEN 'WARNING (>15 min)'
        ELSE 'OK'
    END as status
FROM rest_ingest.market_book_snapshots;
" 2>/dev/null || echo "⚠️  Could not query database"
echo ""

# 4. Recent snapshots
echo "--- Recent Snapshots (last 10) ---"
docker exec netbet-postgres psql -U netbet -d netbet -c "
SELECT 
    snapshot_id,
    snapshot_at,
    market_id,
    total_matched,
    inplay,
    status,
    EXTRACT(EPOCH FROM (NOW() - snapshot_at))::int as age_seconds
FROM rest_ingest.market_book_snapshots
ORDER BY snapshot_at DESC
LIMIT 10;
" 2>/dev/null || echo "⚠️  Could not query database"
echo ""

# 5. Container logs (errors)
echo "--- Recent Errors/Warnings in Logs (last 20) ---"
docker logs --tail 500 netbet-betfair-rest-client 2>&1 | grep -i -E "(error|warning|exception|failed|fail|session)" | tail -20 || echo "No errors found or could not fetch logs"
echo ""

# ============================================================================
# ISSUE 2: IMPEDANCE DATA
# ============================================================================

echo "=========================================="
echo "ISSUE 2: Impedance Data Status"
echo "=========================================="
echo ""

# 1. Impedance column statistics
echo "--- Impedance Data Statistics ---"
docker exec netbet-postgres psql -U netbet -d netbet -c "
SELECT 
    COUNT(*) as total_rows,
    COUNT(home_impedance) as rows_with_home_impedance,
    COUNT(away_impedance) as rows_with_away_impedance,
    COUNT(draw_impedance) as rows_with_draw_impedance,
    COUNT(home_impedance_norm) as rows_with_home_impedance_norm,
    COUNT(away_impedance_norm) as rows_with_away_impedance_norm,
    COUNT(draw_impedance_norm) as rows_with_draw_impedance_norm,
    ROUND(100.0 * COUNT(home_impedance) / NULLIF(COUNT(*), 0), 2) as pct_with_impedance,
    MAX(snapshot_at) as latest_snapshot_with_impedance
FROM rest_ingest.market_derived_metrics;
" 2>/dev/null || echo "⚠️  Could not query database"
echo ""

# 2. Sample impedance values
echo "--- Sample Impedance Values (Latest 5) ---"
docker exec netbet-postgres psql -U netbet -d netbet -c "
SELECT 
    snapshot_id,
    snapshot_at,
    market_id,
    home_impedance,
    away_impedance,
    draw_impedance,
    home_impedance_norm,
    away_impedance_norm,
    draw_impedance_norm,
    home_back_stake,
    home_back_odds,
    home_lay_stake,
    home_lay_odds
FROM rest_ingest.market_derived_metrics
WHERE home_impedance IS NOT NULL
   OR away_impedance IS NOT NULL
   OR draw_impedance IS NOT NULL
ORDER BY snapshot_at DESC
LIMIT 5;
" 2>/dev/null || echo "⚠️  Could not query database"
echo ""

# 3. Recent snapshots WITHOUT impedance
echo "--- Recent Snapshots WITHOUT Impedance (last 10) ---"
docker exec netbet-postgres psql -U netbet -d netbet -c "
SELECT 
    snapshot_id,
    snapshot_at,
    market_id,
    home_impedance IS NULL as missing_home_impedance,
    away_impedance IS NULL as missing_away_impedance,
    draw_impedance IS NULL as missing_draw_impedance
FROM rest_ingest.market_derived_metrics
WHERE home_impedance IS NULL
   AND away_impedance IS NULL
   AND draw_impedance IS NULL
ORDER BY snapshot_at DESC
LIMIT 10;
" 2>/dev/null || echo "⚠️  Could not query database"
echo ""

# 4. Markets with impedance data
echo "--- Markets with Impedance Data ---"
docker exec netbet-postgres psql -U netbet -d netbet -c "
SELECT 
    market_id,
    COUNT(*) as total_snapshots,
    COUNT(CASE WHEN home_impedance IS NOT NULL THEN 1 END) as snapshots_with_impedance,
    MAX(snapshot_at) as latest_snapshot,
    ROUND(100.0 * COUNT(CASE WHEN home_impedance IS NOT NULL THEN 1 END) / NULLIF(COUNT(*), 0), 2) as pct_with_impedance
FROM rest_ingest.market_derived_metrics
GROUP BY market_id
HAVING COUNT(CASE WHEN home_impedance IS NOT NULL THEN 1 END) > 0
ORDER BY latest_snapshot DESC
LIMIT 10;
" 2>/dev/null || echo "⚠️  Could not query database"
echo ""

# 5. Test API endpoint (if we can find a market_id)
echo "--- Testing API Endpoint ---"
MARKET_ID=$(docker exec netbet-postgres psql -U netbet -d netbet -t -c "
SELECT market_id FROM rest_ingest.market_derived_metrics 
WHERE home_impedance IS NOT NULL 
ORDER BY snapshot_at DESC LIMIT 1;
" 2>/dev/null | tr -d ' ' || echo "")

if [ -n "$MARKET_ID" ]; then
    echo "Testing with market_id: $MARKET_ID"
    echo "Endpoint: GET /api/events/$MARKET_ID/timeseries?include_impedance=true"
    echo ""
    
    RESPONSE=$(curl -s "http://localhost:8000/events/$MARKET_ID/timeseries?include_impedance=true&limit=1" 2>/dev/null || echo "")
    if [ -n "$RESPONSE" ]; then
        if echo "$RESPONSE" | grep -q "impedance"; then
            echo "✓ Response contains 'impedance' field"
            echo "$RESPONSE" | head -c 500
            echo ""
        else
            echo "✗ Response does NOT contain 'impedance' field"
            echo "Response preview: $RESPONSE" | head -c 200
            echo ""
        fi
    else
        echo "⚠️  Could not fetch API response (API may not be accessible or market_id invalid)"
    fi
else
    echo "⚠️  No market_id found with impedance data to test API"
fi
echo ""

# 6. Check container logs for impedance computation
echo "--- Impedance Computation Logs (last 20) ---"
docker logs --tail 1000 netbet-betfair-rest-client 2>&1 | grep -i "impedance" | tail -20 || echo "No impedance logs found"
echo ""

echo "=========================================="
echo "Diagnostic Complete"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Review container logs: docker logs netbet-betfair-rest-client"
echo "2. Check API logs: docker logs risk-analytics-ui-api"
echo "3. Verify frontend is calling API with include_impedance=true"
echo "4. Check database schema: SELECT column_name FROM information_schema.columns WHERE table_name = 'market_derived_metrics' AND column_name LIKE '%impedance%';"
