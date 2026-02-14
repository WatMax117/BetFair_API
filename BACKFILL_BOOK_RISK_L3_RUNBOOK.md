# Backfill Book Risk L3 — Runbook

One-time backfill of historical snapshots: compute Book Risk L3 from `raw_payload` and write to `market_derived_metrics`.

## Prerequisites

- `raw_payload` in `market_book_snapshots` contains `runners` with `ex.availableToBack` ladders (top 3 levels).
- Same structure used by impedance backfill; if impedance backfill works, Book Risk L3 backfill will work.

## VPS commands

### 1. Dry run (small limit)

```bash
docker compose run --rm \
  -e PGOPTIONS=-c\ search_path=public \
  -e POSTGRES_HOST=netbet-postgres \
  -e POSTGRES_PASSWORD=$POSTGRES_PASSWORD \
  betfair-rest-client \
  python backfill_book_risk_l3.py --limit 50 --dry-run
```

### 2. Full backfill

```bash
docker compose run --rm \
  -e PGOPTIONS=-c\ search_path=public \
  -e POSTGRES_HOST=netbet-postgres \
  -e POSTGRES_PASSWORD=$POSTGRES_PASSWORD \
  betfair-rest-client \
  python backfill_book_risk_l3.py --limit 50000 --batch-size 100 2>&1 | tee backfill_book_risk_l3.log
```

### 3. Verify DB

```sql
SELECT snapshot_id, snapshot_at, home_book_risk_l3, away_book_risk_l3, draw_book_risk_l3
FROM market_derived_metrics
WHERE home_book_risk_l3 IS NOT NULL
ORDER BY snapshot_at ASC
LIMIT 3;
```

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--limit` | 10000 | Max snapshots to process |
| `--batch-size` | 100 | Commit every N rows |
| `--dry-run` | false | Log only, no updates |
