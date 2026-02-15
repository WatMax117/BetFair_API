#!/usr/bin/env python3
"""Create a mock Parquet sample for Book Risk L3 export structure review."""
from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone

try:
    import pandas as pd
except ImportError:
    print("pip install pandas pyarrow")
    raise SystemExit(1)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "data_exports" / "book_risk_l3"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Mock long-format sample (Lazio v Atalanta, market 1.253489253)
rows = [
    {"market_id": "1.253489253", "snapshot_at_utc": "2026-02-02T14:00:00+00:00", "event_id": 35215830,
     "event_start_time_utc": "2026-02-02T19:45:00+00:00", "home_team_name": "Lazio", "away_team_name": "Atalanta",
     "market_type": "MATCH_ODDS", "total_volume": 125000.0, "selection_id": 47972, "selection_name": "Lazio",
     "side": "H", "back_odds_l1": 2.42, "back_size_l1": 450.0, "back_odds_l2": 2.44, "back_size_l2": 320.0,
     "back_odds_l3": 2.46, "back_size_l3": 180.0, "market_status": "OPEN", "in_play": False},
    {"market_id": "1.253489253", "snapshot_at_utc": "2026-02-02T14:00:00+00:00", "event_id": 35215830,
     "event_start_time_utc": "2026-02-02T19:45:00+00:00", "home_team_name": "Lazio", "away_team_name": "Atalanta",
     "market_type": "MATCH_ODDS", "total_volume": 125000.0, "selection_id": 58805, "selection_name": "Atalanta",
     "side": "A", "back_odds_l1": 2.98, "back_size_l1": 380.0, "back_odds_l2": 3.0, "back_size_l2": 210.0,
     "back_odds_l3": 3.02, "back_size_l3": 150.0, "market_status": "OPEN", "in_play": False},
    {"market_id": "1.253489253", "snapshot_at_utc": "2026-02-02T14:00:00+00:00", "event_id": 35215830,
     "event_start_time_utc": "2026-02-02T19:45:00+00:00", "home_team_name": "Lazio", "away_team_name": "Atalanta",
     "market_type": "MATCH_ODDS", "total_volume": 125000.0, "selection_id": 47973, "selection_name": "The Draw",
     "side": "D", "back_odds_l1": 3.35, "back_size_l1": 290.0, "back_odds_l2": 3.4, "back_size_l2": 175.0,
     "back_odds_l3": 3.45, "back_size_l3": 120.0, "market_status": "OPEN", "in_play": False},
]

df = pd.DataFrame(rows)
out = OUTPUT_DIR / "book_risk_l3__sample_long.parquet"
df.to_parquet(out, index=False)
print(f"Created {out}")
print(df.to_string())
