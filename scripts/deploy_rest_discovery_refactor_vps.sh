#!/usr/bin/env bash
# Deploy REST discovery refactor to VPS: rebuild rest client, switch cron to discovery_time_window, run discovery once.
# Run ON THE VPS from /opt/netbet after: git pull origin main
# Usage: ./scripts/deploy_rest_discovery_refactor_vps.sh

set -e
cd "$(dirname "$0")/.."
NETBET_ROOT="${PWD}"

echo "=== 1. Rebuild betfair-rest-client image (includes discovery_time_window.py) ==="
docker compose build --no-cache betfair-rest-client

echo ""
echo "=== 2. Ensure discovery cron (discovery_time_window every 15 min) ==="
./scripts/ensure_discovery_cron.sh || ./scripts/ensure_discovery_cron.sh install

echo ""
echo "=== 3. Restart REST client container ==="
docker compose up -d --force-recreate --no-deps betfair-rest-client

echo ""
echo "=== 4. Run discovery once to populate tracked_markets and discovery_run_log ==="
docker run --rm --network netbet_default \
  -v "${NETBET_ROOT}/auth-service/certs:/app/certs:ro" \
  --env-file "${NETBET_ROOT}/auth-service/.env" \
  --env-file "${NETBET_ROOT}/.env" \
  -e POSTGRES_HOST=netbet-postgres \
  -e POSTGRES_PORT=5432 \
  netbet-betfair-rest-client \
  python discovery_time_window.py

echo ""
echo "=== 5. Verify ==="
echo "REST client logs (tracked set from DB, no sticky):"
docker logs netbet-betfair-rest-client --tail=20
echo ""
echo "Discovery run log (should have one row):"
docker exec -i netbet-postgres psql -U netbet -d netbet -c "SELECT run_at_utc, discovered_count, desired_count, tracked_count_after, added_count, dropped_count, duration_ms FROM discovery_run_log ORDER BY run_at_utc DESC LIMIT 1;"
echo ""
echo "Tracked markets count:"
docker exec -i netbet-postgres psql -U netbet -d netbet -c "SELECT state, COUNT(*) FROM tracked_markets GROUP BY state;"

echo ""
echo "=== Done. Discovery will run every 15 min via cron. REST daemon uses tracked_markets from DB only. ==="
