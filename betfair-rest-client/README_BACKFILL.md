# Tier A Backfill: Full Deterministic Reconstruction

## Overview

The `backfill_tier_a.py` script recomputes missing parameters from `raw_payload` using the exact same production logic as ingestion:

- **L1 sizes**: `*_best_back_size_l1`, `*_best_lay_size_l1`
- **VWAP/top-N inputs**: `*_back_stake`, `*_back_odds`, `*_lay_stake`, `*_lay_odds`
- **Impedance (raw)**: `*_impedance`, `*_impedance_norm`
- **Imbalance (risk)**: `*_risk` (if NULL)
- **Total volume**: `total_volume` (if NULL)

## Requirements

- Python 3 with `psycopg2-binary`
- Access to PostgreSQL database
- Production code (`risk.py`, `main.py`) in the same directory

## Usage

### On VPS (recommended)

```bash
cd /opt/netbet/betfair-rest-client

# Test run: process first 200 rows (dry run)
python3 backfill_tier_a.py --limit 200 --dry-run

# Test run: process first 200 rows (actual update)
python3 backfill_tier_a.py --limit 200

# Full backfill: all rows (batch size 500)
python3 backfill_tier_a.py --batch-size 500

# Full backfill with progress logging
python3 backfill_tier_a.py --batch-size 500 2>&1 | tee backfill_$(date +%Y%m%d_%H%M%S).log
```

### Options

- `--batch-size N`: Process in batches of N rows (default: 500)
- `--limit M`: Limit to first M rows (for testing)
- `--dry-run`: Show what would be updated without making changes

## Production Logic

The script uses the exact same functions and parameters as ingestion:

- **Imbalance**: `calculate_risk()` with `depth_limit=3` (DEPTH_LIMIT)
- **Impedance**: `compute_impedance_index()` with `depth_limit=4` (IMPEDANCE_DEPTH_LEVELS)
- **L1 sizes**: `_best_back_lay()` extracts level 1 only
- **Validation**: Same rules (price > 1, size > 0)

## Output

The script logs:
- Progress every `batch_size` rows
- Final summary: processed, updated, skipped, errors

Example:
```
2026-02-13 12:00:00 [INFO] Found 7881 rows needing backfill
2026-02-13 12:00:05 [INFO] Progress: 500/7881 processed, 498 updated, 2 skipped, 0 errors
...
2026-02-13 12:15:00 [INFO] Backfill complete: 7881 processed, 7875 updated, 6 skipped, 0 errors
```

## Post-Backfill Validation

After running backfill:

1. **Re-run audit**:
   ```bash
   docker exec -i netbet-postgres psql -U netbet -d netbet < risk-analytics-ui/sql/audit_snapshot_inventory.sql
   ```
   Expected: near-0% NULL for new columns.

2. **Spot-check latest rows**:
   ```bash
   docker exec -i netbet-postgres psql -U netbet -d netbet -c "
   SELECT snapshot_at,
          home_best_back_size_l1, away_best_back_size_l1, draw_best_back_size_l1,
          home_back_stake, away_back_stake, draw_back_stake
   FROM market_derived_metrics
   ORDER BY snapshot_at DESC
   LIMIT 5;"
   ```

3. **API validation**: Confirm timeseries returns populated fields for older snapshots.

## Notes

- Only NULL fields are updated (COALESCE preserves existing values)
- Rows without `raw_payload` or runner metadata are skipped
- Errors are logged but don't stop the batch
- Process in batches to avoid long locks
