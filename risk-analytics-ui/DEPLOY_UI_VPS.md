# UI Deployment Workflow via SSH (risk-analytics-ui-web)

Deployment procedure for rebuilding and redeploying the UI container on the VPS.

---

## 1. Copy Changes to VPS (if local changes exist)

If you have local changes in `risk-analytics-ui/web` on Windows:

**From:** `C:\Users\WatMax\NetBet`

```powershell
scp -r risk-analytics-ui\web root@<VPS_IP>:/opt/netbet/risk-analytics-ui/
```

Replace `<VPS_IP>` with the actual VPS IP (e.g. `158.220.83.195`) or hostname.

This overwrites/updates the UI source code on the server.

---

## 2. SSH and Deploy on VPS

Connect to the VPS:

```powershell
ssh root@<VPS_IP>
```

On the VPS, run:

```bash
cd /opt/netbet
docker compose build risk-analytics-ui-web --no-cache
docker compose up -d risk-analytics-ui-web --no-deps
```

**Notes:**
- `--no-cache` ensures a clean rebuild of the UI bundle.
- `--no-deps` avoids restarting unrelated services.

If your setup uses multiple compose files, specify them explicitly:

```bash
docker compose -f docker-compose.yml -f risk-analytics-ui/docker-compose.yml build risk-analytics-ui-web --no-cache
docker compose -f docker-compose.yml -f risk-analytics-ui/docker-compose.yml up -d risk-analytics-ui-web --no-deps
```

Adjust paths if the compose configuration differs on the VPS.

---

## 3. Hard Refresh in Browser

After deployment:

1. Open the UI in the browser.
2. Press **Ctrl+F5** to force reload the updated SPA bundles.
3. Optionally clear cache if needed.
