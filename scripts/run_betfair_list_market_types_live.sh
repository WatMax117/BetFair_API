#!/bin/bash
# Run betfair_list_market_types_live.py inside Docker on VPS.
# Uses auth-service for token (BETFAIR_TOKEN_URL=http://auth-service:8080/token).
# Output: data_exports/betfair_live_output.json

set -e
cd "$(dirname "$0")/.."
set -a
[ -f .env ] && source .env 2>/dev/null || true
set +a

OUTPUT_DIR="${DATA_EXPORTS_DIR:-/opt/netbet/data_exports}"
export BETFAIR_TOKEN_URL="${BETFAIR_TOKEN_URL:-http://auth-service:8080/token}"
export BETFAIR_APP_KEY="${BETFAIR_APP_KEY:-}"

echo "Running Betfair listMarketTypes/listMarketCatalogue (Live API)..."
echo "Token URL: $BETFAIR_TOKEN_URL"
echo "Output: $OUTPUT_DIR/betfair_live_output.json"

docker run --rm --network netbet_default \
  -e BETFAIR_TOKEN_URL \
  -e BETFAIR_APP_KEY \
  -v "$(pwd)/data_exports:/data_exports" \
  -v "$(pwd)/scripts:/opt/netbet/scripts" \
  -w /opt/netbet \
  python:3.11-slim \
  bash -c "python scripts/betfair_list_market_types_live.py > /data_exports/betfair_live_output.json 2>&1"

echo "Done. Output written to data_exports/betfair_live_output.json"
