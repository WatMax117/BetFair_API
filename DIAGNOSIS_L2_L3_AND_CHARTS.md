# Diagnosis: L2/L3 Table + Chart Updates

## A) Table endpoint and L2/L3 fix

### A1: Endpoint used for "Last 10 snapshots"
- **Previously:** `/api/events/{market_id}/timeseries` (bucketed, 15-min intervals)
- **Now:** `/api/debug/markets/{market_id}/snapshots` (per-snapshot rows)

### A2: Why L2/L3 showed "—"
- Timeseries returns **one row per 15-min bucket** (latest snapshot in bucket)
- L2/L3 can be NULL when:
  - Thin book (only L1 liquidity)
  - Bucketing picks a row where L2/L3 are null
- **Fix:** Use Debug endpoint instead — returns raw per-snapshot rows with full L2/L3 from `market_derived_metrics`

### A3: Changes made

1. **API (risk-analytics-ui/api/app/main.py):**
   - Added `home_best_back_size_l1`, `away_best_back_size_l1`, `draw_best_back_size_l1` to Debug snapshots SELECT

2. **UI (EventDetail.tsx):**
   - Load `fetchMarketSnapshots(marketId, from, to, 200)` when market/time range changes
   - Use `snapshots.slice(0, 10)` for "Last 10 snapshots" (Debug returns DESC, first 10 = latest)
   - Normalize impedance: `p.impedance?.home ?? p.home_impedance` (Debug has flat keys)
   - Normalize volume: `p.total_volume ?? p.mdm_total_volume`

3. **Types (api.ts):**
   - Added `home_best_back_size_l1`, `away_best_back_size_l1`, `draw_best_back_size_l1` to `DebugSnapshotRow`

### A5: DB verification
Run on VPS:
```bash
docker exec netbet-postgres psql -U netbet -d netbet -c "
SELECT snapshot_id, snapshot_at, home_back_odds_l2, home_back_size_l2, home_back_odds_l3, home_back_size_l3
FROM public.market_derived_metrics
ORDER BY snapshot_at DESC
LIMIT 10;
"
```

## B) Chart updates

### B1: Three charts only (in order)
1. **Risk (Book Risk L3)** — `home_book_risk_l3`, `away_book_risk_l3`, `draw_book_risk_l3`
2. **Imbalance (H/A/D)** — `home_risk`, `away_risk`, `draw_risk`
3. **Impedance Index (H/A/D)** — `home_impedance_raw`, `away_impedance_raw`, `draw_impedance_raw`

### B2: Removed
- Best back odds chart
- Total volume chart

### B3: Verification
- No console errors
- Charts update when selecting a different market/event
- Chart order: Risk first, then Imbalance, then Impedance

## Deployment

1. Rebuild and redeploy `risk-analytics-ui-api` (API changes)
2. Rebuild and redeploy `risk-analytics-ui-web` (UI changes)

## No-deploy rule (pre-deploy check)
1. Confirm via Network JSON that `/api/debug/markets/{market_id}/snapshots` returns non-null L2/L3 for recent rows
2. Confirm UI table shows L2/L3 numbers (not "—")
3. Confirm charts show Risk, Imbalance, Impedance in that order
