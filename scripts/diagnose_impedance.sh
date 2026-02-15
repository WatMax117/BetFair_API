#!/bin/bash
# Diagnostic script for impedance data issue
# Run on VPS: bash scripts/diagnose_impedance.sh [market_id]

set -e

MARKET_ID="${1:-}"

echo "=== Impedance Diagnostic ==="
echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""

# 1. Check if impedance columns exist
echo "--- Database Schema: Impedance Columns ---"
docker exec netbet-postgres psql -U netbet -d netbet -c "
SELECT 
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'rest_ingest'
  AND table_name = 'market_derived_metrics'
  AND column_name LIKE '%impedance%'
ORDER BY column_name;
" 2>/dev/null || echo "Could not query schema"
echo ""

# 2. Check impedance data availability
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
    MAX(snapshot_at) as latest_snapshot_with_impedance
FROM rest_ingest.market_derived_metrics;
" 2>/dev/null || echo "Could not query database"
echo ""

# 3. Sample impedance values (latest 5 snapshots)
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
" 2>/dev/null || echo "Could not query database"
echo ""

# 4. If market_id provided, check specific market
if [ -n "$MARKET_ID" ]; then
    echo "--- Impedance Data for Market: $MARKET_ID ---"
    docker exec netbet-postgres psql -U netbet -d netbet -c "
    SELECT 
        snapshot_id,
        snapshot_at,
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
    WHERE market_id = '$MARKET_ID'
    ORDER BY snapshot_at DESC
    LIMIT 10;
    " 2>/dev/null || echo "Could not query database"
    echo ""
fi

# 5. Check API endpoint response (if API is accessible)
echo "--- Testing API Endpoint ---"
if [ -n "$MARKET_ID" ]; then
    echo "Testing: GET /api/events/$MARKET_ID/timeseries?include_impedance=true"
    curl -s "http://localhost:8000/events/$MARKET_ID/timeseries?include_impedance=true" | jq '.[0] | {snapshot_at, impedance, impedanceNorm}' 2>/dev/null || echo "Could not fetch API response or jq not available"
else
    echo "No market_id provided. To test API, run: bash scripts/diagnose_impedance.sh <market_id>"
fi
echo ""

# 6. Check for markets with impedance data
echo "--- Markets with Impedance Data ---"
docker exec netbet-postgres psql -U netbet -d netbet -c "
SELECT 
    market_id,
    COUNT(*) as snapshot_count,
    MAX(snapshot_at) as latest_snapshot,
    COUNT(CASE WHEN home_impedance IS NOT NULL THEN 1 END) as rows_with_impedance
FROM rest_ingest.market_derived_metrics
GROUP BY market_id
HAVING COUNT(CASE WHEN home_impedance IS NOT NULL THEN 1 END) > 0
ORDER BY latest_snapshot DESC
LIMIT 10;
" 2>/dev/null || echo "Could not query database"
echo ""

echo "=== Diagnostic Complete ==="
