#!/usr/bin/env bash
# Restrict Apache (port 80) to a single IP for temporary validation.
# Run on the VPS: ./risk-analytics-ui/apache/vps_ufw_allow_single_ip.sh
# Allows only 94.26.26.147 to TCP 80; removes any global allow 80/tcp.

set -e

ALLOW_IP="${1:-94.26.26.147}"

if ! command -v ufw >/dev/null 2>&1; then
  echo "UFW not found. Install with: sudo apt install ufw"
  exit 1
fi

echo "Restricting port 80 to ${ALLOW_IP} only..."

# Remove generic allow 80/tcp if present (ignore error if rule does not exist)
sudo ufw delete allow 80/tcp 2>/dev/null || true

# Allow only from the single IP
sudo ufw allow from "$ALLOW_IP" to any port 80 proto tcp
echo "Rule added: allow from $ALLOW_IP to any port 80"

sudo ufw status
echo "If UFW was inactive, enable with: sudo ufw enable"
