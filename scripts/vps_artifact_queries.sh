#!/bin/bash
echo "=== \\d market_risk_snapshots ==="
docker exec -i netbet-postgres psql -U netbet -d netbet -c '\d market_risk_snapshots'

echo ""
echo "=== Latest row ==="
docker exec -i netbet-postgres psql -U netbet -d netbet -c "SELECT market_id, snapshot_at, home_risk, away_risk, draw_risk, total_volume, (raw_payload IS NOT NULL) AS has_raw_payload FROM market_risk_snapshots ORDER BY snapshot_at DESC LIMIT 1;"
