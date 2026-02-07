# Deploy betfair-rest-client to VPS and run single-shot verification.
# Run from NetBet repo root. Uses SSH key at $KEY for root@158.220.83.195.
#
# HOW TO RUN: Type only this (do not paste the "PS C:\...>" prompt):
#   .\scripts\deploy_and_verify_rest_client_vps.ps1
# Or:  powershell -ExecutionPolicy Bypass -File .\scripts\deploy_and_verify_rest_client_vps.ps1

$ErrorActionPreference = "Stop"
$KEY = "C:\Users\WatMax\.ssh\id_ed25519_contabo"
$VPS = "root@158.220.83.195"
$REMOTE = "/opt/netbet"
$LOCAL = $PSScriptRoot + "\.."

Write-Host "=== 1. Environment Sync: Upload main.py, risk.py, Dockerfile ==="
& scp -i $KEY "$LOCAL\betfair-rest-client\main.py" "${VPS}:${REMOTE}/betfair-rest-client/"
& scp -i $KEY "$LOCAL\betfair-rest-client\risk.py" "${VPS}:${REMOTE}/betfair-rest-client/"
& scp -i $KEY "$LOCAL\betfair-rest-client\Dockerfile" "${VPS}:${REMOTE}/betfair-rest-client/"
& scp -i $KEY "$LOCAL\betfair-rest-client\requirements.txt" "${VPS}:${REMOTE}/betfair-rest-client/"

$script = @'
set -e
cd /opt/netbet
echo "=== 2. Clean Rebuild ==="
docker compose stop betfair-rest-client 2>/dev/null || true
docker compose rm -f betfair-rest-client 2>/dev/null || true
docker rmi netbet-betfair-rest-client betfair-rest-client_betfair-rest-client 2>/dev/null || true
docker exec -i netbet-postgres psql -U netbet -d netbet -c "DROP TABLE IF EXISTS market_risk_snapshots;"
docker compose build betfair-rest-client

echo "=== 3. Single-Shot Test ==="
mkdir -p /opt/netbet/betfair-rest-client
docker compose run --rm \
  -e BF_SINGLE_SHOT=1 \
  -e DEBUG_MARKET_SAMPLE_PATH=/opt/netbet/betfair-rest-client/debug_market_sample.json \
  -v /opt/netbet/betfair-rest-client:/opt/netbet/betfair-rest-client \
  betfair-rest-client 2>&1 | tee /tmp/single_shot_log.txt

echo ""
echo "=== 4. Verification ==="
docker exec -i netbet-postgres psql -U netbet -d netbet -c "\d market_risk_snapshots"
echo ""
docker exec -i netbet-postgres psql -U netbet -d netbet -c "SELECT market_id, snapshot_at, home_risk, away_risk, draw_risk, total_volume, (raw_payload IS NOT NULL) AS has_raw_payload FROM market_risk_snapshots LIMIT 1;"
echo ""
echo "=== RAW MARKET JSON (first 120 lines of saved file) ==="
head -120 /opt/netbet/betfair-rest-client/debug_market_sample.json 2>/dev/null || cat /tmp/single_shot_log.txt | sed -n "/Raw market JSON (single market):/,/^[0-9][0-9][0-9][0-9]-/p" | head -120
'@

Write-Host "=== Running remote deploy and single-shot (SSH) ==="
$script | & ssh -i $KEY $VPS "bash -s"

Write-Host ""
Write-Host "Done. Copy the 'RAW MARKET JSON' and the SQL query result from above and paste into chat for review."
