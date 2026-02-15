#!/bin/bash
# Verify Book Risk L3 backfill on VPS
echo "=== DB sample (oldest 3 with book_risk_l3) ==="
docker exec netbet-postgres psql -U netbet -d netbet -t -c "
SELECT snapshot_id, snapshot_at, home_book_risk_l3, away_book_risk_l3, draw_book_risk_l3
FROM public.market_derived_metrics
WHERE home_book_risk_l3 IS NOT NULL
ORDER BY snapshot_at ASC
LIMIT 3;
"

echo ""
echo "=== API timeseries (first point) ==="
curl -s "http://localhost:8000/api/events/1.253641180/timeseries?from_ts=2026-02-06T00:00:00Z&to_ts=2026-02-15T00:00:00Z&interval_minutes=60&limit=5" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    pts = d if isinstance(d, list) else d.get('points', [])
    if pts:
        p = pts[0]
        print(json.dumps({k: v for k, v in p.items() if 'book_risk_l3' in k or 'impedance' in k or 'size' in k}, indent=2))
    else:
        print('No points')
except Exception as e:
    print('Error:', e)
"
