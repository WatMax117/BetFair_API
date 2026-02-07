#!/usr/bin/env bash
# Disable temporary public access to Risk Analytics UI (port 80).
# Run on VPS from repo root: ./risk-analytics-ui/apache/vps_disable_public_access.sh
# Options: --stop-apache   also stop Apache (default: only remove port 80 and disable vhost)

set -e

STOP_APACHE=false
for arg in "$@"; do
  case "$arg" in
    --stop-apache) STOP_APACHE=true ;;
  esac
done

echo "Removing firewall rule: allow 80/tcp..."
sudo ufw delete allow 80/tcp 2>/dev/null || true

echo "Disabling risk-analytics vhost..."
sudo a2dissite risk-analytics.conf 2>/dev/null || true
sudo systemctl reload apache2 2>/dev/null || true

if [ "$STOP_APACHE" = true ]; then
  echo "Stopping Apache..."
  sudo systemctl stop apache2
fi

echo "Done. Port 80 is closed; Docker ports (8080/8081) remain internal only."
sudo ufw status | grep -E "80|Status" || true
