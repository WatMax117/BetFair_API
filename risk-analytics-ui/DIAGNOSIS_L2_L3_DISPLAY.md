# Diagnosis: Missing L2/L3 Display in Event "Last 10 snapshots"

**Date**: 2026-02-14  
**Status**: Code verified correct; no UI/API regression found. Likely cause: stale Docker build or VPS image.

---

## Step 1 — Endpoint: Debug snapshots ✓

**Expected**: `/api/debug/markets/{market_id}/snapshots`  
**Actual**: `EventDetail.tsx` uses `fetchMarketSnapshots()` → calls this endpoint (line 148).

- `last10 = snapshots.slice(0, 10)` (line 188)
- Table uses `snapshots`, not `timeseries`

---

## Step 2 — API response L2/L3 ✓

**API** (`risk-analytics-ui/api/app/main.py` lines 875-877):

- SELECT includes: `d.home_back_odds_l2`, `d.home_back_size_l2`, `d.home_back_odds_l3`, `d.home_back_size_l3` (and away/draw)
- `_serialize` passes row keys through (lines 904-914) → L2/L3 keys present in JSON

---

## Step 3 — UI field names ✓

**EventDetail.tsx** (lines 334-358):

- Table columns use: `p.home_back_odds_l2`, `p.home_back_size_l2`, `p.home_back_odds_l3`, `p.home_back_size_l3` (and away/draw)
- `DebugSnapshotRow` type in `api.ts` (lines 156-167): all L2/L3 fields defined
- No camelCase mismatch; API returns snake_case, UI expects snake_case

---

## Step 4 — Snapshots state ✓

- `loadSnapshots()` calls `fetchMarketSnapshots(marketId, from, to, 200)` (line 146)
- `snapshots` state populated via `setSnapshots(data)` (line 147)
- Table uses `last10 = snapshots.slice(0, 10)` (line 188)

---

## Step 5 — Git diff (no regression)

```bash
git log --oneline -5 -- risk-analytics-ui/web/src/components/EventDetail.tsx
# 70f42a9 Fix DebugSnapshotRow types: add impedance, total_volume; use mdm_total_volume for table
# c26c60f L2/L3: switch Last 10 snapshots to Debug endpoint; ...
# ...
```

`git diff c26c60f..HEAD -- EventDetail.tsx` shows only: `p.total_volume ?? p.mdm_total_volume` → `p.mdm_total_volume ?? p.total_volume` (total_volume column fallback). L2/L3 logic unchanged.

---

## Root cause (likely)

1. **Stale Docker build** – VPS web container may have been built with cached layers from before L2/L3 table columns (c26c60f).
2. **No-cache not used** – `docker compose build` without `--no-cache` can serve old layers.

---

## Fix: Rebuild and redeploy

```bash
docker compose build risk-analytics-ui-web --no-cache
docker compose up -d risk-analytics-ui-web --no-deps
# Hard refresh (Ctrl+F5) in browser
```

---

## Verification checklist

1. **Network** – DevTools → Network: request to `/api/debug/markets/{market_id}/snapshots?...`
2. **Response** – JSON rows include `home_back_odds_l2`, `home_back_size_l2`, `home_back_odds_l3`, `home_back_size_l3` (and away/draw).
3. **Table** – "Last 10 snapshots" shows L2/L3 columns with numeric values (or "—" when null).
4. **Console** – No JS errors.

---

## Deliverables (after fix)

- Commit hash of current code
- Screenshot: "Last 10 snapshots" with L2/L3 visible
- Network screenshot or JSON snippet proving debug endpoint + L2/L3 keys
