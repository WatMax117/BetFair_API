#!/bin/bash
# VPS Deep Clean & Re-Deploy
# Run on VPS from /opt/netbet
# Usage: ./scripts/vps_cleanup_and_deploy.sh

set -e
cd /opt/netbet

echo "=== Deep clean: stopping compose, removing containers, pruning volumes and networks ==="
docker compose down 2>/dev/null || true
docker rm -f $(docker ps -aq) 2>/dev/null || true
docker volume prune -f
docker network prune -f

echo "=== Ensuring /opt/netbet/logs exists with write permissions ==="
mkdir -p /opt/netbet/logs
chmod 777 /opt/netbet/logs

echo "=== Build and start ==="
docker compose up -d --build

echo "=== Streaming logs (Ctrl+C to stop) ==="
docker compose logs -f
