#!/bin/bash
# Clean deployment and single-shot test for betfair-rest-client on VPS.
# Run on VPS via SSH: bash /opt/netbet/scripts/vps_clean_deploy_rest_client.sh
# Or copy-paste the sections below.

set -e
cd /opt/netbet

echo "=== 1. Server Cleanup ==="
docker compose stop betfair-rest-client 2>/dev/null || true
docker compose rm -f betfair-rest-client 2>/dev/null || true
docker rmi netbet-betfair-rest-client 2>/dev/null || true
docker rmi betfair-rest-client_betfair-rest-client 2>/dev/null || true

echo "=== 2. Database Reset (drop market_risk_snapshots) ==="
docker exec -i netbet-postgres psql -U netbet -d netbet -c "DROP TABLE IF EXISTS market_risk_snapshots;"

echo "=== 3. Rebuild ==="
docker compose build betfair-rest-client

echo "=== 4. Single-shot test (one market, raw JSON to console + file + DB) ==="
mkdir -p /opt/netbet/betfair-rest-client
docker compose run --rm \
  -e BF_SINGLE_SHOT=1 \
  -e DEBUG_MARKET_SAMPLE_PATH=/opt/netbet/betfair-rest-client/debug_market_sample.json \
  -v /opt/netbet/betfair-rest-client:/opt/netbet/betfair-rest-client \
  betfair-rest-client

echo "=== 5. Verification ==="
echo "--- Raw JSON was printed above in the 'docker compose run' output (scroll up to see 'Raw market JSON') ---"

echo "--- Debug file on host ---"
ls -la /opt/netbet/betfair-rest-client/debug_market_sample.json 2>/dev/null && head -50 /opt/netbet/betfair-rest-client/debug_market_sample.json || echo "File not found"

echo "--- PostgreSQL: table structure and first row ---"
docker exec -i netbet-postgres psql -U netbet -d netbet -c "\d market_risk_snapshots"
docker exec -i netbet-postgres psql -U netbet -d netbet -c "SELECT market_id, snapshot_at, home_risk, away_risk, draw_risk, total_volume, (raw_payload IS NOT NULL) AS has_raw_payload FROM market_risk_snapshots LIMIT 1;"
