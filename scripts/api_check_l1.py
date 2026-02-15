#!/usr/bin/env python3
"""Check API returns non-null *_best_back_size_l1 for a market snapshot."""
import json
import urllib.request

url = "http://localhost:8000/api/debug/markets/1.253489253/snapshots?limit=1"
try:
    with urllib.request.urlopen(url, timeout=5) as r:
        data = json.load(r)
except Exception as e:
    print({"error": str(e)})
    exit(1)

row = data[0] if data else {}
out = {
    "snapshot_at": row.get("snapshot_at"),
    "home_best_back_size_l1": row.get("home_best_back_size_l1"),
    "away_best_back_size_l1": row.get("away_best_back_size_l1"),
    "draw_best_back_size_l1": row.get("draw_best_back_size_l1"),
}
print(json.dumps(out, indent=2))
