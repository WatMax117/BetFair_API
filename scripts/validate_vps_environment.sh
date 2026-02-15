#!/bin/bash
# VPS Environment Validation Script
# Run this from the project root on the VPS: bash scripts/validate_vps_environment.sh
# This performs the pre-verification checks before running the full build verification

set -e

echo "=========================================="
echo "VPS Environment Validation"
echo "=========================================="
echo ""

echo "Step 1: Confirm current working directory"
echo "----------------------------------------"
CURRENT_DIR=$(pwd)
echo "Current directory: $CURRENT_DIR"
echo ""

# Check if docker-compose.yml exists
if [ -f "docker-compose.yml" ]; then
    echo "✓ docker-compose.yml found in current directory"
else
    echo "✗ ERROR: docker-compose.yml NOT found in current directory"
    echo "  Please run this script from the project root where docker-compose.yml is located."
    exit 1
fi
echo ""

echo "Step 2: Verify the updated source exists on the VPS"
echo "----------------------------------------"
echo "Running: grep -R 'back and forward from now' ."
echo ""
SOURCE_GREP=$(grep -R "back and forward from now" . 2>/dev/null || echo "")
if [ -z "$SOURCE_GREP" ]; then
    echo "✗ NOT_FOUND: 'back and forward from now' NOT found in source code"
    echo "  The VPS source is not updated."
    echo ""
    echo "Checking if LeaguesAccordion.tsx exists..."
    if [ -f "risk-analytics-ui/web/src/components/LeaguesAccordion.tsx" ]; then
        echo "  File exists. Checking contents..."
        grep -n "Time window" risk-analytics-ui/web/src/components/LeaguesAccordion.tsx | head -3 || echo "  No 'Time window' found in file"
    else
        echo "  File does not exist at expected path"
    fi
    exit 1
else
    echo "✓ Found 'back and forward from now' in source code:"
    echo "$SOURCE_GREP" | head -5
fi
echo ""

echo "Step 3: Confirm Docker build context"
echo "----------------------------------------"
echo "Running: docker compose config | grep -A5 risk-analytics-ui-web"
echo ""
BUILD_CONTEXT=$(docker compose config 2>&1 | grep -A5 "risk-analytics-ui-web" || echo "")
if [ -z "$BUILD_CONTEXT" ]; then
    echo "✗ ERROR: Could not find risk-analytics-ui-web in docker compose config"
    echo "  Full config output:"
    docker compose config 2>&1 | tail -20
    exit 1
else
    echo "$BUILD_CONTEXT"
    echo ""
    # Extract and verify build context path
    CONTEXT_PATH=$(echo "$BUILD_CONTEXT" | grep -oP 'context:\s*\K[^\s]+' || echo "")
    if [ -n "$CONTEXT_PATH" ]; then
        echo "Build context path: $CONTEXT_PATH"
        # Check if it's the expected path
        if [[ "$CONTEXT_PATH" == *"risk-analytics-ui/web"* ]] || [[ "$CONTEXT_PATH" == *"risk-analytics-ui\\web"* ]]; then
            echo "✓ Build context appears correct (contains risk-analytics-ui/web)"
        else
            echo "⚠ WARNING: Build context may not point to expected location"
        fi
    fi
fi
echo ""

echo "Step 4: Confirm container currently running"
echo "----------------------------------------"
echo "Running: docker ps | grep risk-analytics-ui-web"
echo ""
CONTAINER_STATUS=$(docker ps | grep risk-analytics-ui-web || echo "")
if [ -z "$CONTAINER_STATUS" ]; then
    echo "⚠ Container is NOT currently running"
    echo "  Checking if container exists..."
    docker ps -a | grep risk-analytics-ui-web || echo "  Container does not exist"
else
    echo "✓ Container is running:"
    echo "$CONTAINER_STATUS"
fi
echo ""

echo "Step 5: Verify whether the running container contains the updated string"
echo "----------------------------------------"
echo "Running: docker exec risk-analytics-ui-web sh -c \"grep -R 'back and forward from now' /usr/share/nginx/html || echo NOT_FOUND\""
echo ""

# Check if container is running first
if docker ps | grep -q risk-analytics-ui-web; then
    CONTAINER_GREP=$(docker exec risk-analytics-ui-web sh -c "grep -R 'back and forward from now' /usr/share/nginx/html 2>/dev/null || echo NOT_FOUND" 2>&1 || echo "ERROR_EXECUTING")
    
    if [ "$CONTAINER_GREP" = "NOT_FOUND" ]; then
        echo "✗ NOT_FOUND: 'back and forward from now' NOT found in running container"
        echo "  The current image does not include the updated code."
        echo ""
        echo "Checking what files exist in container..."
        docker exec risk-analytics-ui-web sh -c "find /usr/share/nginx/html -name '*.js' -type f | head -5" 2>&1 || echo "  Could not list files"
    elif [ "$CONTAINER_GREP" = "ERROR_EXECUTING" ]; then
        echo "✗ ERROR: Could not execute command in container"
    else
        echo "✓ Found 'back and forward from now' in container:"
        echo "$CONTAINER_GREP" | head -3
    fi
else
    echo "⚠ Container is not running. Skipping container check."
    echo "  Start the container first: docker compose -p netbet up -d risk-analytics-ui-web"
fi
echo ""

echo "=========================================="
echo "Validation Summary"
echo "=========================================="
echo ""
echo "Please share the following outputs:"
echo ""
echo "1. Step 2 output (source grep):"
echo "   (Shown above)"
echo ""
echo "2. Step 3 output (build context):"
echo "   (Shown above)"
echo ""
echo "3. Step 5 output (container grep):"
echo "   (Shown above)"
echo ""
echo "=========================================="
