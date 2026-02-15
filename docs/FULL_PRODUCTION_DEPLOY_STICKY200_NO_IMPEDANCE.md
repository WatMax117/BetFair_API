# Full Production Deployment – Remove Imbalance/Impedance + Sticky200 (All Services)

Deploy the updated stack to the virtual server via SSH: REST client (no Imbalance/Impedance, Sticky K=200), backend API (no risk/impedance), frontend (no UI references), and DB migration to drop related columns.

---

## PHASE 1 – Pre-Deployment Checks (Local)

### 1.1 Commit and push

Ensure all changes are committed and pushed to the main branch:

```bash
git status
git add -A
git commit -m "Remove Imbalance/Impedance MVP; Sticky K=200; DB migration"
git push origin main
```

### 1.2 Build Docker images

From the **repository root** (e.g. `C:\Users\WatMax\NetBet` or `/path/to/NetBet`):

Set a version tag (use today’s date and short SHA):

```bash
export DATE_TAG=$(date +%Y%m%d)
export SHORT_SHA=$(git rev-parse --short HEAD)
export IMAGE_TAG=sticky200-${DATE_TAG}-${SHORT_SHA}
```

Optional: set a registry prefix (e.g. `ghcr.io/myorg` or `myregistry.net/netbet`). If you do not use a registry, skip `docker push` and use **on-server build** in Phase 4/5.

```bash
export REGISTRY=<your-registry>   # e.g. ghcr.io/myorg
```

Build all three images:

```bash
# Betfair REST client (no Imbalance/Impedance, Sticky K=200)
docker build -t "${REGISTRY:-local}/betfair-rest-client:${IMAGE_TAG}" ./betfair-rest-client

# Risk Analytics API (no risk/impedance in responses)
docker build -t "${REGISTRY:-local}/risk-api:${IMAGE_TAG}" ./risk-analytics-ui/api

# Risk Analytics Web (no imbalance/impedance in UI)
docker build -t "${REGISTRY:-local}/risk-web:${IMAGE_TAG}" ./risk-analytics-ui/web
```

Confirm builds succeed (no errors).

### 1.3 Push images (if using a registry)

Do not overwrite previous stable tags. Use the new tag from 1.2:

```bash
docker push "${REGISTRY}/betfair-rest-client:${IMAGE_TAG}"
docker push "${REGISTRY}/risk-api:${IMAGE_TAG}"
docker push "${REGISTRY}/risk-web:${IMAGE_TAG}"
```

If you **do not use a registry**, you will build images on the server in Phase 4/5 after `git pull`.

---

## PHASE 2 – SSH into Production Server

From your local machine:

```bash
ssh <user>@<server_ip>
```

Navigate to the deployment directory (typical path):

```bash
cd /opt/netbet
# or: cd /path/to/deployment
```

---

## PHASE 3 – Backup Current State

Before making any changes:

```bash
cp .env .env.backup.$(date +%F_%H%M)
cp docker-compose.yml docker-compose.yml.backup.$(date +%F_%H%M)
```

Optional:

```bash
docker ps > docker_running_backup.txt
```

---

## PHASE 4 – Update Configuration

### 4.1 Edit `.env`

Ensure these are set (Sticky K=200 and related):

```bash
# Sticky pre-match K=200
BF_STICKY_PREMATCH=1
BF_STICKY_K=200
BF_STICKY_CATALOGUE_MAX=400
BF_KICKOFF_BUFFER_SECONDS=60
BF_STICKY_NEAR_KICKOFF_HOURS=2
BF_STICKY_NEAR_KICKOFF_CONSECUTIVE_TICKS=1
BF_MARKET_BOOK_BATCH_SIZE=50
```

(Other vars, e.g. Postgres, auth, should already be present.)

### 4.2 Use new code (choose one approach)

**Option A – Pre-built images (registry)**

If you pushed images in Phase 1, set image tags. Either:

- Add to `.env`:
  - `BETFAIR_REST_CLIENT_IMAGE=<registry>/betfair-rest-client:sticky200-YYYYMMDD-<sha>`
  - `RISK_API_IMAGE=<registry>/risk-api:sticky200-YYYYMMDD-<sha>`
  - `RISK_WEB_IMAGE=<registry>/risk-web:sticky200-YYYYMMDD-<sha>`
- And in `docker-compose.yml` for each of the three services, set `image: ${BETFAIR_REST_CLIENT_IMAGE}` (and the other two) and comment out or remove the `build:` block for that service so `docker compose pull` and `up` use the image.

**Option B – Build on server (no registry)**

Pull latest code and build on the server (use `master` if that is your default branch):

```bash
git pull origin master
docker compose build betfair-rest-client risk-analytics-ui-api risk-analytics-ui-web
```

Alternatively, run the automated script from repo root: `bash scripts/run_production_deploy_sticky200_no_impedance.sh`

No image tag changes needed; compose will use the newly built images.

Save all config changes.

---

## PHASE 5 – Deploy API and Frontend First

Pull new images (if using registry):

```bash
docker compose pull
```

Restart only API and web (so they stop reading dropped columns before migration):

```bash
docker compose up -d risk-analytics-ui-api risk-analytics-ui-web
```

If you built on server (Option B), use:

```bash
docker compose up -d --build risk-analytics-ui-api risk-analytics-ui-web
```

Verify:

```bash
docker ps
docker logs -f --tail=100 risk-analytics-ui-api
docker logs -f --tail=100 risk-analytics-ui-web
```

