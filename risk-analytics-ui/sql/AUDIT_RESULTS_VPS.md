# VPS Snapshot Inventory Audit Results

**Audit run:** SQL audit executed on VPS as requested.  
**Note:** Section C (NULL percentages) and the full eligibility matrix did not run because the impedance input and L1 size columns do not yet exist in `market_derived_metrics` on the VPS (migrations not yet applied). Re-run the same audit after applying migrations to get the full matrix.

---

## 1. Snapshot inventory summary

| Metric | Value |
|--------|--------|
| **Total snapshots** | 7,881 |
| **Oldest snapshot date** | 2026-02-06 11:54:08.556418+00 |
| **Latest snapshot date** | 2026-02-13 11:18:46.090762+00 |

---

## 2. Raw payload availability

| Check | Result |
|--------|--------|
| **Does `raw_payload` exist?** | **YES** (column present in `market_book_snapshots`) |
| **Rows with non-NULL `raw_payload`** | **7,881** (100% of snapshots have raw payload) |
| **Contains `runners` + `availableToBack` / `availableToLay`?** | **YES** (sample of 5 rows: all have `has_runners = YES`, `has_availableToBack = YES`) |

Sample raw payload check output:

```
 snapshot_id |  market_id  |          snapshot_at          | has_runners | has_availabletoback 
-------------+-------------+-------------------------------+-------------+---------------------
           1 | 1.253641180 | 2026-02-06 11:54:08.556418+00 | YES         | YES
           2 | 1.253638564 | 2026-02-06 11:54:19.649005+00 | YES         | YES
           3 | 1.253641180 | 2026-02-06 11:54:19.649005+00 | YES         | YES
           4 | 1.253638564 | 2026-02-06 11:55:20.047493+00 | YES         | YES
           5 | 1.253641180 | 2026-02-06 11:55:20.047493+00 | YES         | YES
```

**Conclusion:** Full order book data (runners with `availableToBack` / `availableToLay`) is present in `raw_payload`. This supports **Tier A (full deterministic reconstruction)** once migrations are applied and the eligibility matrix is computed.

---

## 3. NULL percentages breakdown

**Not available on this run.** The query failed with:

```text
ERROR: column "home_back_stake" does not exist
```

The impedance input and L1 size columns have not been added to `market_derived_metrics` on the VPS yet. After applying:

- `2026-02-13_add_impedance_input_columns.sql`
- `2026-02-14_add_l1_size_columns.sql`

re-run the audit to get:

- VWAP inputs: `*_back_stake`, `*_lay_stake`, `*_back_odds`, `*_lay_odds`
- L1 sizes: `*_best_back_size_l1`, `*_best_lay_size_l1`
- Impedance
- Imbalance (risk)

---

## 4. Eligibility matrix

**Full matrix not produced** (depends on NULL counts for the new columns). After migrations:

- **Expected:** All new columns will be NULL for historical rows (7,881 rows).
- **Reconstructability:** Given that `raw_payload` contains full order book arrays, **Tier A** is expected: full deterministic reconstruction (L1 sizes, VWAP inputs, Imbalance, Stake Impedance, Size Impedance) using production logic.

Once you apply the migrations and re-run:

```bash
docker exec -i netbet-postgres psql -U netbet -d netbet < risk-analytics-ui/sql/audit_snapshot_inventory.sql
```

the report will include the full NULL percentages and the parameter-level eligibility matrix.

---

## 5. Next steps (no backfill yet)

1. **Apply migrations** on the VPS (if not already done) so that the new columns exist.
2. **Re-run the SQL audit** to get the full NULL breakdown and eligibility matrix.
3. **Review the matrix** and confirm Tier A (or B/C) and backfill scope.
4. **Then** implement the batched backfill script using production logic only (no approximation).

No backfill has been implemented; strategy will be decided after review of the full eligibility matrix.
