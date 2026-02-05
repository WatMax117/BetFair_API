#!/bin/bash
# Run 10-minute (600 seconds) data collection for highest-volume in-play football market.
# 1. Find live market via Python discovery script
# 2. Start Java streaming-client with discovered Market ID(s)
# 3. Run for exactly 600 seconds, then auto-close CSV writers
# Requires: auth-service running, Python 3, docker compose.
# Usage: ./scripts/run_production_test.sh (from /opt/netbet)

set -e
cd /opt/netbet

echo "=== Ensuring services are running ==="
docker compose up -d
echo "Waiting 15 seconds for Auth service to initialize..."
sleep 15

mkdir -p /opt/netbet/logs && chmod 777 /opt/netbet/logs

echo "=== Discovering highest-volume in-play football market ==="
export BETFAIR_TOKEN_URL="http://localhost:8080/token"
if [ -f auth-service/.env ]; then set -a; . auth-service/.env; set +a; fi
export BETFAIR_APP_KEY="${BETFAIR_APP_KEY:-WftFC5jIOJMsORVD}"
MARKET_IDS=$(python3 betfair-streaming-client/scripts/discover_live_football.py)

if [ -z "$MARKET_IDS" ]; then
  echo "Discovery failed: no market IDs" >&2
  exit 1
fi
echo "Market IDs: $MARKET_IDS"
export BETFAIR_MARKET_IDS="$MARKET_IDS"

echo "=== Starting 10-minute data collection (datalogging profile) ==="
docker compose run --rm \
  -e BETFAIR_MARKET_IDS \
  -e SPRING_PROFILES_ACTIVE=datalogging \
  -e BETFAIR_CSV_LOGGING=true \
  streaming-client

echo "=== Done. CSV files in /opt/netbet/logs/ ==="
ls -la /opt/netbet/logs/ 2>/dev/null || true
