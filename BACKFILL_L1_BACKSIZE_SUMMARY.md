# L1 Back Size Backfill — Summary

**Date:** 15 February 2026  
**VPS:** 158.220.83.195  
**Scope:** `home_best_back_size_l1`, `away_best_back_size_l1`, `draw_best_back_size_l1` in `market_derived_metrics`

---

## Step 1 — Baseline (Before)

| Column | NULL count | Total rows | % NULL |
|--------|------------|------------|--------|
| home_best_back_size_l1 | 980 | 12,401 | 7.9% |
| away_best_back_size_l1 | 980 | 12,401 | 7.9% |
| draw_best_back_size_l1 | 980 | 12,401 | 7.9% |

**Recent 7 days:** 980 NULL per column (gap ongoing — not historical only).

**Sample snapshot_ids (5):** 12390, 12388, 12391, 12386, 12389  
**Sample market_ids:** 1.253503553, 1.253495293, 1.253504079, 1.253489918, 1.253495440

---

## Step 2 — Raw Ladder Availability

Sample snapshots with NULL L1 backsize showed:
- `availableToBack` exists with length 2–3
- Dry run confirmed `availableToBack[0].size` is present and extractable

Raw ladder evidence: Python extraction succeeded in dry run (e.g. H=130.28, A=10.44, D=114.93 for snapshot 9454).

---

## Step 3 — Backfill Script

**Script:** `betfair-rest-client/backfill_l1_backsize.py`  
**Logic:** Extract `availableToBack[0].size` per runner; map via `market_event_metadata`; UPDATE using COALESCE to avoid overwriting non-NULL values.  
**Safety:** Only updates rows where current value is NULL; leaves NULL where raw ladder has no L1.

---

## Step 4 — Execution

| Action | Result |
|--------|--------|
| Dry run (limit 200) | 200 would be updated; 0 skipped; 0 errors |
| Full backfill (limit 50000, batch-size 500) | **980 updated**; 0 skipped; 0 errors |

**Total rows updated:** 980

---

## Step 5 — Post-Backfill (After)

| Column | NULL count | Total rows | % NULL |
|--------|------------|------------|--------|
| home_best_back_size_l1 | **1** | 12,401 | **0.01%** |
| away_best_back_size_l1 | **0** | 12,401 | **0%** |
| draw_best_back_size_l1 | **0** | 12,401 | **0%** |

**Remaining NULL:** 1 row has `home_best_back_size_l1` NULL — expected where raw ladder has no L1 back level for that runner.

---

## Before/After NULL Counts Table

| Column | Before | After |
|--------|--------|-------|
| home_best_back_size_l1 | 980 | 1 |
| away_best_back_size_l1 | 980 | 0 |
| draw_best_back_size_l1 | 980 | 0 |

---

## API Snippet

**Endpoint:** `GET /debug/markets/{market_id}/snapshots?limit=1`

**Sample response (market 1.253489253, post-backfill):**

```json
{
  "snapshot_at": "2026-02-14T17:51:58.466790+00:00",
  "market_id": "1.253489253",
  "home_best_back_size_l1": 21.53,
  "away_best_back_size_l1": 164.01,
  "draw_best_back_size_l1": 614.0,
  "home_back_odds_l2": 10.0,
  "home_back_size_l2": 343.34,
  "away_back_odds_l2": 1.49,
  "away_back_size_l2": 3345.92,
  "draw_back_odds_l2": 4.0,
  "draw_back_size_l2": 1876.42
}
```

The API already includes `*_best_back_size_l1` in its SELECT and serializer. No redeploy needed.

---

## Redeploy Required?

**No.** The API and UI already SELECT and serialize `*_best_back_size_l1` from the DB. Only DB values were updated; no code changes; no redeploy.

---

## Deliverables

| Item | Location |
|------|----------|
| Backfill script | `betfair-rest-client/backfill_l1_backsize.py` |
| Run script (VPS) | `scripts/run_backfill_l1_backsize_vps.sh` |
| Verify SQL | `scripts/verify_l1_backsize_nulls.sql` |
| Sample SQL | `scripts/sample_l1_null_rows.sql` |
| Raw ladder check | `scripts/check_raw_l1_backsize.sql` |
