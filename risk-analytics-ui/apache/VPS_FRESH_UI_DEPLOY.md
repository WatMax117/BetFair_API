# VPS: Fresh UI deploy (no version conflicts)

## Temporary (no Git)

Use this flow until production is validated; then you can keep using it for ad-hoc deploys or move to a Git-based flow.

**Script:** `scripts\deploy_risk_analytics_ui_web_to_vps.ps1`  
Same VPS/SSH as rest-client deploy: `root@158.220.83.195`, key `C:\Users\WatMax\.ssh\id_ed25519_contabo`. It uploads the whole `risk-analytics-ui\web` folder to the VPS at `/opt/netbet/risk-analytics-ui/` (service at `/opt/netbet/risk-analytics-ui/web/`), then on the VPS runs:

- `cd /opt/netbet`
- `docker compose build --no-cache risk-analytics-ui-web`
- `docker compose up -d --no-deps risk-analytics-ui-web`

No Git, Apache, or backend steps—only the web service is updated.

**How to run** (from repo root):

```powershell
.\scripts\deploy_risk_analytics_ui_web_to_vps.ps1
```

Or:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy_risk_analytics_ui_web_to_vps.ps1
```

**After it finishes:** Open http://158.220.83.195/ and do a hard refresh (**Ctrl+Shift+R**). Confirm requests go to `/api/leagues` (single `/api`), return 200, and there are no 404s. Once that’s confirmed, you can keep using this script for ad-hoc deploys or introduce a Git-based deployment on the server.

---

## Git-based flow (after production is validated)

Run the steps below when you want to deploy from Git on the server.

## 1. Fresh pull

```bash
cd /opt/netbet
git fetch origin
git checkout master
git pull origin master
```

## 2. Confirm source has the fix (no `/api/api/`)

```bash
grep -n 'API_BASE.*leagues' risk-analytics-ui/web/src/api.ts
```

Expected: line with `${API_BASE}/leagues` (no `/api/` between `API_BASE` and `leagues`).

## 3. Remove old web image and rebuild

```bash
docker compose down risk-analytics-ui-web --remove-orphans 2>/dev/null || true
docker rmi netbet-risk-analytics-ui-web:latest 2>/dev/null || true
docker compose build --no-cache risk-analytics-ui-web
docker compose up -d --force-recreate --no-deps risk-analytics-ui-web
```

## 4. Verification in the browser

1. Open http://158.220.83.195/
2. Hard refresh: **Ctrl+Shift+R** (or DevTools → Network → "Disable cache" → refresh).
3. In **View Page Source** or **Network** tab, check the main JS file:
   - **Old (broken):** `index-Bj5rbbWR.js`
   - **New (fixed):** different hash, e.g. `index-<newhash>.js`
4. In **Network**, confirm requests go to `/api/leagues` (single `/api`), not `/api/api/leagues`, and return 200.
