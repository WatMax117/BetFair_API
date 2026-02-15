#!/bin/bash
# Diagnostic script for impedance rendering issue
# Run on VPS: bash scripts/diagnose_impedance_rendering.sh

set -e

echo "=========================================="
echo "Impedance Rendering Diagnostic"
echo "=========================================="
echo ""

echo "Step 1: Test API timeseries endpoint with include_impedance=true"
echo "----------------------------------------"
echo "Testing: GET /api/events/{market_id}/timeseries?include_impedance=true"
echo ""
echo "First, get a market_id from recent snapshots:"
MARKET_ID=$(docker exec netbet-postgres psql -U netbet -d netbet -t -c "
SELECT market_id 
FROM rest_ingest.market_book_snapshots 
WHERE snapshot_at > NOW() - INTERVAL '24 hours' 
LIMIT 1;
" 2>/dev/null | tr -d ' ' || echo "")

if [ -z "$MARKET_ID" ]; then
    echo "⚠ No recent market_id found. Using example: 1.123456789"
    MARKET_ID="1.123456789"
else
    echo "Found market_id: $MARKET_ID"
fi
echo ""

echo "Step 2: Call API endpoint with include_impedance=true"
echo "----------------------------------------"
FROM_TS=$(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-24H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo "")
TO_TS=$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo "")

curl -s "http://127.0.0.1:8000/events/${MARKET_ID}/timeseries?from_ts=${FROM_TS}&to_ts=${TO_TS}&include_impedance=true&interval_minutes=15" | \
    jq -r 'if type == "array" then 
        "Response is array with \(length) points" + 
        (if length > 0 then 
            "\nFirst point keys: \(.[0] | keys | join(", "))" +
            "\nHas impedanceNorm: \(.[0] | has("impedanceNorm"))" +
            "\nHas impedance: \(.[0] | has("impedance"))" +
            (if .[0].impedanceNorm then 
                "\nimpedanceNorm values: \(.[0].impedanceNorm | to_entries | map("\(.key): \(.value)") | join(", "))" 
            else "" end)
        else "" end)
    else 
        "Response is not an array: \(type)" 
    end' 2>/dev/null || echo "API call failed or jq not installed"
echo ""

echo "Step 3: Check database for impedance columns"
echo "----------------------------------------"
docker exec netbet-postgres psql -U netbet -d netbet -c "
SELECT 
    column_name,
    data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'market_derived_metrics'
  AND column_name LIKE '%impedance%'
ORDER BY column_name;
" 2>&1 || echo "Query failed"
echo ""

echo "Step 4: Check if impedance data exists in market_derived_metrics"
echo "----------------------------------------"
docker exec netbet-postgres psql -U netbet -d netbet -c "
SELECT 
    COUNT(*) as total_rows,
    COUNT(home_impedance_norm) as rows_with_home_imp,
    COUNT(away_impedance_norm) as rows_with_away_imp,
    COUNT(draw_impedance_norm) as rows_with_draw_imp,
    MAX(snapshot_at) as latest_snapshot
FROM public.market_derived_metrics
WHERE snapshot_at > NOW() - INTERVAL '24 hours';
" 2>&1 || echo "Query failed"
echo ""

echo "Step 5: Sample impedance values from recent snapshots"
echo "----------------------------------------"
docker exec netbet-postgres psql -U netbet -d netbet -c "
SELECT 
    market_id,
    snapshot_at,
    home_impedance_norm,
    away_impedance_norm,
    draw_impedance_norm
FROM public.market_derived_metrics
WHERE snapshot_at > NOW() - INTERVAL '24 hours'
  AND (home_impedance_norm IS NOT NULL 
       OR away_impedance_norm IS NOT NULL 
       OR draw_impedance_norm IS NOT NULL)
ORDER BY snapshot_at DESC
LIMIT 5;
" 2>&1 || echo "Query failed"
echo ""

echo "=========================================="
echo "Summary"
echo "=========================================="
echo ""
echo "If API returns impedanceNorm:"
echo "  - Frontend should receive it when includeImpedance=true"
echo "  - Check browser console for impedance data in response"
echo ""
echo "If API does not return impedanceNorm:"
echo "  - Check if database has impedance columns"
echo "  - Check if impedance data exists in market_derived_metrics"
echo "  - Verify rest-client is computing impedance"
echo ""
echo "If frontend receives data but doesn't render:"
echo "  - Check browser console for errors"
echo "  - Verify 'Include Impedance' checkbox is checked"
echo "  - Check hasImpedance condition in EventDetail.tsx"
echo ""
