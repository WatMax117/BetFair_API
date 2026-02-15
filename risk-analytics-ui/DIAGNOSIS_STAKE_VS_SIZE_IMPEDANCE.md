# Diagnosis: Stake vs Size Impedance (UI vs API)

## Architecture Summary

| Index | Source | DB Column | API Field | UI Usage |
|-------|--------|-----------|-----------|----------|
| **Stake Impedance** | REST ingestion (risk.py compute_impedance_index) | `home_impedance`, `away_impedance`, `draw_impedance` | `impedance` (home/away/draw) | Rendered as "Stake Impedance Index" |
| **Size Impedance (L1)** | Client-side computed | None (computed from L1 sizes + odds) | N/A — UI computes from `home_best_back_size_l1` + `home_best_back` | Rendered as "Size Impedance Index (L1)" |

### Important

**Size Impedance is NOT stored in the DB.** The UI computes it on the fly using:

```ts
// EventDetail.tsx computeSizeImpedanceL1(p)
// Inputs: home_best_back_size_l1, away_best_back_size_l1, draw_best_back_size_l1
//         home_best_back, away_best_back, draw_best_back (odds)
// Formula: L1_j = size_j*(odds_j-1), SizeImpedance_L1_j = L1_j − Σ(L1_k for k≠j)
```

So the API must return **L1 size fields** and **best_back odds** — the UI then computes Size Impedance.

---

## API Response Contract (Required Fields)

For both indices to appear in the UI, the timeseries JSON must include:

| Category | Fields | Purpose |
|----------|--------|---------|
| **A) L1 sizes** | `home_best_back_size_l1`, `away_best_back_size_l1`, `draw_best_back_size_l1`, `home_best_lay_size_l1`, `away_best_lay_size_l1`, `draw_best_lay_size_l1` | backSize/laySize columns + Size Impedance computation |
| **B) Stake inputs** | `impedanceInputs.home.backStake`, `.layStake`, `.backOdds`, `.layOdds` (and away/draw) | backStake/layStake columns |
| **C) Stake Impedance** | `impedance.home`, `impedance.away`, `impedance.draw` | Stake Impedance Index column |
| **D) Odds** | `home_best_back`, `away_best_back`, `draw_best_back` | Size Impedance formula (always present) |

There is **no separate API field for Size Impedance** — it is derived in the UI from A + D.

---

## Verification Steps

### Step 1: API JSON (DevTools → Network)

1. Open Risk Analytics UI in browser
2. DevTools → Network → XHR
3. Refresh, open a market/event
4. Find the timeseries request: `GET .../events/{market_id}/timeseries?include_impedance=true&include_impedance_inputs=true`
5. Inspect Response

**Expected:**
- A) `home_best_back_size_l1`, `away_best_back_size_l1`, `draw_best_back_size_l1` (and lay) present
- B) `impedanceInputs.home.backStake`, `.layStake` present
- C) `impedance.home`, `impedance.away`, `impedance.draw` present

**If A+B+C exist:** API is correct. If UI still shows "—" for Size Impedance → UI bundle cache or old UI container.

**If A or B missing:** API container is outdated — rebuild/redeploy risk-analytics-ui-api.

### Step 2: DB Check (VPS)

```sql
SELECT snapshot_at, market_id,
  home_best_back_size_l1, away_best_back_size_l1, draw_best_back_size_l1,
  home_impedance, away_impedance, draw_impedance,
  home_back_stake, away_back_stake, draw_back_stake
FROM market_derived_metrics
WHERE market_id = '1.253002724'
ORDER BY snapshot_at DESC
LIMIT 3;
```

- L1 size columns: should be non-NULL (after backfill + ingestion fix)
- `home_impedance` etc.: Stake Impedance — should be non-NULL
- `home_back_stake` etc.: VWAP inputs — should be non-NULL

**Size Impedance has no DB column** — it is computed client-side.

### Step 3: UI Container

If API returns all fields but UI shows "—":

1. Rebuild UI: `docker compose build risk-analytics-ui-web --no-cache`
2. Redeploy: `docker compose up -d risk-analytics-ui-web --no-deps`
3. Hard refresh browser (Ctrl+F5) to clear cached JS

---

## Evidence

### API JSON (2026-02-14)

The timeseries endpoint returns:

- **A) L1 size fields:** `home_best_back_size_l1`, `away_best_back_size_l1`, `draw_best_back_size_l1`, `home_best_lay_size_l1`, etc. ✅
- **B) impedanceInputs:** `home.backStake`, `home.layStake`, `away.backStake`, etc. ✅
- **C) impedance (Stake Impedance):** `impedance.home`, `impedance.away`, `impedance.draw` ✅

**Size Impedance Index** is not an API field — the UI computes it from L1 sizes + best_back odds.

### DB Query Output (market 1.253002724, last 3 snapshots)

```
snapshot_at          | home_best_back_size_l1 | home_impedance | home_back_stake
---------------------+------------------------+----------------+----------------
2026-02-14 07:03:01  | (null)                 | -748.45        | (null)
2026-02-14 07:01:43  | 686.74                 | -655.57        | 1506.2
2026-02-14 06:58:17  | 310.42                 | -416.10        | 1111.36
```

- L1 sizes, impedance (Stake), back_stake are populated for most rows.
- One newest row has NULL L1/back_stake (possible transient ingest gap).
- **No DB column for Size Impedance** — it is computed client-side.

---

## Current State (as of 2026-02-14)

| Layer | Status |
|-------|--------|
| DB | L1 sizes + impedance + back_stake populated (backfill + ingestion) |
| API | risk-analytics-ui-api redeployed; returns L1, impedanceInputs, impedance |
| UI | risk-analytics-ui-web — **rebuild if columns missing** (see below) |

---

## UI Table Columns (Expected)

| Column | Data Source |
|--------|-------------|
| backOdds (L1) | `home_best_back`, `away_best_back`, `draw_best_back` |
| backSize (L1) | `home_best_back_size_l1`, ... |
| laySize (L1) | `home_best_lay_size_l1`, ... |
| backStake (top-N VWAP) | `impedanceInputs.home.backStake`, ... |
| layStake (top-N VWAP) | `impedanceInputs.home.layStake`, ... |
| Imbalance | `home_risk`, `away_risk`, `draw_risk` |
| **Size Impedance Index (L1)** | Computed: `computeSizeImpedanceL1(p)` from L1 sizes + odds |
| **Stake Impedance Index** | `impedance.home`, `impedance.away`, `impedance.draw` |

---

## Rebuild UI Web (if columns missing)

```bash
cd /opt/netbet
# Transfer web source (from Windows): scp -r risk-analytics-ui/web root@VPS:/opt/netbet/risk-analytics-ui/
docker compose build risk-analytics-ui-web --no-cache
docker compose up -d risk-analytics-ui-web --no-deps
```

Then hard refresh browser (Ctrl+F5) to clear cached SPA bundles.
