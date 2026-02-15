# Export Book Risk L3 — Usage

## Goal

Export snapshots for Book Risk L3 (Home/Away/Draw) with back ladder L1–L3. Outputs Parquet (long) and CSV (wide) under `data_exports/book_risk_l3/`.

## Requirements

```bash
pip install pandas pyarrow psycopg2-binary
```

## Usage

```bash
# Full date range (DB on localhost)
python scripts/export_book_risk_l3.py --date-from 2026-02-01 --date-to 2026-02-16

# With market filter
python scripts/export_book_risk_l3.py --date-from 2026-02-01 --date-to 2026-02-16 --market-ids 1.253489253

# With event filter
python scripts/export_book_risk_l3.py --date-from 2026-02-01 --date-to 2026-02-16 --event-ids 35215830

# Environment tag (for filename)
python scripts/export_book_risk_l3.py --date-from 2026-02-01 --date-to 2026-02-16 --env vps
```

## Environment

Set DB connection (same as backfill scripts):

- `POSTGRES_HOST` (default: localhost)
- `POSTGRES_PORT` (default: 5432)
- `POSTGRES_DB` (default: netbet)
- `POSTGRES_USER` (default: netbet)
- `POSTGRES_PASSWORD` (required)

For VPS DB via SSH tunnel:

```bash
ssh -L 5432:localhost:5432 -i ~/.ssh/id_ed25519_contabo root@158.220.83.195 -N &
export POSTGRES_PASSWORD=<your_password>
python scripts/export_book_risk_l3.py --date-from 2026-02-01 --date-to 2026-02-16 --env vps
```

## Output

- `book_risk_l3__<env><YYYY-MM-DD><HHMMSS>__part1.parquet` — Long format (one row per market_id, snapshot_at, side)
- `book_risk_l3__<env><YYYY-MM-DD><HHMMSS>__part1.csv` — Wide format (one row per market_id, snapshot_at)
- `book_risk_l3__<env><YYYY-MM-DD><HHMMSS>__metadata.json` — Run metadata
- `book_risk_l3__<env><YYYY-MM-DD><HHMMSS>.log` — Log file

## Schema

**Long format columns:** market_id, snapshot_at_utc, event_id, event_start_time_utc, home_team_name, away_team_name, market_type, total_volume, selection_id, selection_name, side (H|A|D), back_odds_l1..l3, back_size_l1..l3, market_status, in_play

**Wide format:** Same keys + H_back_odds_l1..l3, H_back_size_l1..l3, A_*, D_*
