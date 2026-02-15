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

---

## Which build is actually served? (troubleshooting)

If the UI still shows old content (e.g. old time-window label) after a redeploy, use this to see which layer is serving the app.

### 1. Container port mapping

```bash
docker ps
```

Expect: `risk-analytics-ui-web` with **0.0.0.0:3000->80/tcp**.

### 2. What Apache does

```bash
sudo apachectl -S
```

Port 80 should be the **risk-analytics** vhost (from `/etc/apache2/sites-enabled/risk-analytics.conf`). That vhost **proxies** only (no DocumentRoot):

- `ProxyPass /api/` → `http://127.0.0.1:8000/`
- `ProxyPass /` → `http://127.0.0.1:3000/`

So Apache does **not** serve static files from `/var/www/html` for this site; it forwards to the Docker UI on port 3000.

### 3. JS bundle in the container

```bash
docker exec risk-analytics-ui-web ls -la /usr/share/nginx/html/assets/
docker exec risk-analytics-ui-web cat /usr/share/nginx/html/index.html
```

Note the script name in `index.html` (e.g. `/assets/index-cMmmbk3x.js`). That is the **current** build.

### 4. What the browser loads

- Open the site (http://&lt;VPS_IP&gt;/ or http://&lt;VPS_IP&gt;:3000).
- DevTools → **Network** → refresh → click the main JS file (e.g. `index-….js`).
- **Exact filename** should match the one in the container’s `index.html`.

If the filename matches but the UI is still old, the browser is using a **cached** copy of that JS. If the filename is different, the browser is using a cached **index.html** that points to an old bundle.

### 5. Direct test (bypass Apache)

Open:

- http://&lt;VPS_IP&gt;:3000

If **:3000** shows the new UI but **:80** does not, something is wrong with Apache (e.g. another vhost or cache). If both show the same (old) content, the container is serving the right files and the issue is **browser cache**.

### 6. Fix: force fresh content

- **Hard refresh:** **Ctrl+Shift+R** (or Cmd+Shift+R on Mac).
- Or: DevTools → Network → tick **“Disable cache”** → refresh.
- Or: clear site data / cache for this origin.

After that, reload and check the JS filename again; it should match the container and the UI should show the new label (e.g. “Time window (hours back and forward from now)”).

### Summary (verified on this VPS)

- **Container:** Serves `index.html` with `/assets/index-cMmmbk3x.js` (new build).
- **Apache:** Proxies `/` to `127.0.0.1:3000`; response from port 80 has `Server: nginx/1.29.5` (i.e. from the container).
- **Conclusion:** Port 80 and port 3000 both serve the **same** build from the container. If you still see the old menu, clear browser cache and hard refresh.
