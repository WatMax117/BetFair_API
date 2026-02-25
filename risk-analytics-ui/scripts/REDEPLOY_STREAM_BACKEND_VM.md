# Backend redeploy for STALE_MINUTES = 120 (VM via SSH)

Run these steps **on the project VM** after SSH’ing in. Adjust `risk-analytics-ui` path if your repo lives elsewhere.

---

## 1. SSH and confirm project directory

```bash
# SSH into your VM (use your actual host/key)
# ssh user@<vm-ip>

cd /path/to/NetBet/risk-analytics-ui
# or: cd ~/NetBet/risk-analytics-ui
pwd
```

Confirm you are in the **risk-analytics-ui** project directory (the one that contains `api/`, `web/`, `docker-compose.yml`).

---

## 2. Pull latest code

```bash
git fetch origin
git pull origin master
# Or your branch: git pull origin <your-branch>
```

Confirm `STALE_MINUTES = 120` is present:

```bash
grep -n "STALE_MINUTES" api/app/stream_data.py
```

You should see a line like: `15:STALE_MINUTES = 120`.

---

## 3. Rebuild and restart backend (Docker Compose)

From the **risk-analytics-ui** directory (where `docker-compose.yml` lives):

```bash
# Rebuild the API image so new code is included
docker compose build risk-analytics-ui-api

# Restart the API container (new image)
docker compose up -d risk-analytics-ui-api
```

If the stack is run from the **repo root** with a compose override:

```bash
cd /path/to/NetBet
docker compose -f docker-compose.yml -f risk-analytics-ui/docker-compose.yml build risk-analytics-ui-api
docker compose -f docker-compose.yml -f risk-analytics-ui/docker-compose.yml up -d risk-analytics-ui-api
```

Check that the container is running and has no restart loop:

```bash
docker ps --filter name=risk-analytics-ui-api
docker logs risk-analytics-ui-api --tail 50
```

---

## 3 (alternative). Restart without Docker (gunicorn/uvicorn/systemd)

If the API runs as a process (e.g. systemd or a process manager):

```bash
# Example systemd
sudo systemctl restart risk-analytics-api

# Or if you run uvicorn/gunicorn manually, stop the process and start again
# after pulling and (if needed) installing deps:
# cd api && pip install -r requirements.txt && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Check logs for your service (e.g. `journalctl -u risk-analytics-api -f` or the log file you use).

---

## 4. Validate deployment

1. **Browser**
   - Open `https://<your-host>/stream` (or `http://<your-host>:3000/stream` if using web on 3000).
2. **DevTools → Network**
   - Reload or change date; find:
     - `GET .../api/stream/events/by-date-snapshots?date=YYYY-MM-DD`
   - Confirm:
     - Status **200**.
     - Response body is not `[]` (if you have streaming data for that date).
3. **Event detail**
   - Click an event; confirm event detail loads and **charts/timeseries** render.

---

## 5. Confirm in logs

```bash
docker logs risk-analytics-ui-api --tail 100
# Or for systemd: journalctl -u risk-analytics-api -n 100
```

Verify:

- Backend started successfully (no traceback on startup).
- No errors mentioning `stream_router` or `stream_data`.
- No database connection errors.

---

## Checklist to report back

- [ ] Backend redeploy completed (pull + rebuild + restart).
- [ ] `/stream` UI: events visible? **Yes / No**
- [ ] Event detail: charts/timeseries render? **Yes / No**
- [ ] Any errors in logs (paste or describe).

Once you’ve run through this on the VM, you can reply with the checklist and any log snippets to confirm the updated `STALE_MINUTES = 120` configuration is active and the /stream UI behaves as expected.
