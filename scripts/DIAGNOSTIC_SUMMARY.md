# Diagnostic Summary: Snapshot Ingestion & Impedance Rendering

## Issue 1: Snapshots Not Updating

### Symptoms
- UI loads correctly but data appears static
- No new snapshots being generated
- Data not refreshing with new backend entries

### Diagnostic Steps

#### On VPS (run diagnostic script):
```bash
bash scripts/diagnose_snapshot_ingestion.sh
```

This checks:
1. **rest-client container status** - Is `netbet-betfair-rest-client` running?
2. **rest-client logs** - Any errors in the last 50 lines?
3. **Healthcheck status** - Is the container healthy?
4. **Recent snapshots** - Count and age of latest snapshot in last 24h
5. **Snapshots per hour** - Hourly breakdown to see if ingestion stopped
6. **streaming-client status** - Is the Java streaming client also running?

#### Manual checks:
```bash
# Check container status
docker ps --filter "name=betfair-rest-client"

# Check logs
docker logs --tail 100 netbet-betfair-rest-client

# Check recent snapshots
docker exec netbet-postgres psql -U netbet -d netbet -c "
SELECT COUNT(*), MAX(snapshot_at), NOW() - MAX(snapshot_at) as age
FROM rest_ingest.market_book_snapshots
WHERE snapshot_at > NOW() - INTERVAL '24 hours';
"
```

### Common Causes & Fixes

**A) Container stopped/crashed**
- **Fix:** `docker compose -p netbet restart betfair-rest-client`
- Check logs for crash reason

**B) API authentication failure**
- **Symptom:** Logs show "401 Unauthorized" or token errors
- **Fix:** Check `auth-service` container and `.env` credentials

**C) Database connectivity issue**
- **Symptom:** Logs show connection errors
- **Fix:** Verify `netbet-postgres` is healthy and accessible

**D) No markets in time window**
- **Symptom:** Container running but no snapshots (no events in BF API window)
- **Fix:** Normal - check if events exist in Betfair for the configured window

---

## Issue 2: Impedance Not Rendering in Match View

### Symptoms
- Event detail page loads but impedance chart doesn't appear
- Third-level index visualization missing

### Diagnostic Steps

#### Frontend (Browser DevTools):

1. **Check "Include Impedance" checkbox**
   - Must be **checked** for impedance to be fetched
   - Located in event detail page controls

2. **Network tab**
   - Filter for `/api/events/{market_id}/timeseries`
   - Verify request includes `include_impedance=true`
   - Check response contains `impedanceNorm` objects

3. **Console tab**
   - Look for `[EventDetail]` logs:
     - `Loading timeseries` - confirms request with `includeImpedance` flag
     - `Timeseries loaded` - shows if `impedanceNorm` exists in response
     - `Render state` - shows `hasImpedance` value
   - Check for chart rendering errors (Recharts/LineChart)

#### Backend (VPS - run diagnostic script):
```bash
bash scripts/diagnose_impedance_rendering.sh
```

This checks:
1. **API endpoint** - Tests `/events/{market_id}/timeseries?include_impedance=true`
2. **Response shape** - Verifies `impedanceNorm` in response
3. **Database columns** - Checks if impedance columns exist
4. **Data existence** - Verifies impedance values in `market_derived_metrics`

### Common Causes & Fixes

**A) Checkbox not checked**
- **Symptom:** No impedance data in Network response
- **Fix:** Check "Include Impedance" checkbox in UI

**B) API not returning impedanceNorm**
- **Symptom:** Response has no `impedanceNorm` even with `include_impedance=true`
- **Possible causes:**
  - Database has no impedance data (rest-client not computing it)
  - Impedance columns missing from `market_derived_metrics`
- **Fix:**
  1. Verify rest-client is computing impedance (check logs)
  2. Run backfill if needed: `scripts/vps_backfill_impedance_and_validate.sh`
  3. Check if columns exist: `SELECT column_name FROM information_schema.columns WHERE table_name = 'market_derived_metrics' AND column_name LIKE '%impedance%';`

**C) Frontend receives data but doesn't render**
- **Symptom:** Network shows `impedanceNorm` but no chart
- **Possible causes:**
  - `hasImpedance` check failing (all values null)
  - Chart component error
- **Fix:**
  1. Check browser console for errors
  2. Verify `hasImpedance` logic (line 232 in EventDetail.tsx)
  3. Check if `chartData` includes `home_impedance_norm` etc.

---

## Quick Reference

### Container Names
- **rest-client:** `netbet-betfair-rest-client`
- **streaming-client:** `netbet-streaming-client`
- **API:** `risk-analytics-ui-api`
- **Web:** `risk-analytics-ui-web`
- **Postgres:** `netbet-postgres`

### Key Database Tables
- **Snapshots:** `rest_ingest.market_book_snapshots`
- **Derived metrics:** `public.market_derived_metrics`
- **Event metadata:** `public.market_event_metadata`

### Key API Endpoints
- **Timeseries:** `GET /api/events/{market_id}/timeseries?include_impedance=true`
- **Leagues:** `GET /api/leagues?from_ts=...&to_ts=...`

### Diagnostic Scripts
- **Snapshot ingestion:** `scripts/diagnose_snapshot_ingestion.sh`
- **Impedance rendering:** `scripts/diagnose_impedance_rendering.sh`
- **Impedance guide:** `scripts/diagnose_impedance_rendering.md`

---

## Next Steps

1. **Run both diagnostic scripts on VPS** and share outputs
2. **Check browser console** when viewing event detail page
3. **Verify "Include Impedance" checkbox** is checked
4. **Share Network tab** response for `/timeseries` endpoint

This will help identify whether the issues are:
- **Infrastructure** (containers not running)
- **Data** (no impedance computed/stored)
- **API** (endpoint not returning impedance)
- **Frontend** (rendering logic issue)
