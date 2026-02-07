# VPS: Fresh UI deploy (no version conflicts)

Run this **after** the repo has the API path fix committed and pushed to `master` (commit `ce2bed6` or later).

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
