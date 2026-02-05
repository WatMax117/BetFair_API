# Final Deployment: Clean Slate & Production Launch

This document describes the **one-time clean deploy** of the approved Production Ready architecture on the VPS. Use it when wiping legacy Docker resources and bringing up the new partitioned Postgres and streaming client from scratch.

**Prerequisites:** SSH access to the VPS; project (with V3/V4 migrations, scripts, and `docker-compose.yml`) available at e.g. `/opt/netbet/` or `/opt/netbet/betfair-streaming-client/`.  
**SSH upload and one-command deploy:** see [DEPLOYMENT_SSH.md](DEPLOYMENT_SSH.md) (VPS `158.220.83.195`, `deploy_clean_slate.sh`).

---

## Step 1: Deep Clean of the VPS

Run these commands **on the VPS** to ensure no old data or processes remain.

### 1.1 Stop and remove all containers

```bash
docker stop $(docker ps -aq) 2>/dev/null; docker rm $(docker ps -aq) 2>/dev/null
```

*(If no containers exist, the commands may report an error; that is safe to ignore.)*

### 1.2 Remove all unused volumes

**Critical:** Ensures the new partitioned Postgres starts with a clean state (no old `ladder_levels` or DB files).

```bash
docker volume prune -f
```

### 1.3 Full system prune

Removes unused images, build cache, and networks.

```bash
docker system prune -a -f
```

---

## Step 2: Sync & Build

### 2.1 Sync files

Ensure the latest project files are on the VPS at your project root (e.g. `/opt/netbet/`), including:

- `docker-compose.yml` (with services: postgres, streaming-client)
- `Dockerfile`, `pom.xml`, `mvnw`, `mvnw.cmd`, `.mvn/`
- `src/` (including `db/migration/`: V1, V2, V3, V4)
- `scripts/`: `manage_partitions.sql`, `verify_partitions.sql`, `backup_db.sh`, etc.
- Env file for the app (e.g. `/opt/netbet/auth-service/.env`) with Betfair and DB settings

### 2.2 Launch services

From the **project root** (where `docker-compose.yml` lives):

```bash
cd /opt/netbet   # or /opt/netbet/betfair-streaming-client
docker compose up -d --build
```

Wait until both containers are running (`docker ps` shows `netbet-postgres` and the streaming-client container).

---

## Step 3: Post-Deployment Initialization

**Mandatory** after first start: create daily partitions and verify.

### 3.1 Initialize partitions

Creates today’s and tomorrow’s `ladder_levels_YYYYMMDD` partitions (UTC). Run from the **host**, from the directory that contains `scripts/`:

```bash
cd /opt/netbet   # or your project root
docker exec -i netbet-postgres psql -U netbet -d netbet -f - < scripts/manage_partitions.sql
```

*If your compose mounts the project into the container at `/opt/netbet/`, you can instead run:*
```bash
docker exec netbet-postgres psql -U netbet -d netbet -f /opt/netbet/scripts/manage_partitions.sql
```

### 3.2 Verify partitions

Confirm partition layout (no overlaps; `ladder_levels_initial` + daily partitions):

```bash
docker exec -i netbet-postgres psql -U netbet -d netbet -f - < scripts/verify_partitions.sql
```

*(Or with mounted path: `docker exec netbet-postgres psql -U netbet -d netbet -f /opt/netbet/scripts/verify_partitions.sql`.)*

Inspect the output: you should see `ladder_levels_initial` and `ladder_levels_YYYYMMDD` with contiguous, non-overlapping ranges.

---

## Step 4: Health Check

### 4.1 Logs (Betfair and Postgres connection)

Tail the streaming-client logs for ~30 seconds and confirm successful connection to Betfair and Postgres (no repeated connection/DB errors):

```bash
docker logs -f netbet-streaming-client --tail 50
# Let run ~30 seconds, then Ctrl+C
```

*(Replace `netbet-streaming-client` with your actual streaming container name if different, e.g. `netbet_streaming-client_1`.)*

### 4.2 Telemetry endpoint

Verify `/metadata/telemetry` is reachable and reports sink metrics (e.g. `postgres_sink_inserted_rows`). Use the Basic Auth credentials configured for the app (e.g. from `BETFAIR_METADATA_ADMIN_USER` / `BETFAIR_METADATA_ADMIN_PASSWORD`):

```bash
curl -s -u "admin:changeme" http://localhost:8080/metadata/telemetry | jq .
```

*(Adjust host/port if the app is behind a reverse proxy or runs on another port.)*

Confirm that `postgres_sink_inserted_rows` (and other sink metrics) are present; after a short period of live data, the count should increase if data is flowing into the partitioned tables.

---

## Summary Checklist

| Step | Action | Done |
|------|--------|------|
| 1.1 | `docker stop/rm` all containers | ☐ |
| 1.2 | `docker volume prune -f` | ☐ |
| 1.3 | `docker system prune -a -f` | ☐ |
| 2.1 | Sync latest project (V3/V4, scripts, compose) to VPS | ☐ |
| 2.2 | `docker compose up -d --build` | ☐ |
| 3.1 | Run `manage_partitions.sql` (today + tomorrow) | ☐ |
| 3.2 | Run `verify_partitions.sql` and check output | ☐ |
| 4.1 | Tail streaming-client logs ~30s | ☐ |
| 4.2 | `curl` /metadata/telemetry and check `postgres_sink_inserted_rows` | ☐ |

After all steps, the server is on a clean slate with the Production Ready architecture and data flowing into the partitioned `ladder_levels` (and related) tables.
