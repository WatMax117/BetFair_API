#!/usr/bin/env bash
# Stage 3 (VPS): Deploy risk-analytics-ui-web and validate (new bundle served, then manual browser check from client).
# Run on VPS: cd /opt/netbet && ./scripts/vps_stage3_deploy_and_validate.sh
# After script: hard refresh or incognito on client to confirm UI (Imbalance + Impedance).

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/opt/netbet}"
cd "$REPO_ROOT"

WEB_PORT="${WEB_PORT:-3000}"
WEB_URL="${WEB_URL:-http://localhost:3000}"

echo ""
echo "========== STAGE 3: Deploy risk-analytics-ui-web =========="
[ -d .git ] && git pull || echo "(Skipping git pull: not a git repo; ensure code is synced)"
docker compose -p netbet build --no-cache risk-analytics-ui-web
docker compose -p netbet up -d --force-recreate --no-deps risk-analytics-ui-web

echo "Waiting 10s for web container to start..."
sleep 10

echo ""
echo "========== Stage 3 validation =========="

# Confirm the UI bundle is served (200 and HTML with root)
echo "--- 3.1: UI bundle served (HTTP 200, HTML) ---"
RESP=$(curl -sS -w "\n%{http_code}" "$WEB_URL/")
BODY=$(echo "$RESP" | head -n -1)
CODE=$(echo "$RESP" | tail -n 1)
if [ "$CODE" != "200" ]; then
  echo "FAIL: GET $WEB_URL/ returned $CODE"
  exit 1
fi
if ! echo "$BODY" | grep -q '<div id="root">'; then
  echo "WARN: Response may not be the SPA (no #root). Code was 200."
fi
echo "OK: UI returned HTTP 200"

# Optional: build timestamp / version (if added to index.html later)
# if echo "$BODY" | grep -q 'data-build'; then echo "OK: build marker present"; fi

echo ""
echo "========== Stage 3 deploy complete =========="
echo "Next: From a client machine, open http://<VPS_IP>/ (or :$WEB_PORT if direct)."
echo "  - Hard refresh (Ctrl+F5 / Cmd+Shift+R) or use Incognito to load the new bundle."
echo "  - Confirm: Imbalance unchanged; 'Impedance (norm) (H/A/D)' when 'Include Impedance' is enabled; separate charts/columns."
