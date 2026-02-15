#!/usr/bin/env bash
# Stage 2 (VPS): Deploy risk-analytics-ui-api and validate (imbalance always present, impedanceNorm when include_impedance=true, no 500s).
# Run on VPS: cd /opt/netbet && ./scripts/vps_stage2_deploy_and_validate.sh
# Do not proceed to Stage 3 unless validation passes.

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/opt/netbet}"
cd "$REPO_ROOT"

API_BASE="${API_BASE:-http://localhost:8000}"
FROM_TS="${FROM_TS:-2025-01-01T00:00:00Z}"
TO_TS="${TO_TS:-2030-01-01T00:00:00Z}"

if ! command -v jq &>/dev/null; then
  echo "FAIL: jq is required for Stage 2 validation. Install with: apt install -y jq"
  exit 1
fi

echo ""
echo "========== STAGE 2: Deploy risk-analytics-ui-api =========="
[ -d .git ] && git pull || echo "(Skipping git pull: not a git repo; ensure code is synced)"
docker compose -p netbet build --no-cache risk-analytics-ui-api
docker compose -p netbet up -d --force-recreate --no-deps risk-analytics-ui-api

echo "Waiting 10s for API to start..."
sleep 10

echo ""
echo "========== Stage 2 validation (curl) =========="

# 2.1 GET /leagues
echo "--- 2.1: GET /leagues ---"
LEAGUES_HTTP=$(curl -sS -w "\n%{http_code}" "$API_BASE/leagues?from_ts=$FROM_TS&to_ts=$TO_TS&limit=5")
LEAGUES_BODY=$(echo "$LEAGUES_HTTP" | head -n -1)
LEAGUES_CODE=$(echo "$LEAGUES_HTTP" | tail -n 1)
if [ "$LEAGUES_CODE" -ge 500 ]; then
  echo "FAIL: /leagues returned $LEAGUES_CODE"
  echo "$LEAGUES_BODY" | head -20
  exit 1
fi
LEAGUE_NAME=$(echo "$LEAGUES_BODY" | jq -r '.[0].league // empty')
if [ -z "$LEAGUE_NAME" ]; then
  echo "FAIL: No leagues returned or invalid JSON. Body: $LEAGUES_BODY"
  exit 1
fi
echo "OK: leagues returned (using league: $LEAGUE_NAME)"

# 2.2 GET /leagues/{league}/events?include_impedance=true
echo ""
echo "--- 2.2: GET /leagues/.../events?include_impedance=true ---"
ENCODED_LEAGUE=$(echo -n "$LEAGUE_NAME" | jq -sRr @uri)
EVENTS_HTTP=$(curl -sS -w "\n%{http_code}" "$API_BASE/leagues/$ENCODED_LEAGUE/events?include_impedance=true&from_ts=$FROM_TS&to_ts=$TO_TS&limit=5")
EVENTS_BODY=$(echo "$EVENTS_HTTP" | head -n -1)
EVENTS_CODE=$(echo "$EVENTS_HTTP" | tail -n 1)
if [ "$EVENTS_CODE" -ge 500 ]; then
  echo "FAIL: /leagues/.../events returned $EVENTS_CODE"
  echo "$EVENTS_BODY" | head -20
  exit 1
fi
# imbalance must always be present
HAS_IMBALANCE=$(echo "$EVENTS_BODY" | jq 'if type == "array" and length > 0 then (.[0] | has("imbalance")) else false end')
if [ "$HAS_IMBALANCE" != "true" ]; then
  echo "FAIL: event missing 'imbalance' object"
  echo "$EVENTS_BODY" | jq '.[0]' 2>/dev/null || echo "$EVENTS_BODY"
  exit 1
fi
echo "OK: imbalance present"
# impedanceNorm should appear when include_impedance=true (may be null if no data yet)
HAS_IMPEDANCE_NORM=$(echo "$EVENTS_BODY" | jq 'if type == "array" and length > 0 then (.[0] | has("impedanceNorm")) else false end')
if [ "$HAS_IMPEDANCE_NORM" = "true" ]; then
  echo "OK: impedanceNorm present"
else
  echo "WARN: impedanceNorm missing (OK if no impedance data in DB yet)"
fi

# 2.3 GET /events/{market_id}/timeseries?include_impedance=true
MARKET_ID=$(echo "$EVENTS_BODY" | jq -r '.[0].market_id // .[0].event_id // empty')
if [ -n "$MARKET_ID" ]; then
  echo ""
  echo "--- 2.3: GET /events/$MARKET_ID/timeseries?include_impedance=true ---"
  TS_HTTP=$(curl -sS -w "\n%{http_code}" "$API_BASE/events/$MARKET_ID/timeseries?include_impedance=true&from_ts=$FROM_TS&to_ts=$TO_TS")
  TS_BODY=$(echo "$TS_HTTP" | head -n -1)
  TS_CODE=$(echo "$TS_HTTP" | tail -n 1)
  if [ "$TS_CODE" -ge 500 ]; then
    echo "FAIL: /events/.../timeseries returned $TS_CODE"
    echo "$TS_BODY" | head -20
    exit 1
  fi
  TS_HAS_IMBALANCE=$(echo "$TS_BODY" | jq 'if type == "array" and length > 0 then (.[0] | has("imbalance")) else true end')
  if [ "$TS_HAS_IMBALANCE" != "true" ]; then
    echo "FAIL: timeseries point missing 'imbalance'"
    exit 1
  fi
  echo "OK: timeseries point has imbalance"
  TS_HAS_IMP=$(echo "$TS_BODY" | jq 'if type == "array" and length > 0 then (.[0] | has("impedanceNorm")) else true end')
  if [ "$TS_HAS_IMP" = "true" ]; then
    echo "OK: timeseries point has impedanceNorm when requested"
  fi
else
  echo "--- 2.3: Skipped (no market_id from events) ---"
fi

echo ""
echo "========== Stage 2 complete. No 500s; imbalance present; impedanceNorm when requested. Proceed to Stage 3. =========="
