#!/bin/bash
# Test API endpoint for impedance data
# Usage: bash scripts/test_api_impedance.sh [market_id]

set -e

MARKET_ID="${1:-}"

if [ -z "$MARKET_ID" ]; then
    echo "Usage: bash scripts/test_api_impedance.sh <market_id>"
    echo ""
    echo "First, get a market_id from the database:"
    docker exec netbet-postgres psql -U netbet -d netbet -c "
    SELECT market_id, event_name, MAX(snapshot_at) as latest_snapshot
    FROM rest_ingest.market_event_metadata e
    JOIN rest_ingest.market_derived_metrics d ON d.market_id = e.market_id
    GROUP BY market_id, event_name
    ORDER BY latest_snapshot DESC
    LIMIT 5;
    " 2>/dev/null || echo "Could not query database"
    exit 1
fi

echo "=== Testing API Endpoint for Impedance ==="
echo "Market ID: $MARKET_ID"
echo ""

# Test without impedance
echo "--- Test 1: Without impedance (default) ---"
curl -s "http://localhost:8000/events/$MARKET_ID/timeseries?limit=1" | jq '.[0] | keys' 2>/dev/null || curl -s "http://localhost:8000/events/$MARKET_ID/timeseries?limit=1"
echo ""

# Test with impedance=true
echo "--- Test 2: With include_impedance=true ---"
RESPONSE=$(curl -s "http://localhost:8000/events/$MARKET_ID/timeseries?include_impedance=true&limit=1")
echo "$RESPONSE" | jq '.[0] | {snapshot_at, has_impedance: (.impedance != null), has_impedanceNorm: (.impedanceNorm != null), impedance, impedanceNorm}' 2>/dev/null || echo "$RESPONSE"
echo ""

# Check if impedance fields are present
if echo "$RESPONSE" | jq -e '.[0].impedance != null' >/dev/null 2>&1; then
    echo "✓ Impedance field found in response"
    echo "$RESPONSE" | jq '.[0].impedance' 2>/dev/null
else
    echo "✗ Impedance field NOT found in response"
fi

if echo "$RESPONSE" | jq -e '.[0].impedanceNorm != null' >/dev/null 2>&1; then
    echo "✓ ImpedanceNorm field found in response"
    echo "$RESPONSE" | jq '.[0].impedanceNorm' 2>/dev/null
else
    echo "✗ ImpedanceNorm field NOT found in response"
fi

echo ""
echo "=== Test Complete ==="
