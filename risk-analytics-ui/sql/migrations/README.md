# DB migrations (risk-analytics-ui)

Apply migrations **before** rebuilding services so the schema is in place when the rest-client and API start.

## Final column set (market_derived_metrics)

After both migrations, the table must have:

- **Impedance inputs (VWAP / top-N):**  
  `home_back_stake`, `away_back_stake`, `draw_back_stake`  
  `home_lay_stake`, `away_lay_stake`, `draw_lay_stake`  
  `home_back_odds`, `away_back_odds`, `draw_back_odds`  
  `home_lay_odds`, `away_lay_odds`, `draw_lay_odds`
- **Best-level (L1) sizes:**  
  `home_best_back_size_l1`, `away_best_back_size_l1`, `draw_best_back_size_l1`  
  `home_best_lay_size_l1`, `away_best_lay_size_l1`, `draw_best_lay_size_l1`
- **Existing:** imbalance (home/away/draw risk), impedance (raw → Stake Impedance Index), total_volume, snapshot_at, etc.

## VPS: apply migration

```bash
# 1) SSH (from repo root or with correct paths)
ssh -F .ssh/config <VPS_ALIAS>
# or: ssh -i /path/to/key root@158.220.83.195

# 2) Ensure migration files are on VPS (e.g. under /opt/netbet), then apply in order:
cd /opt/netbet
docker exec -i netbet-postgres psql -U netbet -d netbet < risk-analytics-ui/sql/migrations/2026-02-13_add_impedance_input_columns.sql
docker exec -i netbet-postgres psql -U netbet -d netbet < risk-analytics-ui/sql/migrations/2026-02-14_add_l1_size_columns.sql

# 3) Verify columns exist
docker exec -i netbet-postgres psql -U netbet -d netbet -c "\d market_derived_metrics"

# 4) Rebuild and redeploy
docker compose -p netbet build --no-cache
docker compose -p netbet up -d --force-recreate
```

## Validate data after deploy

After a fresh snapshot is ingested:

```sql
SELECT snapshot_at,
       home_back_stake, home_lay_stake,
       away_back_stake, away_lay_stake,
       draw_back_stake, draw_lay_stake
FROM market_derived_metrics
ORDER BY snapshot_at DESC
LIMIT 5;
```

If older rows stay NULL, run the backfill (see project backfill docs).

## Backfill Audit and Eligibility

Before implementing backfill, audit historical data to determine reconstructability:

### Run Audit

**SQL version (recommended for VPS):**
```bash
docker exec -i netbet-postgres psql -U netbet -d netbet < risk-analytics-ui/sql/audit_snapshot_inventory.sql
```

**Python version (if psycopg2 available):**
```bash
python3 risk-analytics-ui/scripts/audit_snapshot_inventory.py
```

### Eligibility Tiers

- **Tier A (Full reconstruction)**: `raw_payload` contains full `availableToBack`/`availableToLay` arrays → can recompute all parameters using production logic
- **Tier B (Partial reconstruction)**: only best-level prices/sizes exist → can backfill L1 sizes and Size Impedance (L1) only
- **Tier C (Not allowed)**: insufficient raw data → leave NULL, do not approximate

### Backfill Rules

Backfill is allowed ONLY if necessary raw inputs exist:

- **Tier A**: Recompute L1 sizes, VWAP/top-N stake/odds, Imbalance, Stake Impedance, Size Impedance using exact production logic
- **Tier B**: Backfill only L1 size fields and Size Impedance (L1); do NOT attempt VWAP or stake-based impedance
- **Tier C**: Leave NULL; do NOT approximate or infer from indices

See `risk-analytics-ui/scripts/README_BACKFILL_AUDIT.md` for details.
