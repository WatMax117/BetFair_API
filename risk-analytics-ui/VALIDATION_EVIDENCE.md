# Risk Analytics UI — Final validation evidence

Use this checklist to confirm all enhancements are implemented and working before UAT handover.  
**Screenshots:** Capture from a running instance (e.g. `docker compose up` then http://localhost:3000).  
**API/DB proof:** Commands below can be run locally.

---

## 1. In-play toggle (UI proof)

**What to capture:**  
Screenshot of the **Leagues** page showing:

- The **“Include in-play events”** toggle (default ON).
- The **“In-play lookback (hours)”** input (e.g. 6) when in-play is ON.

**Confirmation:**  
Toggle OFF → refresh → event counts/events should respect the strict time window only.  
Toggle ON → events that opened in the last N hours (lookback) should appear even if they started before the window.

**Where:** Layer 0 — top of the Leagues accordion (time range + in-play controls).

---

## 2. Configurable index threshold (UI proof)

**What to capture:**  
Screenshot of the **Events** table (Layer 1) showing:

- The **“Index highlight threshold”** control (numeric input, default 500) in the Leagues section.
- At least **one row highlighted** (e.g. background colour) when its index exceeds the current threshold.

**Confirmation:**  
Change the threshold (e.g. 500 → 1000) and refresh; number of highlighted rows should change accordingly.

**Where:** Same Leagues panel as the in-play toggle; table is below per league.

---

## 3. Event Detail header (UI proof)

**What to capture:**  
Screenshot of **Layer 2 — Event Detail** header showing:

- **Spreads** (Home / Away / Draw) as “best_lay − best_back”.
- **“Copy market_id”** button.
- **“View latest raw snapshot (JSON)”** button (or equivalent label).

**Confirmation:**  
- Copy market_id → paste elsewhere to verify clipboard.  
- Click “View latest raw snapshot” → modal opens with JSON.

**Where:** Top of Event Detail, after opening an event from the Events table.

---

## 4. Raw snapshot view (API proof — curl)

If the API is running (e.g. http://localhost:8000):

**With a known market_id:**

```bash
curl -s "http://localhost:8000/events/MARKET_ID/latest_raw"
```

**Or use the script** (fetches first league/event if no market_id given):

```powershell
cd risk-analytics-ui/scripts
.\validate_latest_raw_api.ps1
# or with a specific market_id:
.\validate_latest_raw_api.ps1 "1.234567890"
```

**Expected response shape (first ~30 lines when pretty-printed):**

```json
{
  "market_id": "1.234567890",
  "snapshot_at": "2025-02-06T12:00:00",
  "raw_payload": {
    "marketId": "1.234567890",
    "totalMatched": 12345.67,
    "runners": [ ... ]
  }
}
```

- Status **200** and JSON with `market_id`, `snapshot_at`, and `raw_payload` (full marketBook) confirm the endpoint.
- **404** means no raw snapshot for that market in `market_book_snapshots`.

**Optional UI proof:**  
Screenshot of the **raw snapshot modal** open in the UI (after clicking “View latest raw snapshot”) showing the same JSON.

---

## 5. Depth & version tooltips (UI proof)

**What to capture:**  
Screenshot of the **Events** table (Layer 1) showing:

- An **info icon** (or similar) in a column (e.g. per row or in the header).
- **Tooltip** open with **depth_limit** and **calculation_version** for that event.

**Confirmation:**  
Hover or click the info icon → tooltip shows depth_limit and calculation_version so analysts can interpret data correctly.

**Where:** Events table — look for the (i) or info icon on each row.

---

## 6. Database index confirmation (DB proof)

On the **target environment** where the app runs, confirm the index on `market_derived_metrics` exists.

**Option A — List indexes on the table (PostgreSQL):**

From repo root (or `risk-analytics-ui`):

```bash
psql -U netbet -d netbet -f risk-analytics-ui/scripts/check_mdm_index.sql
```

Or run inline:

```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'market_derived_metrics'
ORDER BY indexname;
```

**Expected:** A row with `indexname = 'idx_mdm_market_snapshot_desc'` and `indexdef` containing `(market_id, snapshot_at DESC)`.

**Option B — Create if missing (idempotent):**

From repo root:

```bash
psql -U netbet -d netbet -f betfair-rest-client/scripts/ensure_mdm_index_desc.sql
```

Then run Option A again to confirm.

**Option C — \di+ style (size) in psql:**

```sql
\di+ idx_mdm_market_snapshot_desc
```

Or from a script:

```sql
SELECT i.relname AS index_name,
       pg_size_pretty(pg_relation_size(i.oid)) AS size
FROM pg_class t
JOIN pg_index ix ON t.oid = ix.indrelid
JOIN pg_class i ON i.oid = ix.indexrelid
WHERE t.relname = 'market_derived_metrics';
```

---

## Summary checklist

| # | Item | Evidence type | Done |
|---|------|----------------|------|
| 1 | In-play toggle + lookback on Leagues page | Screenshot + toggle behaviour | ☐ |
| 2 | Index threshold control + highlighted row(s) | Screenshot | ☐ |
| 3 | Event Detail: spreads, Copy market_id, View raw | Screenshot | ☐ |
| 4 | Raw snapshot: modal and/or curl `latest_raw` | Screenshot or curl output | ☐ |
| 5 | depth_limit / calculation_version tooltips in Events table | Screenshot | ☐ |
| 6 | Index `(market_id, snapshot_at DESC)` on `market_derived_metrics` | SQL query output | ☐ |

Once all rows are checked and evidence is attached (e.g. in a folder or Confluence), the task can be treated as complete for UAT handover.