Ensure:

- No missing-column errors in logs.
- No impedance/imbalance references in logs.
- API responds (e.g. `curl -s http://localhost:8000/leagues?from_ts=...&to_ts=...` returns JSON).

---

## PHASE 6 – Run Database Migration

The migration drops Imbalance/Impedance columns from `market_derived_metrics`. Run it **after** API/frontend are updated and **before** restarting the REST client.

### 6.1 Get the migration file on the server

If the repo is at `/opt/netbet` (or your deployment path):

```bash
cd /opt/netbet
# Migration path:
# risk-analytics-ui/sql/migrations/2026-02-15_drop_imbalance_impedance_columns.sql
```

If the repo is elsewhere, copy the migration file to the server and note its path.

### 6.2 Run the migration

Use a DB user that can alter `public.market_derived_metrics` (e.g. a superuser or the role that owns the table). Example:

```bash
psql -h localhost -p 5432 -U netbet -d netbet -f risk-analytics-ui/sql/migrations/2026-02-15_drop_imbalance_impedance_columns.sql
```

Or with `PGPASSWORD` and connection params from your `.env`:

```bash
export PGPASSWORD="${POSTGRES_PASSWORD}"
psql -h localhost -p 5432 -U "${POSTGRES_USER:-netbet}" -d "${POSTGRES_DB:-netbet}" -f risk-analytics-ui/sql/migrations/2026-02-15_drop_imbalance_impedance_columns.sql
```

Confirm no SQL errors in the output.

### 6.3 Verify schema

```bash
psql -h localhost -p 5432 -U netbet -d netbet -c "\d market_derived_metrics"
```

Confirm the following columns **no longer exist**:

- `home_risk`, `away_risk`, `draw_risk`
- `home_impedance`, `away_impedance`, `draw_impedance`
- `home_impedance_norm`, `away_impedance_norm`, `draw_impedance_norm`
- `home_back_stake`, `home_back_odds`, `home_lay_stake`, `home_lay_odds` (and away/draw equivalents)

Check API logs again; ensure no new SQL or missing-column errors.

---

## PHASE 7 – Deploy REST Client

Pull (if using registry) and restart the REST client:

```bash
docker compose pull
docker compose up -d betfair-rest-client
```

If building on server:

```bash
docker compose up -d --build betfair-rest-client
```

Verify logs:

```bash
docker logs -f --tail=200 netbet-betfair-rest-client
```

Confirm:

- `tracked_count` reaches 200 when there are enough pre-match markets.
- `requests_per_tick = 4` when at full capacity.
- No missing-column or schema errors.
- No `[Imbalance]` or `[Impedance]` log lines.

---

## PHASE 8 – System Validation

### 8.1 API smoke test

Call key endpoints (replace host/port if different):

```bash
curl -s "http://localhost:8000/leagues?from_ts=2026-02-15T00:00:00Z&to_ts=2026-02-16T00:00:00Z&limit=5" | head -c 500
curl -s "http://localhost:8000/events/book-risk-focus?limit=3" | head -c 500
# Replace <market_id> with a real ID from your data:
curl -s "http://localhost:8000/events/<market_id>/timeseries?interval_minutes=15" | head -c 500
```

Confirm:

- JSON responses are valid.
- No `impedance`, `imbalance`, `home_risk`, `away_risk`, `draw_risk` (or related) in the response bodies.

### 8.2 UI smoke test

- Open the UI in a browser (e.g. `http://<server>:3000`).
- Load the events list and open an event detail.
- Check the browser console: no errors about missing fields or impedance/imbalance.
- Confirm no UI labels or columns for Imbalance/Impedance.

### 8.3 Resource check

```bash
docker stats --no-stream
```

Ensure no abnormal CPU or memory usage.

---

## PHASE 9 – Rollback (If Needed)

If a critical issue occurs:

1. Restore backups:
   ```bash
   cp .env.backup.<timestamp> .env
   cp docker-compose.yml.backup.<timestamp> docker-compose.yml
   ```
2. If you had reverted to previous image tags in compose or `.env`, run:
   ```bash
   docker compose pull
   docker compose up -d
   ```
3. Re-check logs and API/UI behaviour.

**Note:** The DB migration **drops columns**. Rollback does **not** re-add them; restoring the previous app and REST client only avoids new writes/reads of those columns. To restore the old schema you would need a separate migration that re-adds the columns (and backfill if required). For this release, rollback is application-level only.

---

## Acceptance Criteria

Deployment is successful when:

- No calculation or exposure of Imbalance or Impedance exists anywhere in the stack.
- Database columns listed in Phase 6.3 are removed.
- UI does not reference the removed fields; no console errors.
- Sticky pre-match runs at K=200 (tracked_count reaches 200, requests_per_tick = 4 when full).
- No runtime or schema errors in API or REST client logs.
- System performance remains stable (docker stats acceptable).

When all checks pass, this release can be marked **production-complete**.

---

## Reference – Service and Container Names

| Service (compose)           | Container name              |
|----------------------------|-----------------------------|
| betfair-rest-client        | netbet-betfair-rest-client  |
| risk-analytics-ui-api      | risk-analytics-ui-api      |
| risk-analytics-ui-web      | risk-analytics-ui-web      |

Use these in `docker logs` and `docker ps` (e.g. `docker logs risk-analytics-ui-api` or `netbet-betfair-rest-client`).
