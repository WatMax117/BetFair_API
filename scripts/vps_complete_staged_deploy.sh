#!/usr/bin/env bash
# Complete staged deploy (Steps 0–5) on the VPS. Resolves Stage 1 blocker via .env credentials.
# Run on VPS: cd /opt/netbet && ./scripts/vps_complete_staged_deploy.sh
#
# Prerequisites:
#   - Create /opt/netbet/.env from .env.example and set POSTGRES_*_PASSWORD to match Postgres roles.
#   - jq installed (apt install -y jq) for Stage 2.

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/opt/netbet}"
cd "$REPO_ROOT"

# --- Step 0: Update code ---
echo ""
echo "========== Step 0: Update code =========="
if [ -d .git ]; then
  git pull
else
  echo "(Not a git repo; ensure code is synced)"
fi

# --- Step 1: Require Postgres credentials ---
echo ""
echo "========== Step 1: Postgres credentials =========="
if [ ! -f .env ]; then
  echo "ERROR: No .env file."
  echo "  Create it: cp .env.example .env"
  echo "  Edit .env and set (must match ALTER ROLE ... PASSWORD in Postgres):"
  echo "    POSTGRES_REST_WRITER_USER=netbet_rest_writer"
  echo "    POSTGRES_REST_WRITER_PASSWORD=<REST_WRITER_PASSWORD>"
  echo "    POSTGRES_STREAM_WRITER_USER=netbet_stream_writer"
  echo "    POSTGRES_STREAM_WRITER_PASSWORD=<STREAM_WRITER_PASSWORD>"
  echo "    POSTGRES_ANALYTICS_READER_USER=netbet_analytics_reader"
  echo "    POSTGRES_ANALYTICS_READER_PASSWORD=<ANALYTICS_READER_PASSWORD>"
  exit 1
fi
for var in POSTGRES_REST_WRITER_PASSWORD POSTGRES_STREAM_WRITER_PASSWORD POSTGRES_ANALYTICS_READER_PASSWORD; do
  if ! grep -qE "^${var}=.+$" .env 2>/dev/null; then
    echo "ERROR: $var is missing or empty in .env. Edit .env and set real passwords (see .env.example)."
    exit 1
  fi
done
echo "OK: .env present and required credentials set"

# --- Step 2: Restart REST client only ---
echo ""
echo "========== Step 2: Restart REST client only =========="
docker compose up -d --force-recreate --no-deps betfair-rest-client
echo "Waiting 10s for container to start..."
sleep 10

# --- Step 3: Wait for data, then validate Stage 1 ---
echo ""
echo "========== Step 3: Wait for data, then validate Stage 1 =========="
echo "Wait 15–20 minutes for at least one snapshot cycle, then run Stage 1 validation."
read -r -p "Press Enter when ready to validate Stage 1 (or Ctrl+C to exit and run later: VALIDATE_ONLY=1 ./scripts/vps_stage1_deploy_and_validate.sh) ..."
VALIDATE_ONLY=1 ./scripts/vps_stage1_deploy_and_validate.sh

# --- Step 4: Stage 2 (API) ---
echo ""
echo "========== Step 4: Stage 2 (API) =========="
./scripts/vps_stage2_deploy_and_validate.sh

# --- Step 5: Stage 3 (Web/UI) ---
echo ""
echo "========== Step 5: Stage 3 (Web/UI) =========="
./scripts/vps_stage3_deploy_and_validate.sh

echo ""
echo "========== Staged deploy complete =========="
echo "From a client browser: hard refresh / incognito and confirm:"
echo "  - Imbalance (H/A/D) unchanged."
echo "  - 'Impedance (norm) (H/A/D)' visible when 'Include Impedance' is enabled."
echo "  - Separate charts and table columns for Imbalance vs Impedance."
