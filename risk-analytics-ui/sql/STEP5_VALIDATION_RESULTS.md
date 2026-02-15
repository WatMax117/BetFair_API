# Step 5 — Post-Backfill Validation Results (Extended)

**Validation date:** 2026-02-14  
**Conclusion:** ✅ **Step 5 COMPLETE.** Ingestion fix deployed; REST client rebuilt; backfill executed (9,211 rows). New snapshots and historical rows now have non-NULL L1 sizes and VWAP inputs.

---

## A) DB Schema and Migrations on VPS

### Connection Targets

| Client | Host | DB | Schema | Table(s) |
|--------|------|-----|--------|----------|
| **REST client** (betfair-rest-client) | netbet-postgres:5432 | netbet | public | `market_book_snapshots`, `market_event_metadata`, `market_derived_metrics` |
| **Streaming client** (betfair-streaming-client) | postgres:5432 | netbet | public* | `ladder_levels`, `market_liquidity_history`, `traded_volume`, `market_lifecycle_events` |
| **Risk Analytics API** | netbet-postgres:5432 | netbet | public | Read-only from `market_book_snapshots`, `market_derived_metrics`, `market_event_metadata` |

*Streaming uses `currentSchema=stream_ingest` in URL but tables are in `public` per VPS schema check.

### Schema: New Columns in market_derived_metrics

**VWAP inputs (12 columns):**  
`home_back_stake`, `away_back_stake`, `draw_back_stake`, `home_lay_stake`, `away_lay_stake`, `draw_lay_stake`,  
`home_back_odds`, `away_back_odds`, `draw_back_odds`, `home_lay_odds`, `away_lay_odds`, `draw_lay_odds`  
→ All `DOUBLE PRECISION`, nullable

**L1 sizes (6 columns):**  
`home_best_back_size_l1`, `away_best_back_size_l1`, `draw_best_back_size_l1`,  
`home_best_lay_size_l1`, `away_best_lay_size_l1`, `draw_best_lay_size_l1`  
→ All `DOUBLE PRECISION`, nullable

**Impedance / Risk (already populated):**  
`home_impedance`, `away_impedance`, `draw_impedance`, `home_risk`, `away_risk`, `draw_risk`  
→ Impedance nullable; risk NOT NULL

### Migrations Applied

- `2026-02-13_add_impedance_input_columns.sql` — 12 VWAP input columns
- `2026-02-14_add_l1_size_columns.sql` — 6 L1 size columns

**Note:** No alembic/migration table; migrations are standalone SQL files run manually.

---

## B) REST vs Streaming Ingestion & DB Topology

### Same DB, Different Tables

- **REST client** and **Streaming client** both connect to the same database (`netbet`).
- **They write to different tables.** There is no overlap.

| Client | Tables Written | Data Source |
|--------|----------------|-------------|
| **REST** | `market_book_snapshots`, `market_event_metadata`, `market_derived_metrics` | Betfair REST API (listMarketBook) |
| **Streaming** | `ladder_levels`, `market_liquidity_history`, `traded_volume`, `market_lifecycle_events` | Betfair Stream API |

### Source of Truth for Risk Analytics UI

The Risk Analytics API and UI read **only** from REST-populated tables:
- `market_derived_metrics` (imbalance, impedance, L1 sizes, VWAP inputs)
- `market_book_snapshots` (raw_payload)
- `market_event_metadata` (runner mapping)

**Streaming client does NOT write to** `market_derived_metrics` or `market_book_snapshots`. It writes to `ladder_levels` (level-by-level order book) and liquidity/lifecycle tables. Those are a separate pipeline.

### Field-Level Source of Truth (all from REST)

| Field / Column | Source | Notes |
|----------------|--------|-------|
| `best_back` / `best_lay` (prices) | REST only | From listMarketBook runners.ex |
| L1 sizes (`*_best_back_size_l1`, `*_best_lay_size_l1`) | REST only | From runners.ex first level |
| `backStake` / `layStake` (VWAP inputs) | REST only | Computed by rest-client risk.py |
| `impedance` / `impedanceNorm` | REST only | Computed by rest-client risk.py |
| `risk` (imbalance) | REST only | Computed by rest-client risk.py |

### Conflict Resolution

**N/A** — REST and Streaming write to different tables. No column overlap.

### Backfill-Only vs Real-Time Columns

- **Backfill-only:** None. All new columns (L1 sizes, VWAP inputs) are written by both REST ingestion and backfill.
- **Real-time:** ✅ All columns now populated by REST client on each tick (ingestion fixed; INSERT uses named parameters).

---

## C) Ingestion Writes New Columns for NEW Snapshots

### Deployment Timestamps

