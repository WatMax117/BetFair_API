#!/usr/bin/env bash
# Hard Reset & Unified v1.2.1 Production Deployment
# Run on VPS from /opt/netbet:  bash scripts/hard_reset_deploy_v1.2.1.sh
# Step 1: Deep cleanup (containers, pgdata volume, network prune)
# Step 2: Launch is separate — run after sync:  cd /opt/netbet && docker compose up -d --build

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-/opt/netbet}"
cd "$PROJECT_ROOT"

echo "=== Step 1: Deep Cleanup (VPS) ==="

echo "Stopping netbet containers..."
docker ps -a | grep netbet | awk '{print $1}' | xargs -r docker stop 2>/dev/null || true

echo "Removing netbet containers..."
docker ps -a | grep netbet | awk '{print $1}' | xargs -r docker rm 2>/dev/null || true

echo "Removing database volume (clean Flyway V1–V5 migration)..."
docker volume rm netbet_pgdata 2>/dev/null || true

echo "Pruning unused networks..."
docker network prune -f

echo "=== Cleanup complete. ==="
echo ""
echo "Next: sync all v1.2.1 code to $PROJECT_ROOT, then run:"
echo "  cd $PROJECT_ROOT && docker compose up -d --build"
echo ""
echo "After 2 min: Pulse + Trace (see HARD_RESET_DEPLOY_v1.2.1.md)."
echo "After 5–10 min: Golden Audit."
