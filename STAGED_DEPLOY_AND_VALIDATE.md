# Staged deployment with mandatory validation (Impedance)

**Deployment is VPS-only (Linux).** Do not rely on Docker Desktop on a Windows workstation. All commands and scripts below are intended to run on the VPS under `/opt/netbet`.

Execute each stage in order. **Do not proceed to the next stage until validation passes.**

---

## Runbook: Resolve Stage 1 blocker and complete deploy (Steps 0–5)

Execute the following **on the Linux VPS only**.

**Step 0 — Update code**

```bash
cd /opt/netbet
git pull
```

**Step 1 — Configure Postgres credentials**

```bash
cd /opt/netbet
cp .env.example .env
```

Edit `/opt/netbet/.env` and set real passwords to match the roles in Postgres:

- `POSTGRES_REST_WRITER_USER=netbet_rest_writer`  
  `POSTGRES_REST_WRITER_PASSWORD=<REST_WRITER_PASSWORD>`
- `POSTGRES_STREAM_WRITER_USER=netbet_stream_writer`  
  `POSTGRES_STREAM_WRITER_PASSWORD=<STREAM_WRITER_PASSWORD>`
- `POSTGRES_ANALYTICS_READER_USER=netbet_analytics_reader`  
  `POSTGRES_ANALYTICS_READER_PASSWORD=<ANALYTICS_READER_PASSWORD>`

These must match the passwords set with `ALTER ROLE … WITH PASSWORD '…';` in Postgres.

**Step 2 — Restart the REST client only**

```bash
cd /opt/netbet
docker compose up -d --force-recreate --no-deps betfair-rest-client
```

**Step 3 — Wait for data, then validate Stage 1**

Wait **15–20 minutes** for at least one snapshot cycle, then run validation only:

```bash
cd /opt/netbet
VALIDATE_ONLY=1 ./scripts/vps_stage1_deploy_and_validate.sh
```

Stage 1 passes only if: all 6 impedance columns exist in `market_derived_metrics`, at least one recent row has non-null impedance values, and REST client logs contain `[Impedance] …`. If Stage 1 fails, stop and fix before proceeding.

**Step 4 — Continue with Stage 2 (API)**

```bash
cd /opt/netbet
./scripts/vps_stage2_deploy_and_validate.sh
```

Validation must confirm: `imbalance` is always present, `impedanceNorm` appears when `include_impedance=true`, and no 5xx errors. Proceed only if Stage 2 passes.

**Step 5 — Continue with Stage 3 (Web/UI)**

```bash
cd /opt/netbet
./scripts/vps_stage3_deploy_and_validate.sh
```

Then validate from a client browser (hard refresh / incognito): Imbalance (H/A/D) unchanged; “Impedance (norm) (H/A/D)” visible as a separate block when enabled; separate charts and table columns for Imbalance vs Impedance.

**One-shot script (optional)**  
After creating and editing `.env`, you can run the full sequence (with a prompt to wait before Stage 1 validation):

```bash
cd /opt/netbet
chmod +x scripts/vps_complete_staged_deploy.sh
./scripts/vps_complete_staged_deploy.sh
```

**If anything fails** — paste: the failing script output; last 100 lines of REST client logs (`docker logs netbet-betfair-rest-client --tail=100 2>&1`); variable names only from `.env`:  
`grep -E '^[A-Z_]+' /opt/netbet/.env | sed 's/=.*/=***/'`

---

## Prerequisites on VPS

- Repository at `/opt/netbet` (e.g. `git clone` or sync from your machine).
- Docker and Docker Compose installed.
- For Stage 2 validation: `jq` installed (`apt install -y jq`).
- Postgres and dependent services defined in repo root `docker-compose.yml` (postgres, betfair-rest-client, risk-analytics-ui-api, risk-analytics-ui-web).

---

## Stage 1 blocker: Postgres credentials (fix first)

If Stage 1 validation fails because the REST client cannot write to Postgres (logs show **POSTGRES_PASSWORD not set; skipping 3-layer persistence**), define the required DB credentials on the VPS.

### 1. Define Postgres credentials on the VPS

Add the following to **`/opt/netbet/.env`** (or the env source used by `docker compose`). Use the same usernames as in the migration; set passwords to match the roles you created in Postgres (e.g. after running `db/migrations/001_db_isolation.sql` and setting passwords via `ALTER ROLE ... PASSWORD '...'`):

