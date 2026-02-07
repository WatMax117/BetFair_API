#!/usr/bin/env bash
# Start Apache and allow the Risk Analytics UI to be accessed from anywhere via the VPS public IP.
# Run from repo root on VPS: ./risk-analytics-ui/apache/vps_start_apache_public.sh
# Requires: Docker UI on host port 8080, API on host port 8081 (see risk-analytics.conf).
# Always allows SSH (22) before opening 80 to avoid locking yourself out.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CONF_SRC="$REPO_ROOT/risk-analytics-ui/apache/risk-analytics.conf"

if [ ! -f "$CONF_SRC" ]; then
  echo "Config not found: $CONF_SRC (run from repo root)"
  exit 1
fi

echo "=== 1. Start and enable Apache ==="
sudo systemctl start apache2 || true
sudo systemctl enable apache2
sudo systemctl status apache2 --no-pager || true

echo ""
echo "=== 2. Enable proxy modules ==="
sudo a2enmod proxy
sudo a2enmod proxy_http
sudo systemctl restart apache2

echo ""
echo "=== 3. Activate Risk Analytics vhost (disable default site) ==="
sudo a2dissite 000-default.conf 2>/dev/null || sudo a2dissite 000-default 2>/dev/null || true
sudo cp "$CONF_SRC" /etc/apache2/sites-available/risk-analytics.conf
sudo a2ensite risk-analytics.conf
sudo systemctl reload apache2

echo ""
echo "=== 4. Firewall: allow SSH (22) first, then HTTP (80) ==="
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw reload 2>/dev/null || true
sudo ufw status | grep -E "80|Status" || true

echo ""
echo "=== 5. Verify Apache listening and local response ==="
sudo ss -lntp | grep ':80' && echo "Apache listening on 0.0.0.0:80" || echo "WARNING: nothing on :80"
curl -sS -o /dev/null -w "Local curl: HTTP %{http_code}\n" http://127.0.0.1/ || true

echo ""
echo "Done. Interface is freely accessible from anywhere:"
echo "  UI:  http://<VPS_PUBLIC_IP>/"
echo "  API: http://<VPS_PUBLIC_IP>/api/health"
echo "To disable public access: ./risk-analytics-ui/apache/vps_disable_public_access.sh"
