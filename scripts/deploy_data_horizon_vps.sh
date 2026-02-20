#!/usr/bin/env bash
# Data-horizon ready-to-play: deploy API with /stream/data-horizon and run post-deploy checks.
# Run on VPS (e.g. ssh root@158.220.83.195) from project root, or: bash scripts/deploy_data_horizon_vps.sh [project_root]
# Usage: cd /opt/netbet && bash scripts/deploy_data_horizon_vps.sh
#    or: bash /path/to/deploy_data_horizon_vps.sh /opt/netbet

set -e
PROJECT_ROOT="${1:-/opt/netbet}"
cd "$PROJECT_ROOT"

echo "=== Pre-deploy (project: $PROJECT_ROOT) ==="
git pull
if ! grep -q 'data-horizon' risk-analytics-ui/api/app/stream_router.py; then
  echo "ERROR: risk-analytics-ui/api/app/stream_router.py does not contain data-horizon. Aborting."
  exit 1
fi
echo "Repo contains data-horizon in stream_router.py"

echo "=== Rebuild API image ==="
docker compose build --no-cache risk-analytics-ui-api

echo "=== Restart API container ==="
docker compose up -d risk-analytics-ui-api

echo "=== Waiting for API to be ready (15s) ==="
sleep 15

echo ""
echo "=== 1. Direct API (port 8000) ==="
CODE=$(curl -sS -o /tmp/dh_direct.json -w "%{http_code}" http://localhost:8000/stream/data-horizon)
if [ "$CODE" != "200" ]; then
  echo "FAIL: HTTP $CODE (expected 200)"
  cat /tmp/dh_direct.json | head -5
  exit 1
fi
echo "HTTP: $CODE"
head -5 /tmp/dh_direct.json

echo ""
echo "=== 2. OpenAPI ==="
OPENAPI_MATCH=$(curl -sS http://localhost:8000/openapi.json | grep -o '"/stream/data-horizon"' || true)
if [ "$OPENAPI_MATCH" != '"/stream/data-horizon"' ]; then
  echo "FAIL: /stream/data-horizon not found in openapi.json"
  exit 1
fi
echo "Found: $OPENAPI_MATCH"

echo ""
echo "=== 3. Via Apache (proxy) ==="
CODE_PROXY=$(curl -sS -o /tmp/dh_proxy.json -w "%{http_code}" http://127.0.0.1/api/stream/data-horizon)
if [ "$CODE_PROXY" != "200" ]; then
  echo "FAIL: HTTP $CODE_PROXY (expected 200)"
  cat /tmp/dh_proxy.json | head -5
  exit 1
fi
echo "HTTP: $CODE_PROXY"
head -5 /tmp/dh_proxy.json

echo ""
echo "=== All checks passed. Ready-to-play. ==="
