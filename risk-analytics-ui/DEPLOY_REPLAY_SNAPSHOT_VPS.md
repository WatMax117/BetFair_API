# Deploy Replay Snapshot Release to VPS 158.220.83.195

Target: **158.220.83.195** · DB container: **netbet-postgres** · No partial deploys.

---

## Pre-Deployment Checklist (MANDATORY — run on local machine)

### 1. Commit and push replay snapshot changes

Current replay snapshot work may be **uncommitted**. Ensure everything is committed and pushed so the VPS can `git pull` it.

```powershell
cd c:\Users\WatMax\NetBet
git status -sb
git log -1 --oneline
```

**Required in the commit you will deploy:**

- `risk-analytics-ui/api/app/stream_router.py` — replay_snapshot endpoint + meta (`has_full_raw_payload`, `supports_replay_snapshot`, `last_tick_time`)
- `risk-analytics-ui/web/src/api.ts` — `fetchReplaySnapshot`, `ReplaySnapshot` type, meta fields
- `risk-analytics-ui/web/src/components/EventDetail.tsx` — “View reconstructed snapshot” + replay flow
- `risk-analytics-ui/scripts/add_replay_snapshot_index.sql` — index script

If any of these are modified or untracked, **commit and push** before deploying:

```powershell
git add risk-analytics-ui/api/app/stream_router.py risk-analytics-ui/web/src/api.ts risk-analytics-ui/web/src/components/EventDetail.tsx risk-analytics-ui/scripts/add_replay_snapshot_index.sql
git commit -m "Replay snapshot: endpoint, meta, frontend, index script"
git push origin master
```

### 2. Confirm index script exists

```powershell
Get-Content risk-analytics-ui\scripts\add_replay_snapshot_index.sql
```

Should show `CREATE INDEX IF NOT EXISTS idx_stream_ladder_market_publish ...`

### 3. No local-only changes

Ensure no uncommitted local overrides that would be lost on VPS after `git pull`.

---

## Step 1 — SSH to VPS and pull

From local machine:

```bash
ssh <user>@158.220.83.195
```

On VPS (adjust project path to your actual path, e.g. `/opt/netbet` or `~/NetBet`):

```bash
cd /path/to/project
git pull
```

---

## Step 2 — Create replay index (SAFE + IDEMPOTENT)

SQL file is on the **host**; pass it into the container via stdin (path in `-f` is inside container, so use stdin):

```bash
docker exec -i netbet-postgres psql -U netbet -d netbet -f - < risk-analytics-ui/scripts/add_replay_snapshot_index.sql
```

Confirm index exists:

```bash
docker exec -i netbet-postgres psql -U netbet -d netbet -c "SELECT indexname FROM pg_indexes WHERE schemaname = 'stream_ingest' AND tablename = 'ladder_levels';"
```

Ensure **`idx_stream_ladder_market_publish`** is in the list.

---

## Step 3 — Build Docker images

From **project root** on VPS. If you use the main stack plus risk-analytics-ui override:

```bash
docker compose -f docker-compose.yml -f risk-analytics-ui/docker-compose.yml build --no-cache
```

If your setup composes only risk-analytics-ui services, adjust to your compose file(s). Resolve any build errors before continuing.

---

## Step 4 — Restart services

```bash
docker compose -f docker-compose.yml -f risk-analytics-ui/docker-compose.yml down
docker compose -f docker-compose.yml -f risk-analytics-ui/docker-compose.yml up -d
```

Confirm containers:

```bash
docker ps
```

Verify **risk-analytics-ui-api** and **risk-analytics-ui-web** (or your frontend container name) are running and not restarting.

---

## Step 5 — Production validation (MANDATORY)

Replace `<prod-host>` with your actual host (e.g. `158.220.83.195` or your domain). If the API is behind a reverse proxy, use the public URL.

### 1. Meta endpoint

```bash
curl -s https://<prod-host>/api/stream/events/1.253378204/meta | jq .
```

Must contain: **`has_full_raw_payload`**, **`supports_replay_snapshot`**, **`last_tick_time`**.

### 2. Replay endpoint

```bash
curl -s https://<prod-host>/api/stream/events/1.253378204/replay_snapshot | jq .
```

Must return:

- HTTP **200**
- JSON with **`is_reconstructed: true`**
- **Non-empty `selections`** (or 404 with message if no tick data for that market)

### 3. UI validation

- Open an **archived** market (e.g. 1.253378204).
- Button must show: **“View reconstructed snapshot”**.
- Open it; modal shows reconstructed data and the note: *“Reconstructed from stored ladder ticks. Full raw payload is not retained.”*
- In browser DevTools → Network: **no** request to `/latest_raw` for that flow; request to **`/replay_snapshot`** instead.
- No **404** or **500** in Network tab.

---

## Acceptance criteria

Deployment is **successful** only if:

- Replay endpoint returns data for the archived market (or a clear 404 message when no ticks).
- No backend **500** errors in API logs.
- No frontend console errors.
- Index **idx_stream_ladder_market_publish** exists.
- Containers stable for at least 5–10 minutes.

---

## Rollback (if required)

On VPS:

```bash
cd /path/to/project
git checkout <previous_stable_commit>
docker compose -f docker-compose.yml -f risk-analytics-ui/docker-compose.yml build
docker compose -f docker-compose.yml -f risk-analytics-ui/docker-compose.yml down
docker compose -f docker-compose.yml -f risk-analytics-ui/docker-compose.yml up -d
```

Confirm system restored (e.g. curl meta and previous behaviour).

---

## Non-negotiable

Do **not** mark deployment complete without:

- **curl** validation of meta and replay endpoint.
- **UI** verification on an archived market (button + modal + no 404/500).
