# Deploy Report: L2/L3 Table + Charts

## Commit hash deployed
**c26c60f0db64a936798babd940b10cf4aa6bccdf**

(Includes L2/L3 table switch to Debug endpoint, chart updates to Risk/Imbalance/Impedance only, and TypeScript type fixes)

## Deployment timestamp
**2026-02-14T10:34:52+01:00** (VPS local time, CET)

## Pre-deploy verification

### A) DB check ✓
- Ran: `SELECT COUNT(*) FROM market_derived_metrics WHERE home_back_odds_l2 IS NOT NULL` → 40+ rows
- L2/L3 columns exist and are populated for recent snapshots

### B) Network / API check ✓
- Debug endpoint: `GET /api/debug/markets/{market_id}/snapshots`
- Response includes `home_back_odds_l2`, `home_back_size_l2`, `home_back_odds_l3`, `home_back_size_l3` (and away/draw)
- Some snapshots have non-null L2/L3 (e.g. snapshot 9784 for market 1.253002724)

### C) Containers rebuilt
- `risk-analytics-ui-api` ✓
- `risk-analytics-ui-web` ✓

## Post-deploy verification

1. **Hard refresh** (Ctrl+F5) at http://158.220.83.195/
2. **L2/L3 table** – "Last 10 snapshots" uses `/api/debug/markets/{market_id}/snapshots`; shows numeric L2/L3 when DB has data
3. **Charts** – Only three: Risk (Book Risk L3) → Imbalance → Impedance Index
4. **No console errors** – Check DevTools console

## JSON snippet (Debug endpoint, non-null L2/L3)

Example row from `GET /api/debug/markets/1.253002724/snapshots?limit=5` (snapshot_id 9784):

```json
{
  "snapshot_id": 9784,
  "snapshot_at": "2026-02-14T09:21:43.991313+00:00",
  "market_id": "1.253002724",
  "home_back_odds_l2": 2.08,
  "home_back_size_l2": 206.11,
  "home_back_odds_l3": 2.06,
  "home_back_size_l3": 258.78,
  "away_back_odds_l2": 3.8,
  "away_back_size_l2": 169.6,
  "away_back_odds_l3": 3.75,
  "away_back_size_l3": 94.64,
  "draw_back_odds_l2": 3.6,
  "draw_back_size_l2": 529.93,
  "draw_back_odds_l3": 3.55,
  "draw_back_size_l3": 266.46,
  "home_book_risk_l3": -460.3023999999998,
  "away_book_risk_l3": -453.4480000000001,
  "draw_book_risk_l3": 1067.375,
  ...
}
```

## Screenshots (user to provide)
- Table: L2/L3 columns with numeric values + 3 indices (Imbalance, Impedance, Book Risk L3)
- Charts: 3 charts in order – Risk, Imbalance, Impedance
