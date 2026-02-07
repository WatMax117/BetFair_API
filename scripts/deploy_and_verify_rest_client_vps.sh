#!/bin/bash
# Deploy betfair-rest-client to VPS and run single-shot verification.
# Run from NetBet repo root on your machine (with SSH key for root@158.220.83.195).
# Usage: ./scripts/deploy_and_verify_rest_client_vps.sh

set -e
VPS="root@158.220.83.195"
REMOTE="/opt/netbet"
LOCAL="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== 1. Environment Sync: Upload main.py, risk.py, Dockerfile, requirements.txt ==="
scp "$LOCAL/betfair-rest-client/main.py" "$VPS:${REMOTE}/betfair-rest-client/"
scp "$LOCAL/betfair-rest-client/risk.py" "$VPS:${REMOTE}/betfair-rest-client/"
scp "$LOCAL/betfair-rest-client/Dockerfile" "$VPS:${REMOTE}/betfair-rest-client/"
scp "$LOCAL/betfair-rest-client/requirements.txt" "$VPS:${REMOTE}/betfair-rest-client/"

echo "=== 2 & 3. Clean, drop table, build, single-shot test ==="
ssh "$VPS" "cd $REMOTE && \
  docker compose stop betfair-rest-client 2>/dev/null || true; \
  docker compose rm -f betfair-rest-client 2>/dev/null || true; \
  docker rmi netbet-betfair-rest-client betfair-rest-client_betfair-rest-client 2>/dev/null || true; \
  docker exec -i netbet-postgres psql -U netbet -d netbet -c 'DROP TABLE IF EXISTS market_risk_snapshots;'; \
  docker compose build betfair-rest-client && \
  mkdir -p /opt/netbet/betfair-rest-client && \
  docker compose run --rm \
    -e BF_SINGLE_SHOT=1 \
    -e DEBUG_MARKET_SAMPLE_PATH=/opt/netbet/betfair-rest-client/debug_market_sample.json \
    -v /opt/netbet/betfair-rest-client:/opt/netbet/betfair-rest-client \
    betfair-rest-client 2>&1 | tee /tmp/single_shot_log.txt"

echo ""
echo "=== 4. Verification: table structure and first row ==="
ssh "$VPS" "docker exec -i netbet-postgres psql -U netbet -d netbet -c '\d market_risk_snapshots'"
echo ""
ssh "$VPS" "docker exec -i netbet-postgres psql -U netbet -d netbet -c \"SELECT market_id, snapshot_at, home_risk, away_risk, draw_risk, total_volume, (raw_payload IS NOT NULL) AS has_raw_payload FROM market_risk_snapshots LIMIT 1;\""
echo ""
echo "=== RAW MARKET JSON (excerpt from saved file on VPS) ==="
ssh "$VPS" "head -120 /opt/netbet/betfair-rest-client/debug_market_sample.json 2>/dev/null || echo 'File not found'"

echo ""
echo "Copy the RAW MARKET JSON and SQL output above and paste into chat for review."