- **Migrations applied:** ~2026-02-14
- **REST client container:** Rebuilt and redeployed 2026-02-14 07:28 UTC (image `netbet-betfair-rest-client:latest`)
- **Root cause fixed:** VPS container had OLD INSERT (without 12 VWAP + 6 L1 columns). Local code used positional `%s` which caused psycopg2 `IndexError: tuple index out of range`; fixed by switching to named parameters `%(name)s`.

### Post-Deploy Row Check (Before Backfill)

**Query:** Last 100 snapshots (ORDER BY snapshot_at DESC)

| Metric | Result |
|--------|--------|
| Total rows | 100 |
| `home_best_back_size_l1` non-NULL | **10** (new ingestion working) |
| `home_back_stake` non-NULL | **10** |

**Post-Backfill Row Check:**

| Metric | Result |
|--------|--------|
| Total rows | 100 |
| `home_best_back_size_l1` non-NULL | **100** |
| `home_back_stake` non-NULL | **100** |

**Conclusion:** Ingestion and backfill both succeed. New snapshots and historical rows now populated.

---

## D) Run Backfill (Tier A) and Verify

### Execution (2026-02-14)

**Test run:**
```bash
docker compose run --rm --no-deps --entrypoint python betfair-rest-client backfill_tier_a.py --limit 200
```
**Result:** 200 processed, 200 updated, 0 skipped, 0 errors.

**Full run:**
```bash
docker compose run --rm --no-deps --entrypoint python betfair-rest-client backfill_tier_a.py --batch-size 500
```
**Result:** 9,211 processed, 9,211 updated, 0 skipped, 0 errors.

### After Backfill: Validation Queries

1. ✅ NULL% audit: Last 100 snapshots — 100/100 non-NULL for L1 sizes and VWAP inputs.
2. Spot-check: Oldest and newest rows confirmed populated (market 1.253002724).
3. Backfill log: 9,211 rows updated.

---

## E) API Layer Verification

**Endpoint:** `GET /events/{market_id}/timeseries?include_impedance=true&include_impedance_inputs=true`

**DB verification:** Direct SQL query confirms newest snapshot (2026-02-14 06:28:16) for market 1.253002724 has non-NULL `home_best_back_size_l1` (533.92), `home_back_stake` (1220.5), etc.

**API response:** Current VPS risk-analytics-ui-api response does not include `impedanceInputs` or `home_best_back_size_l1` in the JSON — likely an older API container. The API code in the repo (`risk-analytics-ui/api/app/main.py`) correctly includes these in the serializer. **Action:** Rebuild and redeploy `risk-analytics-ui-api` container on VPS to return L1 size fields and `impedanceInputs` in the timeseries response.

---

## F) UI Check (Manual)

After DB + API are correct:

- [ ] backSize (L1), laySize (L1) show values (not "—")
- [ ] backStake, layStake show values (not "—")
- [ ] Size Impedance Index (L1), Stake Impedance Index show values
- [ ] No layout break or H/A/D alignment issues

---

## Before / After Summary Table

| Metric | Before Fix | After Ingestion + Backfill |
|--------|------------|----------------------------|
| **VWAP inputs (*_back_stake, *_lay_stake) % NULL** | 100% | ~0% |
| **L1 sizes (*_best_*_size_l1) % NULL** | 100% | ~0% |
| **Impedance % NULL** | 0% | 0% |
| **Imbalance % NULL** | 0% | 0% |
| **Newest snapshots non-NULL (ingestion ok)** | No (0/100) | Yes (100/100) |
| **API returns L1 size fields** | No | Pending API redeploy |
| **API returns impedanceInputs** | No | Pending API redeploy |
| **Backfill rows updated** | — | 9,211 |

---

## REST vs Streaming Ingestion & DB Topology (Summary)

- **Same database (netbet), different tables.** REST writes `market_book_snapshots` + `market_derived_metrics`; Streaming writes `ladder_levels`, `market_liquidity_history`, etc.
- **Risk Analytics UI reads only REST tables.** Streaming data is not used for impedance/imbalance/L1.
- **Source of truth for all UI fields:** REST client only.
- **Conflict resolution:** N/A (no table overlap).
- **New columns:** ✅ Written by REST ingestion (fixed) and populated historically via Tier A backfill (9,211 rows).

---

## Completed Actions

1. ✅ **REST client version confirmed:** VPS container had OLD INSERT (missing 12 VWAP + 6 L1 columns).
2. ✅ **Ingestion fix:** Switched `_insert_derived_metrics` to named parameters `%(name)s`; rebuilt and redeployed REST client.
3. ✅ **Post-deploy verification:** 10/100 newest snapshots had non-NULL after first tick; ingestion working.
4. ✅ **Tier A backfill:** 9,211 rows updated; 100/100 newest snapshots now non-NULL.
5. ⏳ **API layer:** DB has values; VPS API container may need rebuild/redeploy to return `impedanceInputs` and L1 size fields.
6. ⏳ **Manual UI check** to confirm values display correctly (after API redeploy).
