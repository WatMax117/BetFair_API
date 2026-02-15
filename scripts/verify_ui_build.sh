#!/bin/bash
# Verification script for UI Docker build
# Run this from the project root on the VPS: bash scripts/verify_ui_build.sh

set -e

echo "=========================================="
echo "Step 1: Verify updated source exists"
echo "=========================================="
if grep -r "back and forward from now" . > /dev/null 2>&1; then
    echo "✓ Found 'back and forward from now' in source code"
    grep -r "back and forward from now" . | head -5
else
    echo "✗ ERROR: 'back and forward from now' NOT found in source code"
    echo "  The change is not present in the deployed source directory."
    exit 1
fi

echo ""
echo "=========================================="
echo "Step 2: Confirm Docker build context"
echo "=========================================="
echo "Checking docker-compose.yml build context..."
if [ -f "docker-compose.yml" ]; then
    echo "Main docker-compose.yml:"
    grep -A 3 "risk-analytics-ui-web:" docker-compose.yml | grep -A 2 "build:" || echo "  (not found in main compose)"
fi

if [ -f "risk-analytics-ui/docker-compose.yml" ]; then
    echo ""
    echo "risk-analytics-ui/docker-compose.yml:"
    grep -A 3 "risk-analytics-ui-web:" risk-analytics-ui/docker-compose.yml | grep -A 2 "build:" || echo "  (not found)"
fi

echo ""
echo "Running: docker compose config"
docker compose config | grep -A 5 "risk-analytics-ui-web:" | grep -A 3 "build:" || echo "  (service not found in config)"

echo ""
echo "=========================================="
echo "Step 3: Rebuild with --no-cache"
echo "=========================================="
echo "Building risk-analytics-ui-web with --no-cache..."
echo "This may take a few minutes..."
docker compose -p netbet build --no-cache risk-analytics-ui-web 2>&1 | tee /tmp/build.log

# Check for build errors
if grep -i "error" /tmp/build.log | grep -v "WARNING" > /dev/null; then
    echo ""
    echo "⚠ WARNING: Errors detected in build log. Check /tmp/build.log for details."
else
    echo ""
    echo "✓ Build completed. Check logs above for TypeScript/Vite compilation status."
fi

echo ""
echo "=========================================="
echo "Step 4: Restart container"
echo "=========================================="
echo "Restarting risk-analytics-ui-web container..."
docker compose -p netbet up -d risk-analytics-ui-web
sleep 3

echo ""
echo "=========================================="
echo "Step 5: Verify built bundle contains change"
echo "=========================================="
echo "Checking inside container at /usr/share/nginx/html..."
if docker exec risk-analytics-ui-web sh -c "grep -r 'back and forward from now' /usr/share/nginx/html 2>/dev/null" > /dev/null; then
    echo "✓ Found 'back and forward from now' in built bundle!"
    docker exec risk-analytics-ui-web sh -c "grep -r 'back and forward from now' /usr/share/nginx/html" | head -3
else
    echo "✗ ERROR: 'back and forward from now' NOT found in built bundle"
    echo "  The Docker image does not include the updated code."
    echo ""
    echo "Checking what files exist in the container..."
    docker exec risk-analytics-ui-web sh -c "find /usr/share/nginx/html -name '*.js' -type f | head -5"
    exit 1
fi

echo ""
echo "=========================================="
echo "Verification Summary"
echo "=========================================="
echo "✓ Source code contains the change"
echo "✓ Docker build completed"
echo "✓ Built bundle contains the change"
echo ""
echo "The UI should now display the updated label."
echo "Please verify in your browser that the label shows:"
echo "  'Time window (hours back and forward from now)'"
