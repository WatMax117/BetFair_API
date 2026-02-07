#!/usr/bin/env bash
# One-off Apache setup on VPS for Risk Analytics UI (temporary, validation only).
# Run on the VPS from the repo root: ./risk-analytics-ui/apache/vps_setup_apache.sh
# Requires: Docker stack with risk-analytics-ui-api (8000) and risk-analytics-ui-web (3000).

set -e

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CONF_SRC="$REPO_ROOT/risk-analytics-ui/apache/risk-analytics.conf"

if [ ! -f "$CONF_SRC" ]; then
  echo "Config not found: $CONF_SRC (run from repo root or adjust path)"
  exit 1
fi

echo "Installing Apache and enabling proxy modules..."
sudo apt-get update -qq
sudo apt-get install -y apache2
sudo a2enmod proxy proxy_http

echo "Deploying risk-analytics vhost..."
sudo cp "$CONF_SRC" /etc/apache2/sites-available/risk-analytics.conf
sudo a2ensite risk-analytics.conf 2>/dev/null || true

# Disable default site if present so port 80 serves Risk Analytics
if [ -f /etc/apache2/sites-enabled/000-default.conf ]; then
  echo "Disabling default site (000-default.conf)..."
  sudo a2dissite 000-default.conf
fi

echo "Reloading Apache..."
sudo systemctl reload apache2

echo "Done. From your browser use: http://<VPS_PUBLIC_IP>/"
echo "API check: http://<VPS_PUBLIC_IP>/api/health"
echo "If UFW is enabled: sudo ufw allow 80/tcp && sudo ufw status"
