# Backfill Audit and Eligibility

## Purpose

Before implementing backfill, we audit historical snapshot data to determine:
- What raw data exists (raw_payload in market_book_snapshots)
- Which parameters can be mathematically reconstructed
- Eligibility tiers for backfill

## Running the Audit

On the VPS:

```bash
cd /opt/netbet
python3 risk-analytics-ui/scripts/audit_snapshot_inventory.py
```

Or if running from a different location, set DB connection in the script or use environment variables.

## Expected Output

The audit produces:

1. **Snapshot inventory**: total count, oldest/latest dates
2. **Raw payload availability**: whether raw_payload exists and contains order book arrays
3. **NULL percentages**: breakdown by parameter
4. **Eligibility matrix**: reconstructability tier for each parameter

## Eligibility Tiers

- **Tier A (Full reconstruction)**: raw_payload contains full `availableToBack`/`availableToLay` arrays → can recompute all parameters using production logic
- **Tier B (Partial reconstruction)**: only best-level prices/sizes exist → can backfill L1 sizes and Size Impedance (L1) only
- **Tier C (Not allowed)**: insufficient raw data → leave NULL, do not approximate

## Next Steps

After audit:
1. Review eligibility matrix
2. If Tier A eligible: implement full backfill script
3. If Tier B eligible: implement partial backfill (L1 sizes only)
4. If Tier C: document limitations, no backfill
