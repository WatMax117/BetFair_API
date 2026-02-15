# VPS Risk Analytics UI – “No data” diagnosis

## Summary

**Root cause:** The UI was sending a time window **from now to now+24h**. The API returns leagues whose events have `event_open_date` in that range. If all events in the DB have start times in the **past** (or outside that window), `/leagues` returns `[]` and the UI shows no data. This is a **default time-window** issue, not connectivity or CORS.

**Fix applied:** The default time window in the UI was changed to **now − 24h → now + 24h** (symmetric), so the first load includes recent and near-future events and leagues show up when data exists.

---

## Checklist results (VPS)

### 1. API process

- **Status:** Running (`risk-analytics-ui-api` container, Up 16 hours).
- **Port:** 8000 (host and container); `ss -tulpn` shows `0.0.0.0:8000` (docker-proxy).
- **Binding:** Container listens on all interfaces (API uses uvicorn default).
- **Local tests:**
  - `curl http://localhost:8000/health` → `200`, `{"status":"ok"}`.
  - `curl http://localhost:8000/leagues?limit=2` → `200`, body `[]` (empty) when no params.
  - `curl 'http://localhost:8000/leagues?from_ts=2025-01-01T00:00:00Z&to_ts=2030-01-01T00:00:00Z&limit=5'` → `200` with league list (e.g. Argentinian Primera Division, English Premier League, …).

### 2. Web → API base URL

- **Configured base URL:** `VITE_API_URL=/api` (set at build in Dockerfile).
- **Runtime behaviour:** Frontend calls relative `/api/...` (e.g. `/api/leagues`), so same-origin as the page.
- **Nginx (in web container):** `location /api/ { proxy_pass http://risk-analytics-ui-api:8000/; ... }` → correct.
- **Apache (host :80):** `ProxyPass /api/ http://127.0.0.1:8000/` → correct. `curl http://127.0.0.1/api/leagues?limit=2` → `200`, body `[]`.

### 3. Browser diagnostics (inferred)

- Requests **are** sent (API logs show `/leagues?from_ts=...&to_ts=...` with 200).
- No 404/502/CORS/network error observed; API returns 200 with an empty array for the default window.
- **Exact request:** `GET /leagues?from_ts=<now>&to_ts=<now+24h>&include_in_play=true&in_play_lookback_hours=6&limit=100&offset=0` → **200 OK**, body `[]`.

### 4. CORS

- API has `CORSMiddleware` with `allow_origins=["*"]` → no CORS issue for normal use.

### 5. Reverse proxy (Apache + nginx)

- **Apache (port 80):** risk-analytics.conf enabled; `/api/` → `http://127.0.0.1:8000/`, `/` → `http://127.0.0.1:3000/`. Verified with curl.
- **Nginx (in web container):** `/api/` → `http://risk-analytics-ui-api:8000/`. Container can reach API (`wget http://risk-analytics-ui-api:8000/health` → 200).
- No trailing-slash or rewrite issues identified.

### 6. Firewall / Docker

- API port 8000 and UI (3000, 80) are listening; containers on same Docker network; API reachable from web container by name.

### 7. Database

- **API:** No DB errors in logs; 200 responses.
- **DB content:** `market_event_metadata` has rows (e.g. 364). Leagues appear when a **wider** time range is used (e.g. 2025–2030).
- **Conclusion:** Empty response is due to **time filter** (default window has no events), not DB connectivity.

---

## Root cause (D – default time window)

- UI sent **from_ts = now**, **to_ts = now + 24h** (and with `include_in_play=true`, API effectively uses **from_effective = min(now, now − 6h) = now − 6h**).
- Query: `event_open_date >= from_effective AND event_open_date <= to_dt`.
- If all stored events have `event_open_date` in the past (or outside this window), the result set is empty → `/leagues` returns `[]` → UI shows “no data” even though the API and DB are fine.

---

## Fix applied (code)

- **File:** `risk-analytics-ui/web/src/components/LeaguesAccordion.tsx`
- **Change:** Default time window made symmetric: **from = now − windowHours**, **to = now + windowHours** (e.g. 24h → last 24h and next 24h).
- **Label:** “Time window (hours from now)” → “Time window (hours back and forward from now)”.

After redeploying the web app (rebuild + restart the web container), the first load should show leagues when there are events in the last 24h or next 24h.

---

## If “no data” persists after redeploy

1. **Confirm event dates in DB** (on VPS):
   ```bash
   docker exec netbet-postgres psql -U netbet -d netbet -c "SELECT MIN(event_open_date), MAX(event_open_date) FROM public.market_event_metadata WHERE event_open_date IS NOT NULL;"
   ```
2. **Temporarily widen the window** in the UI (e.g. 168 hours = 7 days) and click Search again.
3. **Check API logs** during a request:
   ```bash
   docker logs risk-analytics-ui-api --tail=20
   ```
4. **Optional:** Add a small “no leagues in this window” message in the UI when `leagues.length === 0` and the request succeeded, to distinguish “no data” from “request failed”.
