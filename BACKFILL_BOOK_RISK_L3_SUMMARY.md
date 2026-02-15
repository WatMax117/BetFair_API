# Book Risk L3 Full Backfill — Execution Summary

**Date:** 15 February 2026  
**VPS:** 158.220.83.195  
**Scope:** All snapshots in `market_derived_metrics` where `book_risk_l3` was NULL

---

## Definition of Done

| Criterion | Status |
|-----------|--------|
| Historical Book Risk L3 populated wherever ladder data exists | ✅ Complete |
| NULL values only where raw ladder data missing | ✅ Confirmed (0 NULL remaining) |
| Lazio v Atalanta market has continuous Book Risk values | ✅ Complete |
| System ready for statistical and historical analysis | ✅ Yes |

---

## Pre-checks (baseline)

| Metric | Value |
|--------|-------|
| NULL count (home_book_risk_l3) | 1,720 |
| Total rows in market_derived_metrics | 12,331 |
| backfill_book_risk_l3.py | Present |
| REST client container | Running (no conflict; backfill updates NULL rows only) |
| DB | Healthy |

---

## Execution

| Step | Action | Result |
|------|--------|--------|
| 1 | Dry run (limit 200) | 200 rows would be updated; 0 skipped; 0 errors |
| 2 | Small batch (limit 200) | 200 updated; 0 skipped; 0 errors |
| 3 | Full backfill (limit 50000, batch-size 500) | 1,520 updated; 0 skipped; 0 errors |

**Total rows updated:** 1,720 (200 + 1,520)

---

## Post-backfill validation

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| NULL count | 1,720 | **0** | -100% |
| Total rows | 12,331 | 12,331 | — |
| % remaining NULL | 13.9% | **0%** | — |

**NULL rows remaining:** 0 — all snapshots with ladder data now have Book Risk L3 populated.

---

## Lazio v Atalanta (market 1.253489253) — Specific validation

**Book Risk L3 at 5 key time points (post-backfill):**

| Time point | snapshot_at | Home | Away | Draw |
|------------|-------------|------|------|------|
| T-6h | 2026-02-14 11:01:50 | -8,256.37 | -17,504.71 | +30,587.82 |
| T-1h | 2026-02-14 16:01:58 | -15,245.80 | -15,911.20 | +35,594.08 |
| Kickoff | 2026-02-14 17:02:00 | -14,638.94 | -8,010.85 | +23,467.06 |
| Mid-match | 2026-02-14 17:47:01 | -5,570.85 | -118.04 | +1,997.28 |
| Final 15 min | 2026-02-14 17:51:58 | -2,000.97 | -1,201.19 | +3,069.65 |

**Result:** All five checkpoints populated. Lazio v Atalanta report gap resolved.

---

## Deliverables

| Deliverable | Location |
|-------------|----------|
| Backfill log | VPS: stdout captured (tee failed due to PowerShell; output in session) |
| NULL count before/after | 1,720 → 0 |
| Example market (fully populated) | Lazio v Atalanta (1.253489253) |
| Updated Lazio report | `LAZIO_ATALANTA_MARKET_REPORT.md` |
| Lazio report SQL output (post-backfill) | `lazio_atalanta_report_v2.out` |

---

## Commands used

```bash
# Pre-check (baseline)
cat scripts/backfill_precheck.sql | docker exec -i netbet-postgres psql -U netbet -d netbet -t

# Dry run
bash scripts/run_backfill_book_risk_l3_vps.sh --limit 200 --dry-run

# Small batch
bash scripts/run_backfill_book_risk_l3_vps.sh --limit 200

# Full backfill
bash scripts/run_backfill_book_risk_l3_vps.sh --limit 50000 --batch-size 500

# Post-validation
cat scripts/report_lazio_atalanta_market_public.sql | docker exec -i netbet-postgres psql -U netbet -d netbet > /tmp/lazio_atalanta_report_v2.out
```

---

*Integrity phase closed. System ready for historical performance analysis.*
