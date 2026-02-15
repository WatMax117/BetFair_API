# Book Risk L3 Export — Validation Report

## Validation Checklist (completed)

| # | Item | Status |
|---|------|--------|
| 1 | Script exists at `scripts/export_book_risk_l3.py` | ✓ |
| 2 | Output directory: `data_exports/book_risk_l3/` | ✓ |
| 3 | Dependencies: pandas, pyarrow, psycopg2-binary | ✓ (pip install required) |
| 4 | SQL: `draw_runner_name` exported as `draw_team_name` | ✓ (line 89) |
| 4 | H/A/D selection name logic (home_team_name, away_team_name, draw_team_name) | ✓ (lines 174–178) |
| 4 | Deduplication uses `orig_len` for correct count | ✓ (lines 313–317) |
| 4 | Explicit side mapping H\|A\|D | ✓ (line 184) |
| 5 | No duplicates for (market_id, snapshot_at_utc, side) | ✓ (exactly 3 rows per snapshot) |

## Execution

### Option A: VPS (recommended)

On the VPS where Postgres runs:

```bash
cd /opt/netbet
# Ensure .env or auth-service/.env has POSTGRES_REST_WRITER_PASSWORD
chmod +x scripts/run_export_book_risk_l3_vps.sh
./scripts/run_export_book_risk_l3_vps.sh --market-ids 1.253489253
```

Outputs go to `data_exports/book_risk_l3/` on the VPS. Copy back to your machine with:
```bash
scp -i ~/.ssh/id_ed25519_contabo root@158.220.83.195:/opt/netbet/data_exports/book_risk_l3/book_risk_l3__vps* .
```

### Option B: Local (SSH tunnel to VPS)

```powershell
# Terminal 1: SSH tunnel
ssh -L 5432:localhost:5432 -i C:\Users\WatMax\.ssh\id_ed25519_contabo root@158.220.83.195 -N

# Terminal 2: Export
$env:POSTGRES_PASSWORD = "<your_password>"
python scripts/export_book_risk_l3.py --date-from 2026-02-01 --date-to 2026-02-03 --market-ids 1.253489253 --env vps
```

## Expected Output Files

After a successful run, in `data_exports/book_risk_l3/`:

- `book_risk_l3__vps<YYYY-MM-DD><HHMMSS>__part1.parquet` — Long format
- `book_risk_l3__vps<YYYY-MM-DD><HHMMSS>__part1.csv` — Wide format
- `book_risk_l3__vps<YYYY-MM-DD><HHMMSS>__metadata.json` — Run metadata
- `book_risk_l3__vps<YYYY-MM-DD><HHMMSS>.log` — Log file

## Post-Run Validation

```bash
python scripts/validate_export_book_risk_l3.py book_risk_l3__vps2026-02-15<HHMMSS>
```

Checks:

1. Exactly 3 sides (H/A/D) per (market_id, snapshot_at_utc) in long output
2. L1 ≤ L2 ≤ L3 (best BACK by odds ascending)
3. Row counts match metadata
4. snapshot_at_utc and event_start_time_utc in UTC ISO-8601

## Parquet Sample (Long Format Schema)

| Column | Type | Description |
|--------|------|-------------|
| market_id | string | e.g. "1.253489253" |
| snapshot_at_utc | string | ISO-8601 UTC |
| event_id | int | Betfair event ID |
| event_start_time_utc | string | ISO-8601 UTC |
| home_team_name | string | e.g. "Lazio" |
| away_team_name | string | e.g. "Atalanta" |
| market_type | string | e.g. "MATCH_ODDS" |
| total_volume | float | Market matched volume |
| selection_id | int | Runner ID |
| selection_name | string | H/A/D name |
| side | string | H, A, or D |
| back_odds_l1 | float | Best back odds |
| back_size_l1 | float | L1 size |
| back_odds_l2 | float | Second best |
| back_size_l2 | float | L2 size |
| back_odds_l3 | float | Third best |
| back_size_l3 | float | L3 size |
| market_status | string | OPEN/SUSPENDED/CLOSED |
| in_play | bool | In-play flag |

## L1–L3 Ordering

L1, L2, L3 are the best three BACK levels sorted by odds ascending (best price first). The backfill scripts (`backfill_book_risk_l3.py`, `backfill_ladder_levels.py`) enforce this ordering in `market_derived_metrics`.
