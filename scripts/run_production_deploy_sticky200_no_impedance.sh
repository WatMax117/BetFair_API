#!/usr/bin/env bash
# Full Production Deploy – Remove Imbalance/Impedance + Sticky200
# Run on VPS after: cd /opt/netbet (or your deployment root)
# Usage: bash scripts/run_production_deploy_sticky200_no_impedance.sh
# Optional: SKIP_CONFIRM=1 to run without interactive prompts
# Requires: docker compose, psql, git; .env with POSTGRES_* and BF_STICKY_* set

set -e
confirm() {
  if [[ "${SKIP_CONFIRM}" == "1" ]]; then return 0; fi
  echo "$1 (y/n)"
  read -r c
  [[ "$c" == "y" || "$c" == "Y" ]] || { echo "Aborted."; exit 1; }
}
DEPLOY_ROOT="${DEPLOY_ROOT:-$(pwd)}"
cd "$DEPLOY_ROOT"

echo "=== Phase 3 – Backup Current State ==="
TS=$(date +%F_%H%M)
cp .env ".env.backup.${TS}"
cp docker-compose.yml "docker-compose.yml.backup.${TS}"
docker ps > "docker_running_backup_${TS}.txt" 2>/dev/null || true
echo "Backups: .env.backup.${TS}, docker-compose.yml.backup.${TS}"

echo ""
echo "=== Phase 4 – Update code (build on server) ==="
git pull origin master
docker compose build betfair-rest-client risk-analytics-ui-api risk-analytics-ui-web
echo "Build OK."

echo ""
echo "=== Phase 5 – Deploy API and Web first ==="
docker compose up -d --build risk-analytics-ui-api risk-analytics-ui-web
sleep 5
echo "--- risk-analytics-ui-api last 50 lines ---"
docker logs --tail=50 risk-analytics-ui-api 2>&1
echo "--- risk-analytics-ui-web last 30 lines ---"
docker logs --tail=30 risk-analytics-ui-web 2>&1
confirm "Check above for missing-column or impedance/imbalance errors. Proceed?"

echo ""
echo "=== Phase 6 – Database migration ==="
if [[ -z "$POSTGRES_PASSWORD" ]]; then
  echo "Sourcing .env for POSTGRES_*..."
  set -a
  source .env 2>/dev/null || true
  set +a
fi
export PGPASSWORD="${POSTGRES_PASSWORD}"
psql -h localhost -p 5432 -U "${POSTGRES_USER:-netbet}" -d "${POSTGRES_DB:-netbet}" \
  -f risk-analytics-ui/sql/migrations/2026-02-15_drop_imbalance_impedance_columns.sql
echo "Migration done. Verifying schema..."
psql -h localhost -p 5432 -U "${POSTGRES_USER:-netbet}" -d "${POSTGRES_DB:-netbet}" \
  -c "\\d market_derived_metrics" | tee /tmp/schema_after_migration.txt
confirm "Confirm dropped columns are gone (no home_risk, home_impedance, etc.). Proceed?"

echo ""
echo "=== Phase 7 – Deploy REST client ==="
docker compose up -d --build betfair-rest-client
sleep 5
echo "--- netbet-betfair-rest-client last 80 lines ---"
docker logs --tail=80 netbet-betfair-rest-client 2>&1
confirm "Check: tracked_count up to 200, requests_per_tick=4, no Imbalance/Impedance in logs. Proceed?"

echo ""
echo "=== Phase 8 – System validation ==="
echo "--- API smoke: /leagues ---"
curl -s "http://localhost:8000/leagues?from_ts=2026-02-15T00:00:00Z&to_ts=2026-02-16T00:00:00Z&limit=5" | head -c 400
echo ""
echo "--- API smoke: /events/book-risk-focus ---"
curl -s "http://localhost:8000/events/book-risk-focus?limit=3" | head -c 400
echo ""
echo "--- docker stats (no-stream) ---"
docker stats --no-stream
echo ""
echo "Deploy script finished. Please:"
echo "  1) Open UI in browser and confirm no impedance/imbalance labels or console errors."
echo "  2) Confirm no impedance/imbalance in API response bodies."
echo "  3) Mark production-complete when all acceptance criteria pass."