```bash
POSTGRES_REST_WRITER_USER=netbet_rest_writer
POSTGRES_REST_WRITER_PASSWORD=<REST_WRITER_PASSWORD>

POSTGRES_STREAM_WRITER_USER=netbet_stream_writer
POSTGRES_STREAM_WRITER_PASSWORD=<STREAM_WRITER_PASSWORD>

POSTGRES_ANALYTICS_READER_USER=netbet_analytics_reader
POSTGRES_ANALYTICS_READER_PASSWORD=<ANALYTICS_READER_PASSWORD>
```

A template listing only variable names (no secrets) is in the repo root: **`.env.example`**. Copy it to `/opt/netbet/.env` and fill in the passwords.

### 2. Restart the REST client only (no dependency restart)

```bash
cd /opt/netbet
docker compose up -d --force-recreate --no-deps betfair-rest-client
```

### 3. Wait for data, then re-run Stage 1 validation only

Wait **15–20 minutes** for at least one snapshot cycle, then run validation without re-deploying:

```bash
cd /opt/netbet
VALIDATE_ONLY=1 ./scripts/vps_stage1_deploy_and_validate.sh
```

Stage 1 must pass: 6 impedance columns in `market_derived_metrics`, at least one recent row with non-null impedance, and REST client logs showing `[Impedance]`.

### 4. Continue only after Stage 1 passes

Then run:

```bash
./scripts/vps_stage2_deploy_and_validate.sh
./scripts/vps_stage3_deploy_and_validate.sh
```

### If Stage 1 still fails after setting credentials

Paste for debugging:

- REST client logs (last 100 lines):  
  `docker logs netbet-betfair-rest-client --tail=100 2>&1`
- Contents of `.env` **without passwords** (variable names only):  
  `grep -E '^[A-Z_]+' /opt/netbet/.env | sed 's/=.*/=***/'`

---

## One-time setup (run once per VPS)

```bash
cd /opt/netbet
chmod +x scripts/vps_stage1_deploy_and_validate.sh \
        scripts/vps_stage2_deploy_and_validate.sh \
        scripts/vps_stage3_deploy_and_validate.sh \
        scripts/vps_run_all_stages.sh \
        scripts/vps_complete_staged_deploy.sh
apt install -y jq
```

---

## Quick reference – scripts

| Stage | Script | Notes |
|-------|--------|--------|
| 1 | `./scripts/vps_stage1_deploy_and_validate.sh` | After first run, if "recent rows with impedance" fails, wait 15–20 min then `VALIDATE_ONLY=1 ./scripts/vps_stage1_deploy_and_validate.sh` |
| 2 | `./scripts/vps_stage2_deploy_and_validate.sh` | Requires `jq` |
| 3 | `./scripts/vps_stage3_deploy_and_validate.sh` | Then confirm in browser from client (hard refresh/incognito) |
| All | `./scripts/vps_run_all_stages.sh` | Runs 1 → 2 → 3 with prompts; only continues if validation passes |

---

## Stage 1 – Deploy and validate betfair-rest-client (DB + data)

### Action (VPS)

```bash
cd /opt/netbet
git pull
docker compose build --no-cache betfair-rest-client
docker compose up -d --force-recreate betfair-rest-client
```

Or run the script (deploy + validation):

```bash
cd /opt/netbet && ./scripts/vps_stage1_deploy_and_validate.sh
```

Allow **at least one snapshot cycle** (default interval 900 s; 15–20 minutes). If validation fails only on “recent rows with non-null impedance”, wait and re-run validation without re-deploying:

```bash
VALIDATE_ONLY=1 ./scripts/vps_stage1_deploy_and_validate.sh
```

### Validation (must pass before continuing)

The script runs these checks. You can also run them manually:

1. **DB: `market_derived_metrics` has the six impedance columns**

   ```bash
   docker exec -i netbet-postgres psql -U netbet -d netbet -c "
   SELECT column_name
   FROM information_schema.columns
   WHERE table_schema = 'rest_ingest'
     AND table_name = 'market_derived_metrics'
     AND column_name IN (
       'home_impedance', 'away_impedance', 'draw_impedance',
       'home_impedance_norm', 'away_impedance_norm', 'draw_impedance_norm'
     )
   ORDER BY column_name;"
   ```
   **Expected:** 6 rows. If your tables use schema `public`, set `MDM_SCHEMA=public` or replace `rest_ingest` in the SQL.

