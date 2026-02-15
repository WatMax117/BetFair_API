# L2/L3 Ladder Fields Backfill — Summary

**Date:** 15 February 2026  
**VPS:** 158.220.83.195  
**Scope:** `market_derived_metrics` — `home/away/draw_back_odds_l2`, `_back_size_l2`, `_back_odds_l3`, `_back_size_l3`

---

## Step 1 — Baseline NULL Counts (Before)

| Column | NULL count | Total rows | % NULL |
|--------|------------|------------|--------|
| home_back_odds_l2 | 11,473 | 12,361 | 92.8% |
| home_back_odds_l3 | 11,475 | 12,361 | 92.9% |
| away_back_odds_l2 | 11,472 | 12,361 | 92.8% |
| away_back_odds_l3 | 11,473 | 12,361 | 92.9% |
| draw_back_odds_l2 | 11,471 | 12,361 | 92.8% |
| draw_back_odds_l3 | 11,472 | 12,361 | 92.8% |

---

## Step 2 — Raw Ladder Availability

Sample of 10 snapshots with NULL L2/L3 in derived metrics:

| snapshot_id | market_id | atb_levels |
|-------------|-----------|------------|
| 1 | 1.253641180 | 2 |
| 2 | 1.253638564 | 3 |
| 3 | 1.253641180 | 2 |
| ... | ... | ... |

**Conclusion:** Raw `availableToBack` in `market_book_snapshots` contains 2–3 levels for most snapshots. Derived L2/L3 columns were NULL because they were never populated — backfill required.

---

## Step 3 — Backfill Execution

| Action | Result |
|--------|--------|
| Dry run (limit 200) | 200 would be updated; 0 skipped; 0 errors |
| Full backfill (limit 50000, batch-size 500) | **11,475 updated**; 0 skipped; 0 errors |

**Script:** `betfair-rest-client/backfill_ladder_levels.py`  
**Run script:** `scripts/run_backfill_ladder_levels_vps.sh`  
**Method:** Extracts `availableToBack[1]` (L2) and `availableToBack[2]` (L3) per runner; maps via `market_event_metadata`; updates derived columns.

---

## Step 4 — Post-Backfill Validation (After)

| Column | NULL count | Total rows | % NULL |
|--------|------------|------------|--------|
| home_back_odds_l2 | **47** | 12,361 | **0.4%** |
| home_back_odds_l3 | **137** | 12,361 | **1.1%** |
| away_back_odds_l2 | **46** | 12,361 | **0.4%** |
| away_back_odds_l3 | **117** | 12,361 | **0.9%** |
| draw_back_odds_l2 | **39** | 12,361 | **0.3%** |
| draw_back_odds_l3 | **109** | 12,361 | **0.9%** |

**Interpretation:** Remaining NULLs are expected — snapshots where raw `availableToBack` has fewer than 2 levels (L2) or fewer than 3 levels (L3). No artificial zeros; no overwritten valid rows.

---

## Deliverables

| Item | Location |
|------|----------|
| Backfill script | `betfair-rest-client/backfill_ladder_levels.py` |
| Run script (VPS) | `scripts/run_backfill_ladder_levels_vps.sh` |
| Verify SQL | `scripts/verify_l2_l3_nulls.sql` |
| Raw ladder check SQL | `scripts/check_raw_ladder_depth.sql` |
| Dockerfile | Updated to `COPY backfill_ladder_levels.py` (for future builds) |

---

## Commands Used

```bash
# Verify NULL counts
cat scripts/verify_l2_l3_nulls.sql | docker exec -i netbet-postgres psql -U netbet -d netbet

# Dry run
bash scripts/run_backfill_ladder_levels_vps.sh --limit 200 --dry-run

# Full backfill
bash scripts/run_backfill_ladder_levels_vps.sh --limit 50000 --batch-size 500
```

---

*L2/L3 backfill complete. NULL only where raw ladder depth is insufficient.*
