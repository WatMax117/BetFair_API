#!/usr/bin/env bash
# Remove IP restrictions on port 80: allow HTTP from any IP (temporary).
# Run on the VPS: ./risk-analytics-ui/apache/vps_ufw_allow_all_port80.sh

set -e

if ! command -v ufw >/dev/null 2>&1; then
  echo "UFW not found. Install with: sudo apt install ufw"
  exit 1
fi

echo "Removing IP restriction and allowing port 80 from any IP..."

# Remove single-IP rule if present (e.g. 94.26.26.147)
sudo ufw delete allow from 94.26.26.147 to any port 80 proto tcp 2>/dev/null || true

# Allow port 80 from anywhere
sudo ufw allow 80/tcp
sudo ufw reload 2>/dev/null || true

sudo ufw status | grep -E "80|Status" || true
echo "Done: port 80 is now open to all. Restrict again later with: ./risk-analytics-ui/apache/vps_ufw_allow_single_ip.sh 94.26.26.147"