2. **At least one recent row with non-null impedance**

   ```bash
   docker exec -i netbet-postgres psql -U netbet -d netbet -c "
   SELECT COUNT(*) AS recent_with_impedance
   FROM rest_ingest.market_derived_metrics
   WHERE snapshot_at >= NOW() - INTERVAL '7 days'
     AND (home_impedance_norm IS NOT NULL OR away_impedance_norm IS NOT NULL OR draw_impedance_norm IS NOT NULL);"
   ```
   **Expected:** At least 1 after one snapshot cycle. If 0, wait longer or widen the interval (e.g. 30 days).

3. **REST client logs contain `[Impedance]`**

   ```bash
   docker logs netbet-betfair-rest-client --tail=200 2>&1 | grep -E '\[Impedance\]'
   ```
   **Expected:** Lines like `[Impedance] market=... selectionId=... impedance=... normImpedance=...`. If no markets were processed in the last 200 lines, this may be empty after ensuring one snapshot has run.

**If any check fails → stop and fix before Stage 2.**

---

## Stage 2 – Deploy and validate risk-analytics-ui-api (API contract)

### Action (VPS)

```bash
cd /opt/netbet
git pull
docker compose build --no-cache risk-analytics-ui-api
docker compose up -d --force-recreate risk-analytics-ui-api
```

Or run the script (deploy + validation):

```bash
cd /opt/netbet && ./scripts/vps_stage2_deploy_and_validate.sh
```

### Validation (must pass before continuing)

The script uses `curl` and `jq` against `http://localhost:8000` (override with `API_BASE`). It checks:

- **imbalance** — always present in events and timeseries.
- **impedanceNorm** — present when `include_impedance=true` (may be null if no data yet).
- No **5xx** responses on `/leagues`, `/leagues/{league}/events?include_impedance=true`, and `/events/{market_id}/timeseries?include_impedance=true`.

Manual checks (optional):

```bash
curl -s "http://localhost:8000/leagues?from_ts=2025-01-01T00:00:00Z&to_ts=2030-01-01T00:00:00Z" | jq .
curl -s "http://localhost:8000/leagues/Premier%20League/events?include_impedance=true&from_ts=2025-01-01T00:00:00Z&to_ts=2030-01-01T00:00:00Z" | jq '.[0]'
# Then timeseries for a market_id from the response:
curl -s "http://localhost:8000/events/<market_id>/timeseries?include_impedance=true&from_ts=2025-01-01T00:00:00Z&to_ts=2030-01-01T00:00:00Z" | jq '.[0]'
```

**If validation fails → stop and fix before Stage 3.**

---

## Stage 3 – Deploy and validate risk-analytics-ui-web (frontend)

### Action (VPS)

```bash
cd /opt/netbet
git pull
docker compose build --no-cache risk-analytics-ui-web
docker compose up -d --force-recreate risk-analytics-ui-web
```

Or run the script (deploy + validation):

```bash
cd /opt/netbet && ./scripts/vps_stage3_deploy_and_validate.sh
```

### Validation

1. **On VPS:** Script confirms the UI bundle is served (HTTP 200 from `http://localhost:3000/`). Optionally add a build/version marker in `index.html` later for stricter checks.
2. **From client:** Open `http://<VPS_IP>/` (or via Apache on port 80). **Hard refresh (Ctrl+F5 / Cmd+Shift+R)** or use **Incognito** so the new build loads.
   - Imbalance (H/A/D) unchanged.
   - With “Include Impedance” enabled: “Impedance (norm) (H/A/D)” appears; tooltip “Higher positive = higher book loss if that outcome wins.”; separate chart and columns (e.g. impNorm H/A/D).

**If validation fails → stop and fix.**

---

## Completion criteria

- All three stages are deployed in order on the VPS.
- Validation passes at each stage before proceeding.
- Imbalance and Impedance are visible side by side in the UI and existing behaviour is unchanged.

---

## Environment variables (optional)

| Variable | Default | Used in |
|----------|---------|--------|
| `REPO_ROOT` | `/opt/netbet` | All scripts |
| `POSTGRES_CONTAINER` | `netbet-postgres` | Stage 1 |
| `REST_CLIENT_CONTAINER` | `netbet-betfair-rest-client` | Stage 1 |
| `MDM_SCHEMA` | `rest_ingest` | Stage 1 |
| `VALIDATE_ONLY` | `0` | Stage 1 (set `1` to skip deploy, run validation only) |
| `API_BASE` | `http://localhost:8000` | Stage 2 |
| `WEB_URL` | `http://localhost:3000` | Stage 3 |
