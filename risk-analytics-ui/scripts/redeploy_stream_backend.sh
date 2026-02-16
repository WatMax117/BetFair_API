#!/bin/bash
# Run this script ON THE VM after SSH, from the directory that contains risk-analytics-ui
# (e.g. repo root or risk-analytics-ui). Usage: ./risk-analytics-ui/scripts/redeploy_stream_backend.sh

set -e

echo "=== Stream backend redeploy (STALE_MINUTES=120) ==="

# Find project root (directory containing api/app/stream_data.py)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/../api/app/stream_data.py" ]; then
  PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
else
  echo "Error: api/app/stream_data.py not found relative to script. Run from repo root or risk-analytics-ui."
  exit 1
fi

cd "$PROJECT_DIR"
echo "Project dir: $PROJECT_DIR"

# 1. Pull latest
echo "--- Pulling latest code ---"
git pull

# 2. Confirm STALE_MINUTES
echo "--- Checking STALE_MINUTES in api/app/stream_data.py ---"
if grep -q "STALE_MINUTES = 120" api/app/stream_data.py; then
  echo "OK: STALE_MINUTES = 120 found"
else
  echo "WARNING: STALE_MINUTES = 120 not found. Current line:"
  grep "STALE_MINUTES" api/app/stream_data.py || true
  read -p "Continue anyway? (y/N) " -n 1 -r; echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then exit 1; fi
fi

# 3. Rebuild and restart (Docker Compose)
if [ -f "docker-compose.yml" ]; then
  echo "--- Rebuilding API image ---"
  docker compose build risk-analytics-ui-api
  echo "--- Restarting API container ---"
  docker compose up -d risk-analytics-ui-api
  echo "--- Container status ---"
  docker ps --filter name=risk-analytics-ui-api
  echo "--- Last 30 log lines ---"
  docker logs risk-analytics-ui-api --tail 30
elif [ -f "../docker-compose.yml" ] && [ -f "../risk-analytics-ui/docker-compose.yml" ]; then
  echo "--- Rebuilding from repo root ---"
  (cd .. && docker compose -f docker-compose.yml -f risk-analytics-ui/docker-compose.yml build risk-analytics-ui-api)
  (cd .. && docker compose -f docker-compose.yml -f risk-analytics-ui/docker-compose.yml up -d risk-analytics-ui-api)
  docker ps --filter name=risk-analytics-ui-api
  docker logs risk-analytics-ui-api --tail 30
else
  echo "Docker Compose not found in $PROJECT_DIR or parent. Restart API manually (systemd/uvicorn)."
  echo "Example: sudo systemctl restart risk-analytics-api"
  exit 1
fi

echo "=== Redeploy script finished. Validate in browser: /stream and check backend logs. ==="
