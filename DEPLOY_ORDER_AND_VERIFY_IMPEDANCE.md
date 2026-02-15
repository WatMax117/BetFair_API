# Deploy Order and Rebuild Commands (Impedance)

Deploy and verify the impedance feature on the VPS: betfair-rest-client (DB migration + impedance writes) → risk-analytics-ui API → risk-analytics-ui web.

All commands below assume the VPS has the repo at **/opt/netbet** (as per comments in `docker-compose.yml`) and you use the **root compose file** there.

---

## 1. Deploy order and rebuild commands

### 1.1. SSH to VPS and pull latest

```bash
ssh <user>@<vps_ip>
cd /opt/netbet
git pull origin master
```

### 1.2. First: deploy betfair-rest-client (runs DB migration + writes impedance)

If you want a **partial deploy** just for the REST client:

```bash
cd /opt/netbet
# Stop only the rest client (optional)
docker compose stop betfair-rest-client
# Rebuild rest client image without cache
docker compose build --no-cache betfair-rest-client
# Start rest client (force recreate container)
docker compose up -d --force-recreate betfair-rest-client
```

Let it run at least one tick so `_ensure_three_layer_tables` runs and the new columns are added + impedance rows are written.

If you prefer a **full rebuild** here (also valid, just heavier):

```bash
cd /opt/netbet
docker compose down
docker compose build --no-cache
docker compose up -d
```

(That rebuilds and recreates all services including betfair-rest-client.)

### 1.3. Then: deploy risk-analytics-ui-api

If you didn’t do the full rebuild above, rebuild just the API:

```bash
cd /opt/netbet
docker compose stop risk-analytics-ui-api
docker compose build --no-cache risk-analytics-ui-api
docker compose up -d --force-recreate risk-analytics-ui-api
```

### 1.4. Finally: deploy risk-analytics-ui (web)

```bash
cd /opt/netbet
docker compose stop risk-analytics-ui-web
docker compose build --no-cache risk-analytics-ui-web
docker compose up -d --force-recreate risk-analytics-ui-web
```

**Single full redeploy** for steps 1.2–1.4:

```bash
cd /opt/netbet
docker compose down
docker compose build --no-cache
docker compose up -d
```

---

## 2. Verify API before UI

### 2.1. Check containers

```bash
docker ps
```

You should see at least:

- `netbet-postgres`
- `netbet-betfair-rest-client`
- `risk-analytics-ui-api`
- `risk-analytics-ui-web`

(auth-service, streaming-client, etc., depending on your stack)

### 2.2. Verify `/leagues/{league}/events` with impedance

From VPS:

```bash
# Example: find leagues first
curl "http://localhost:8000/leagues?from_ts=2025-01-01T00:00:00Z&to_ts=2030-01-01T00:00:00Z" | jq .

# Then pick a league name exactly as returned, e.g. "Premier League"
curl "http://localhost:8000/leagues/Premier%20League/events?include_impedance=true&from_ts=2025-01-01T00:00:00Z&to_ts=2030-01-01T00:00:00Z" | jq '.[0]'
```

In the single event object you should see:

- **Existing fields (unchanged):** `home_risk`, `away_risk`, `draw_risk`
- **New imbalance object:** `imbalance: { home, away, draw }`
- **New impedanceNorm object:** `impedanceNorm: { home, away, draw }`
- **Optional impedance (raw)** if present: `impedance: { home, away, draw }`

### 2.3. Verify `/events/{market_id}/timeseries` with impedance

```bash
curl "http://localhost:8000/events/<market_id>/timeseries?include_impedance=true&from_ts=2025-01-01T00:00:00Z&to_ts=2030-01-01T00:00:00Z" \
  | jq '.[0]'
```

Each time-series point should have:

- **Existing imbalance fields unchanged:** `home_risk`, `away_risk`, `draw_risk`
- **imbalance:** `imbalance: { home, away, draw }`
- **impedanceNorm** (when impedance is available): `impedanceNorm: { home, away, draw }`
- **Optional impedance:** `impedance: { home, away, draw }`

---

## 3. Logs / runtime checks

From `/opt/netbet`:

```bash
# Betfair REST client (should show [Impedance] logs)
docker logs netbet-betfair-rest-client --tail=100 | sed -n '1,100p'

# Risk Analytics API
docker logs risk-analytics-ui-api --tail=100 | sed -n '1,100p'

# Risk Analytics Web
docker logs risk-analytics-ui-web --tail=100 | sed -n '1,100p'
```

You should see:

- **betfair-rest-client:** lines like  
  `[Impedance] market=... selectionId=... impedance=... normImpedance=...`
- **risk-analytics-ui-api:** normal request logs, no 500s when hitting URLs with `include_impedance=true`
- **risk-analytics-ui-web:** no build errors (mostly nginx/httpd logs if using a static server image)

---

## 4. Verify UI (Imbalance + Impedance)

### 4.1. Ensure latest frontend is loaded

- Open the UI in the browser.
- **Hard refresh:** Windows: `Ctrl+F5` | Mac: `Cmd+Shift+R`
- Or use an Incognito/Private window.
- If behind Apache/nginx, ensure assets aren’t cached aggressively (e.g. disable long-lived cache for `/static` during testing).

### 4.2. Event detail view

Open an event (market) in the Risk Analytics UI. You should see:

**Header block:**

- **“Imbalance index (H / A / D)”** row exactly as before (H, A, D numeric values unchanged).
- A checkbox **“Include Impedance”**. When checked, the app refetches timeseries with `include_impedance=true`.
- When impedance is available and enabled:
  - A separate row: **“Impedance (norm) (H / A / D)”** with H/A/D values.
  - Tooltip: *“Higher positive = higher book loss if that outcome wins.”*
  - Optionally (when “Show raw impedance (debug)” is checked): row **“Impedance (raw) (H / A / D)”**.

**Charts:**

- Existing chart **“Liquidity Imbalance Index”** (H/A/D lines) unchanged.
- When “Include Impedance” is on and data exists: a second chart **“Impedance (norm) (H / A / D)”** with its own H/A/D lines and caption tooltip with the same “Higher positive…” text.

**Last 10 snapshots table:**

- Columns: **Imbalance H, Imbalance A, Imbalance D** (Imbalance index values).
- When Impedance is enabled and present: **impNorm H, impNorm A, impNorm D**.
- When “Show raw impedance (debug)” is on: **impRaw H, impRaw A, impRaw D**.
- Imbalance and Impedance appear as separate columns, side by side.

**Liquidity summary (debug) panel:**

- Row **“Imbalance index (H / A / D)”** — unchanged.
- When impedance is present: row **“Impedance (norm) (H / A / D)”** with tooltip *“Higher positive = higher book loss if that outcome wins.”*
- When raw impedance is present and “Show raw impedance (debug)” is on: row **“Impedance (raw) (H / A / D)”**.

### 4.3. If API returns impedance but UI shows nothing

1. Inspect the API response directly (as in section 2) to confirm `impedanceNorm` exists.
2. If the response is correct but the UI still lacks Impedance:
   - **Frontend is likely stale:**  
     Rebuild and redeploy:  
     `docker compose build --no-cache risk-analytics-ui-web && docker compose up -d --force-recreate risk-analytics-ui-web`
   - Hard refresh the browser or use Incognito.
   - Confirm the reverse proxy isn’t serving an old JS bundle from cache.

Once these checks pass:

- **Imbalance (H/A/D)** remains exactly as before.
- **Impedance (norm) (H/A/D)** appears only when enabled.
- Imbalance and Impedance are shown as distinct rows/blocks so the Risk team can compare them side by side.
