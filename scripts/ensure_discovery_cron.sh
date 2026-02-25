#!/usr/bin/env bash
# Run on VPS: verify or install cron for REST discovery (discovery_time_window.py).
# Usage: ./scripts/ensure_discovery_cron.sh [install]
# - No args: print status and how to fix.
# - install: append cron job if missing (requires cronie/cron installed).
# Discovery runs every 15 min; populates rest_events, rest_markets, tracked_markets. See docs/REST_DISCOVERY_VS_SNAPSHOT_REFACTOR.md

set -e
NETBET_ROOT="${NETBET_ROOT:-/opt/netbet}"
# Run discovery via Docker (same image as rest client; env from auth-service + .env)
CRON_ENTRY="*/15 * * * * docker run --rm --network netbet_default -v ${NETBET_ROOT}/auth-service/certs:/app/certs:ro --env-file ${NETBET_ROOT}/auth-service/.env --env-file ${NETBET_ROOT}/.env -e POSTGRES_HOST=netbet-postgres -e POSTGRES_PORT=5432 netbet-betfair-rest-client python discovery_time_window.py >> /var/log/discovery_time_window.log 2>&1"
CRON_COMMENT="# NetBet REST discovery (every 15 min, discovery_time_window.py)"

echo "=== REST discovery cron check (root=${NETBET_ROOT}) ==="
if ! command -v crontab &>/dev/null; then
    echo "crontab not found. Install cron (e.g. apt install cron) then re-run."
    exit 1
fi

if (crontab -l 2>/dev/null || true) | grep -q "discovery_time_window.py"; then
    echo "OK: Cron job for discovery_time_window.py is present."
    crontab -l 2>/dev/null | grep -n "discovery_time_window"
    exit 0
fi

# Also remove old discovery_hourly entry if present
if (crontab -l 2>/dev/null || true) | grep -q "discovery_hourly.py"; then
    echo "NOTE: Old discovery_hourly.py cron found. Replace with discovery_time_window.py (run install)."
fi

echo "MISSING: No cron job for discovery_time_window.py."
echo ""
echo "To install (run as the user that should own the job):"
echo "  (crontab -l 2>/dev/null; echo \"${CRON_COMMENT}\"; echo \"${CRON_ENTRY}\") | crontab -"
echo ""
if [ "${1:-}" = "install" ]; then
    CRON_BACKUP="$(crontab -l 2>/dev/null || true)"
    (echo "$CRON_BACKUP" | grep -v "discovery_hourly" | grep -v "NetBet REST discovery (hourly" || true
     echo "${CRON_COMMENT}"
     echo "${CRON_ENTRY}") | crontab -
    echo "Installed. Current crontab:"
    crontab -l
else
    echo "Run with: $0 install   to install the job."
    exit 1
fi
