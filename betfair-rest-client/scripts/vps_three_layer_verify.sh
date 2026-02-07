#!/bin/bash
echo "=== \\d market_event_metadata ==="
docker exec -i netbet-postgres psql -U netbet -d netbet -c '\d market_event_metadata'

echo ""
echo "=== \\d market_book_snapshots ==="
docker exec -i netbet-postgres psql -U netbet -d netbet -c '\d market_book_snapshots'

echo ""
echo "=== \\d market_derived_metrics ==="
docker exec -i netbet-postgres psql -U netbet -d netbet -c '\d market_derived_metrics'

echo ""
echo "=== Sanity join (latest row) ==="
docker exec -i netbet-postgres psql -U netbet -d netbet -c "
SELECT
  m.snapshot_at,
  m.market_id,
  e.event_name,
  e.competition_name,
  e.event_open_date,
  d.home_risk, d.away_risk, d.draw_risk,
  d.home_best_back, d.away_best_back, d.draw_best_back,
  (m.raw_payload IS NOT NULL) AS has_raw
FROM market_book_snapshots m
JOIN market_event_metadata e ON e.market_id = m.market_id
JOIN market_derived_metrics d ON d.snapshot_id = m.snapshot_id
ORDER BY m.snapshot_at DESC
LIMIT 1;
"
