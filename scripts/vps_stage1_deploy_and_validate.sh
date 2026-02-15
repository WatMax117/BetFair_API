#!/usr/bin/env bash
# Stage 1 (VPS): Deploy betfair-rest-client and validate impedance (DB + logs).
# Run on VPS: cd /opt/netbet && ./scripts/vps_stage1_deploy_and_validate.sh
# Do not proceed to Stage 2 unless validation passes.
# Deployment is VPS-only (Linux); do not rely on Docker Desktop on Windows.

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/opt/netbet}"
cd "$REPO_ROOT"

POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-netbet-postgres}"
REST_CLIENT_CONTAINER="${REST_CLIENT_CONTAINER:-netbet-betfair-rest-client}"
SCHEMA="${MDM_SCHEMA:-public}"

# Set VALIDATE_ONLY=1 to skip deploy and only run validation (e.g. after waiting 15–20 min for first snapshot).
if [ "${VALIDATE_ONLY:-0}" != "1" ]; then
  # Require Postgres REST writer credentials so the REST client can write impedance (avoids "POSTGRES_PASSWORD not set; skipping 3-layer persistence").
  if [ -f .env ]; then
    if ! grep -qE '^POSTGRES_REST_WRITER_PASSWORD=.+' .env 2>/dev/null; then
      echo "ERROR: POSTGRES_REST_WRITER_PASSWORD is missing or empty in .env. Add it (see .env.example and STAGED_DEPLOY_AND_VALIDATE.md 'Stage 1 blocker: Postgres credentials')."
      exit 1
    fi
  else
    echo "ERROR: No .env file. Create /opt/netbet/.env with POSTGRES_REST_WRITER_* and other credentials (see .env.example)."
    exit 1
  fi
  echo ""
  echo "========== STAGE 1: Deploy betfair-rest-client =========="
  [ -d .git ] && git pull || echo "(Skipping git pull: not a git repo; ensure code is synced)"
  docker compose build --no-cache betfair-rest-client
  docker compose up -d --force-recreate --no-deps betfair-rest-client
  echo "Waiting 10s for container to start..."
  sleep 10
fi

echo ""
echo "========== Stage 1 validation =========="

# 1.1 DB: impedance columns exist (expect 6 rows)
echo "--- 1.1: Check impedance columns exist (expect 6 rows) ---"
COL_COUNT=$(docker exec -i "$POSTGRES_CONTAINER" psql -U netbet -d netbet -t -A -c "
SELECT COUNT(*)
FROM information_schema.columns
WHERE table_schema = '$SCHEMA'
  AND table_name = 'market_derived_metrics'
  AND column_name IN (
    'home_impedance', 'away_impedance', 'draw_impedance',
    'home_impedance_norm', 'away_impedance_norm', 'draw_impedance_norm'
  );
" | tr -d '\r\n')
if [ "${COL_COUNT:-0}" -lt 6 ]; then
  echo "FAIL: Expected 6 impedance columns, got ${COL_COUNT:-0}"
  exit 1
fi
echo "OK: 6 impedance columns present"

# 1.2 DB: at least one recent row with non-null impedance
echo ""
echo "--- 1.2: Recent rows with non-null impedance (last 7 days) ---"
RECENT_COUNT=$(docker exec -i "$POSTGRES_CONTAINER" psql -U netbet -d netbet -t -A -c "
SELECT COUNT(*) FROM ${SCHEMA}.market_derived_metrics
WHERE snapshot_at >= NOW() - INTERVAL '7 days'
  AND (home_impedance_norm IS NOT NULL OR away_impedance_norm IS NOT NULL OR draw_impedance_norm IS NOT NULL);
" | tr -d '\r\n')
if [ "${RECENT_COUNT:-0}" -lt 1 ]; then
  echo "FAIL: No recent rows with non-null impedance. Wait for at least one snapshot cycle (15–20 min) or widen interval."
  echo "Count: ${RECENT_COUNT:-0}"
  exit 1
fi
echo "OK: $RECENT_COUNT recent row(s) with non-null impedance"

# 1.3 Logs: [Impedance] lines
echo ""
echo "--- 1.3: REST client logs ([Impedance] lines) ---"
if docker logs "$REST_CLIENT_CONTAINER" --tail=200 2>&1 | grep -q '\[Impedance\]'; then
  echo "OK: [Impedance] lines found in last 200 log lines"
  docker logs "$REST_CLIENT_CONTAINER" --tail=200 2>&1 | grep '\[Impedance\]' | tail -5
else
  echo "WARN: No [Impedance] lines in last 200 log lines (may be OK if no markets processed yet)."
fi

echo ""
echo "========== Stage 1 complete. Proceed to Stage 2 only if validation passed. =========="
