#!/usr/bin/env bash
# One-time: backfill impedance into public.market_derived_metrics from raw_payload,
# then re-run Stage 1 validation so 1.2 (recent rows with non-null impedance) passes.
# Run on VPS: cd /opt/netbet && ./scripts/vps_backfill_impedance_and_validate.sh
# Requires: .env with POSTGRES_REST_WRITER_* (or POSTGRES_* for netbet owner).

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/opt/netbet}"
cd "$REPO_ROOT"

# Load .env so POSTGRES_REST_WRITER_* are available for the container
if [ -f .env ]; then set -a; . ./.env; set +a; fi

echo ""
echo "========== Backfill impedance (from raw_payload) =========="
# Use public schema and container hostname. Override entrypoint to run backfill_impedance.py.
docker compose -p netbet run --rm \
  --entrypoint python \
  -e PGOPTIONS="-c search_path=public" \
  -e POSTGRES_HOST=netbet-postgres \
  -e POSTGRES_USER="${POSTGRES_REST_WRITER_USER:-netbet_rest_writer}" \
  -e POSTGRES_PASSWORD="${POSTGRES_REST_WRITER_PASSWORD}" \
  --no-deps \
  betfair-rest-client \
  backfill_impedance.py --days 7

echo ""
echo "========== Stage 1 validation (VALIDATE_ONLY=1) =========="
VALIDATE_ONLY=1 ./scripts/vps_stage1_deploy_and_validate.sh
