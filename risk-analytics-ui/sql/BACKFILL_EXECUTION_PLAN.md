# Tier A Backfill Execution Plan

## Status: Ready for Execution

All migrations applied, audit completed, backfill script ready.

---

## Completed Steps

### ✅ STEP 1 — DB Migrations Applied

Both migrations successfully applied on VPS:

```bash
# Applied:
docker exec -i netbet-postgres psql -U netbet -d netbet < risk-analytics-ui/sql/migrations/2026-02-13_add_impedance_input_columns.sql
docker exec -i netbet-postgres psql -U netbet -d netbet < risk-analytics-ui/sql/migrations/2026-02-14_add_l1_size_columns.sql
```

**Result:** All 18 new columns exist in `market_derived_metrics`.

### ✅ STEP 2 — Audit Re-run

Post-migration audit shows:

- **Total snapshots:** 7,881
- **New columns:** 100% NULL (expected, before backfill)
- **Raw payload:** 100% available with full order book arrays
- **Eligibility:** **Tier A** confirmed (full deterministic reconstruction possible)

---

## Next Steps (Execute on VPS)

### STEP 3 — Run Tier A Backfill

**Location:** `/opt/netbet/betfair-rest-client/backfill_tier_a.py`

**Test run (first 200 rows):**
```bash
cd /opt/netbet/betfair-rest-client
python3 backfill_tier_a.py --limit 200 --dry-run
```

**Review output, then run actual update:**
```bash
python3 backfill_tier_a.py --limit 200
```

**Full backfill (all 7,881 rows):**
```bash
python3 backfill_tier_a.py --batch-size 500 2>&1 | tee backfill_$(date +%Y%m%d_%H%M%S).log
```

**Expected:** ~7,875 updated, ~6 skipped (missing metadata/payload), 0 errors

### STEP 4 — Post-Backfill Validation

**1. Re-run audit:**
```bash
docker exec -i netbet-postgres psql -U netbet -d netbet < risk-analytics-ui/sql/audit_snapshot_inventory.sql
```

**Expected:** Near-0% NULL for all new columns.

**2. Spot-check latest 5 rows:**
```bash
docker exec -i netbet-postgres psql -U netbet -d netbet -c "
SELECT snapshot_at,
       home_best_back_size_l1, away_best_back_size_l1, draw_best_back_size_l1,
       home_best_lay_size_l1,  away_best_lay_size_l1,  draw_best_lay_size_l1,
       home_back_stake, away_back_stake, draw_back_stake,
       home_lay_stake,  away_lay_stake,  draw_lay_stake
FROM market_derived_metrics
ORDER BY snapshot_at DESC
LIMIT 5;"
```

**Expected:** All fields populated with non-zero values.

**3. API validation:**
- Call `/api/events/{market_id}/timeseries` for an older market
- Confirm `home_best_back_size_l1`, `impedanceInputs.backStake`, etc. are populated
- UI should show values instead of "—"

---

## Backfill Script Details

**File:** `betfair-rest-client/backfill_tier_a.py`

**Features:**
- Uses exact production logic (`risk.py`, `main.py`)
- Processes in batches (default 500 rows)
- Updates only NULL fields (COALESCE)
- Logs progress and errors
- Dry-run mode for testing

**Production Logic Used:**
- **Imbalance:** `calculate_risk()` with `depth_limit=3`
- **Impedance:** `compute_impedance_index()` with `depth_limit=4`
- **L1 sizes:** `_best_back_lay()` extracts level 1 only
- **Validation:** Same rules (price > 1, size > 0)

**See:** `betfair-rest-client/README_BACKFILL.md` for full documentation.

---

## Expected Outcome

After backfill completes:

- **All 7,881 historical snapshots** will have:
  - L1 sizes populated
  - VWAP/top-N inputs populated
  - Impedance (raw) populated
  - Full consistency with current ingestion model

- **UI will show:**
  - backSize (L1) and laySize (L1) columns with real values
  - Size Impedance Index (L1) computed from real L1 sizes
  - Stake Impedance Index with VWAP/top-N inputs
  - No more "—" for historical data

- **API will return:**
  - All new fields populated in timeseries response
  - Historical snapshots match newly ingested snapshots

---

## Notes

- Backfill is **idempotent**: safe to re-run (only updates NULL fields)
- Errors are logged but don't stop the batch
- Process in batches to avoid long database locks
- Estimated runtime: ~10-15 minutes for 7,881 rows (depends on DB performance)
