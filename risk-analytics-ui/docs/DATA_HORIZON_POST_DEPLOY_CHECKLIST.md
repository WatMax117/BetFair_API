# Data-horizon: post-deploy validation checklist

Use this checklist **after** redeploying the risk-analytics-ui API on the VPS so that the `/stream/data-horizon` endpoint is present.  
Full context: `DATA_HORIZON_VPS_VALIDATION.md` and `DATA_HORIZON_VPS_VALIDATION_RESULT.md`.

**VPS:** 158.220.83.195 · **Project path on VPS:** `/opt/netbet` (or your actual path).

---

## Pre-deploy (on VPS)

**Option A – run the script (recommended):**

```bash
cd /opt/netbet && bash scripts/deploy_data_horizon_vps.sh
```

**Option B – manual steps:**

- [ ] `cd /opt/netbet` (or project root)
- [ ] `git pull origin main` (or `git pull` / your branch)
- [ ] Confirm repo contains data-horizon: `grep -l "data-horizon" risk-analytics-ui/api/app/stream_router.py` → file path printed
- [ ] Rebuild API image: `docker compose build --no-cache risk-analytics-ui-api`
- [ ] Restart API only: `docker compose up -d risk-analytics-ui-api`

---

## 1. Direct API (port 8000)

Run on the VPS:

```bash
curl -sS -w "\nHTTP: %{http_code}\n" http://localhost:8000/stream/data-horizon | head -25
```

- [ ] **HTTP 200**
- [ ] Response is JSON (starts with `{`) with at least `oldest_tick`, `newest_tick`, and optionally `days` array

---

## 2. OpenAPI

```bash
curl -sS http://localhost:8000/openapi.json | grep -o '"/stream/data-horizon"'
```

- [ ] Output is `"/stream/data-horizon"` (endpoint listed in schema)

---

## 3. Via Apache (proxy)

```bash
curl -sS -w "\nHTTP: %{http_code}\n" http://127.0.0.1/api/stream/data-horizon | head -25
```

- [ ] **HTTP 200**
- [ ] Same JSON shape as in step 1 (proxy forwards `/api/stream/...` → backend `/stream/...`)

---

## 4. Handoff for UI validation

Once all server checks above pass:

- Notify the team so they can run **UI-level validation** (calendar behaviour and horizon constraints).
- UI checklist: see **§3** in `DATA_HORIZON_VPS_VALIDATION.md`:
  - Dates before `oldest_tick` cannot be selected; invalid selections clamp to nearest allowed day.
  - Dates in the horizon with no data (not in `days[]`) cannot be selected; selection clamps to nearest previous day with data.
  - Hint shows “Streaming data available from: YYYY-MM-DD (UTC)” from `oldest_tick`.
- In the browser: Stream UI → DevTools → Network → confirm the `data-horizon` request URL is `/api/stream/data-horizon` and returns 200 + JSON.

---

## Quick reference: one-liner (all curl checks)

```bash
echo "=== Direct ===" && curl -sS -w "\nHTTP: %{http_code}\n" http://localhost:8000/stream/data-horizon | head -15
echo "=== OpenAPI ===" && curl -sS http://localhost:8000/openapi.json | grep -o '"/stream/data-horizon"'
echo "=== Proxy ===" && curl -sS -w "\nHTTP: %{http_code}\n" http://127.0.0.1/api/stream/data-horizon | head -15
```

All three should show 200 and (for the two curl URLs) JSON; OpenAPI line should print `"/stream/data-horizon"`.

---

## Ready-to-play reply

Once all checks pass, reply: **"ready-to-play"** and optionally paste the curl outputs for confirmation. Example:

```
=== Direct ===
{"oldest_tick":"2025-...","newest_tick":"2026-...","days":[...]}
HTTP: 200
=== OpenAPI ===
"/stream/data-horizon"
=== Proxy ===
{"oldest_tick":"2025-...","newest_tick":"2026-...","days":[...]}
HTTP: 200
```
