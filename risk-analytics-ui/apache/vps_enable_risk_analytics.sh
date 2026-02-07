#!/usr/bin/env bash
# Make Risk Analytics UI accessible via VPS public IP (temporary validation).
# Run from repo root on VPS: ./risk-analytics-ui/apache/vps_enable_risk_analytics.sh
# Or from this dir: ./vps_enable_risk_analytics.sh
# Requires: Docker UI on host port 8080, API on host port 8081 (see risk-analytics.conf).

set -e

ALLOW_IP="${1:-94.26.26.147}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CONF_SRC="$REPO_ROOT/risk-analytics-ui/apache/risk-analytics.conf"

if [ ! -f "$CONF_SRC" ]; then
  echo "Config not found: $CONF_SRC (run from repo root)"
  exit 1
fi

echo "=== 1. Ensure Apache is running and enabled ==="
sudo systemctl start apache2 || true
sudo systemctl enable apache2
sudo systemctl status apache2 --no-pager || true

echo ""
echo "=== 2. Enable required Apache modules ==="
sudo a2enmod proxy
sudo a2enmod proxy_http
sudo systemctl restart apache2

echo ""
echo "=== 3. Activate the Risk Analytics vhost ==="
sudo cp "$CONF_SRC" /etc/apache2/sites-available/risk-analytics.conf
sudo a2ensite risk-analytics.conf
sudo systemctl reload apache2

echo ""
echo "=== 4. Verify Apache is listening on port 80 ==="
sudo ss -lntp | grep ':80' && echo "Expected: Apache on 0.0.0.0:80" || echo "WARNING: no process listening on :80"

echo ""
echo "=== 5. Firewall: allow port 80 only from $ALLOW_IP ==="
sudo ufw delete allow 80/tcp 2>/dev/null || true
sudo ufw allow from "$ALLOW_IP" to any port 80 proto tcp
sudo ufw reload 2>/dev/null || true
sudo ufw status | grep -E "80|Status" || true

echo ""
echo "=== 6. Local sanity check ==="
curl -sS -o /dev/null -w "%{http_code}" http://127.0.0.1/ | grep -q 200 && echo "OK: HTTP 200 from http://127.0.0.1/" || { echo "WARNING: local curl did not get 200"; exit 1; }

echo ""
echo "Done. From your machine (IP $ALLOW_IP):"
echo "  UI:  http://<VPS_PUBLIC_IP>/"
echo "  API: http://<VPS_PUBLIC_IP>/api/health  -> {\"status\":\"ok\"}"
echo "From other IPs: connection should be refused or blocked."
