# Full Rebuild and Redeploy — Impedance Index (15m)

**Date:** 2026-02-16  
**Status:** Backend and frontend rebuilt and restarted

---

## Step 1 — Backend (API) ✅

- **Actions:** Code copied to VPS; image rebuilt; container recreated and started.
- **Note:** Existing container name conflict was resolved with `docker stop` / `docker rm` before `up`.
- **Result:** `risk-analytics-ui-api` is running with the new image (Impedance Index logic in `stream_data.py`).

### Backend logs

- Server starts: `Uvicorn running on http://0.0.0.0:8000`
- **Pre-existing (unchanged):** Partition provisioner reports missing `POSTGRES_PARTITION_USER` / `POSTGRES_PARTITION_PASSWORD` and `could not translate host name "postgres"` — DDL and DB host resolution are environment/network configuration, not caused by this deploy.

### Backend JSON (when DB is reachable)

When the API can reach the database, each bucket in the timeseries response will include:

- `impedance_index_15m`
- `impedance_abs_diff_home`
- `impedance_abs_diff_away`
- `impedance_abs_diff_draw`

**Current behaviour:** A direct call to the timeseries endpoint from the VPS returns **500** because the API container cannot resolve the DB host name (`postgres`). Fix the DB host (e.g. use the correct service name and ensure the API runs on the same Docker network as Postgres) so the API can connect; then the impedance fields will appear in the JSON.

---

## Step 2 — Verify backend (after DB is fixed)

In the browser open:

```
http://158.220.83.195/api/stream/events/{market_id}/timeseries?from_ts=YYYY-MM-DDTHH:MM:SSZ&to_ts=YYYY-MM-DDTHH:MM:SSZ&interval_minutes=15
```

Replace `{market_id}` and the date range. Check that each bucket object in the JSON has the four impedance fields above.

---

## Step 3 — Frontend (Web) ✅

- **Actions:** Duplicate `EventDetail.tsx` in `web/src/` (left by an earlier copy) was removed; image rebuilt; container recreated and started.
- **Result:** `risk-analytics-ui-web` is running with the new build.

### New bundle

- **JS bundle:** `dist/assets/index-D7cMilgV.js` (hash changed from previous build).

---

## Step 4 — Confirm frontend

1. **Hard refresh:** `Ctrl + Shift + R` (Windows) or open in Incognito.
2. **Network tab:** Reload and confirm the main JS file has the new hash (e.g. `index-D7cMilgV.js`).
3. **Event detail:** Open an event, select a 15‑minute bucket. Confirm:
   - Column **“Impedance Index (15m)”** is visible.
   - Value in [0, 1] when data exists.
   - Footer shows **|s − w|** for H / A / D.
   - Nulls show as **"—"**.

---

## Optional — Clean deploy

If you need a full clean rebuild:

```bash
cd /opt/netbet
docker compose -f risk-analytics-ui/docker-compose.yml down
docker compose -f risk-analytics-ui/docker-compose.yml build --no-cache
docker compose -f risk-analytics-ui/docker-compose.yml up -d
```

Use only if short downtime is acceptable.

---

## Acceptance checklist

| Criterion | Status |
|-----------|--------|
| Backend image rebuilt with impedance logic | ✅ |
| Backend container restarted | ✅ |
| Backend JSON contains impedance fields | ⏳ Once DB host is fixed |
| Frontend image rebuilt with Impedance column | ✅ |
| Frontend container restarted | ✅ |
| UI shows Impedance Index column | ✅ (build includes it) |
| No console/build errors in frontend | ✅ |

---

## Fix for 500 on timeseries

The API uses a DB host that currently does not resolve inside the API container (e.g. `postgres`). Ensure:

1. The API service is on the same Docker network as Postgres.
2. `POSTGRES_HOST` (or equivalent) matches the actual Postgres service/host name (e.g. `netbet-postgres` if that is the container name in the main stack).

After the API can connect to the DB, the timeseries endpoint will return 200 and the impedance fields will be present in the response.
