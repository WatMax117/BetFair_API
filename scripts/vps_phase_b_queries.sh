#!/bin/bash
# Phase B outputs: time-series and stability for a market_id and optional depth_limit filter.
MARKET_ID="${1:-1.253636746}"
DEPTH="${2:-}"

echo "=== 1) Time series (last 12 snapshots) for market_id=$MARKET_ID depth_limit=${DEPTH:-any} ==="
if [ -n "$DEPTH" ]; then
  docker exec -i netbet-postgres psql -U netbet -d netbet -c "
SELECT snapshot_at, home_risk, away_risk, draw_risk,
  home_best_back, away_best_back, draw_best_back,
  home_best_lay, away_best_lay, draw_best_lay,
  total_volume, depth_limit
FROM market_risk_snapshots
WHERE market_id = '$MARKET_ID' AND depth_limit = $DEPTH
ORDER BY snapshot_at DESC
LIMIT 12;"
else
  docker exec -i netbet-postgres psql -U netbet -d netbet -c "
SELECT snapshot_at, home_risk, away_risk, draw_risk,
  home_best_back, away_best_back, draw_best_back,
  home_best_lay, away_best_lay, draw_best_lay,
  total_volume, depth_limit
FROM market_risk_snapshots
WHERE market_id = '$MARKET_ID'
ORDER BY snapshot_at DESC
LIMIT 12;"
fi

echo ""
echo "=== 2) Stability (DRAW) for market_id=$MARKET_ID depth_limit=${DEPTH:-any} ==="
if [ -n "$DEPTH" ]; then
  docker exec -i netbet-postgres psql -U netbet -d netbet -c "
SELECT COUNT(*) AS n,
  SUM(CASE WHEN draw_risk > 0 THEN 1 ELSE 0 END) AS positive,
  SUM(CASE WHEN draw_risk < 0 THEN 1 ELSE 0 END) AS negative
FROM (
  SELECT draw_risk FROM market_risk_snapshots
  WHERE market_id = '$MARKET_ID' AND depth_limit = $DEPTH
  ORDER BY snapshot_at DESC LIMIT 12
) t;"
else
  docker exec -i netbet-postgres psql -U netbet -d netbet -c "
SELECT COUNT(*) AS n,
  SUM(CASE WHEN draw_risk > 0 THEN 1 ELSE 0 END) AS positive,
  SUM(CASE WHEN draw_risk < 0 THEN 1 ELSE 0 END) AS negative
FROM (
  SELECT draw_risk FROM market_risk_snapshots
  WHERE market_id = '$MARKET_ID'
  ORDER BY snapshot_at DESC LIMIT 12
) t;"
fi
