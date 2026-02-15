# Deploy Book Risk L3 to VPS — Runbook

## Pre-check (local)

Confirm the following are present before deploying:

| Item | Location | Status |
|------|----------|--------|
| `compute_book_risk_l3()` | `betfair-rest-client/risk.py` | ✓ |
| Persistence (3 columns) | `betfair-rest-client/main.py` in `_ensure_three_layer_tables`, `_insert_derived_metrics`, metrics dict | ✓ |
| Tests | `betfair-rest-client/tests/test_risk.py` — `test_book_risk_l3_*` | ✓ Run: `pytest betfair-rest-client/tests/test_risk.py -k "book_risk_l3" -v` |
| API snapshots | `risk-analytics-ui/api/app/main.py` — SELECT includes `d.home_book_risk_l3`, etc. | ✓ |
| API timeseries | Same file — bucketed query + _serialize include the 3 fields (always, not only when include_impedance=true) | ✓ |
| Web types | `risk-analytics-ui/web/src/api.ts` — `TimeseriesPoint` and `DebugSnapshotRow` | ✓ |
| UI table | `risk-analytics-ui/web/src/components/EventDetail.tsx` — "Book Risk L3 (H/A/D)" column **before** Imbalance | ✓ |

## 1. Record commit hash to deploy

Commit all Book Risk L3 changes:

```bash
git add betfair-rest-client/risk.py betfair-rest-client/main.py betfair-rest-client/tests/test_risk.py betfair-rest-client/BOOK_RISK_L3_SPEC.md risk-analytics-ui/api/app/main.py risk-analytics-ui/web/src/api.ts risk-analytics-ui/web/src/components/EventDetail.tsx
git commit -m "Add Book Risk L3 index; deploy runbook and UI column before Imbalance"
git log -1 --format=%H
```

Use that hash as “commit hash deployed” in your report.

## 2. Transfer code to VPS and deploy

From your **local machine** (PowerShell), using your SSH key and VPS IP (e.g. `158.220.83.195`):

```powershell
# Replace with your key and VPS IP
$VPS = "root@158.220.83.195"
$KEY = "C:\Users\WatMax\.ssh\id_ed25519_contabo"

# Optional: sync repo (if you use git on VPS)
# ssh -i $KEY $VPS "cd /opt/netbet && git pull"

# Or SCP updated folders
scp -i $KEY -r betfair-rest-client risk-analytics-ui $VPS:/opt/netbet/
```

Then **on the VPS** (SSH in and run):

### 2.1 Deploy betfair REST client (ingestion + DB columns)

```bash
cd /opt/netbet
docker compose build betfair-rest-client --no-cache
docker compose up -d betfair-rest-client --no-deps
docker logs netbet-betfair-rest-client --tail 80
```

Confirm no SQL errors. The client’s `_ensure_three_layer_tables()` adds the 3 columns on first run if missing.

### 2.2 DB: confirm columns

```bash
docker exec -i netbet-postgres psql -U netbet -d netbet -c "
SELECT column_name FROM information_schema.columns
WHERE table_name = 'market_derived_metrics'
  AND column_name IN ('home_book_risk_l3', 'away_book_risk_l3', 'draw_book_risk_l3');
"
```

Expected: 3 rows. After a few minutes of ingestion, check for non-NULL values:

```bash
docker exec -i netbet-postgres psql -U netbet -d netbet -c "
SELECT snapshot_id, snapshot_at, home_book_risk_l3, away_book_risk_l3, draw_book_risk_l3
FROM market_derived_metrics
ORDER BY snapshot_at DESC
LIMIT 3;
"
```

### 2.3 Deploy risk-analytics API

```bash
cd /opt/netbet
docker compose build risk-analytics-ui-api --no-cache
docker compose up -d risk-analytics-ui-api --no-deps
docker logs risk-analytics-ui-api --tail 80
```

### 2.4 Deploy UI (risk-analytics-ui-web)

```bash
cd /opt/netbet
docker compose build risk-analytics-ui-web --no-cache
docker compose up -d risk-analytics-ui-web --no-deps
docker logs risk-analytics-ui-web --tail 80
```

## 3. Verification

### A) DB

Same as 2.2: newest rows have non-NULL `home_book_risk_l3`, `away_book_risk_l3`, `draw_book_risk_l3`.

### B) API (from VPS or your machine)

Pick a `market_id` that has recent snapshots (e.g. from the DB query above).

```bash
# Debug snapshots (limit=1)
curl -s "http://localhost:8000/debug/markets/<MARKET_ID>/snapshots?limit=1" | jq '.[0] | {snapshot_at, home_book_risk_l3, away_book_risk_l3, draw_book_risk_l3}'

# Timeseries (same market)
curl -s "http://localhost:8000/events/<MARKET_ID>/timeseries?from_ts=2026-02-01T00:00:00Z&to_ts=2026-02-15T00:00:00Z&interval_minutes=15" | jq '.[0] | {snapshot_at, home_book_risk_l3, away_book_risk_l3, draw_book_risk_l3}'
```

If the UI is behind Apache/nginx, use the public URL and path (e.g. `http://158.220.83.195/api/...`) for the same calls.

### C) UI

1. Open the app (e.g. `http://158.220.83.195/` or your domain).
2. Hard refresh (Ctrl+F5).
3. Go to an event → market so the “Last 10 snapshots” table is visible.
4. Confirm:
   - Column **“Book Risk L3 (H/A/D)”** is present.
   - It appears **before** the **“Imbalance”** column.
   - Values show H/A/D (or — when null).

**Table column order (expected):**  
… → backStake → layStake → **Book Risk L3 (H/A/D)** → **Imbalance** → Size Impedance Index (L1) → Stake Impedance Index → total_volume.

## 4. Deliverables (report back)

- **VPS timestamp of deploy:** e.g. `2026-02-XX HH:MM TZ`
- **Commit hash deployed:** from `git log -1 --format=%H` after commit
- **Containers:** confirm rest-client, api, web rebuilt and restarted without errors
- **DB sample:** one row with `snapshot_at` + `home_book_risk_l3`, `away_book_risk_l3`, `draw_book_risk_l3`
- **API snippet:** JSON fragment showing the three fields from snapshots or timeseries
- **UI:** screenshot of the table with “Book Risk L3 (H/A/D)” before “Imbalance”

## Definition of done

- [ ] New snapshots have non-NULL book_risk_l3 values in DB.
- [ ] API returns book_risk_l3 in both debug snapshots and timeseries.
- [ ] UI shows “Book Risk L3 (H/A/D)” and it appears before Imbalance columns.
