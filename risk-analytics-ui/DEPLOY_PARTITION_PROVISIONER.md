# Deploy: Partition provisioner (stream_ingest.ladder_levels)

The Risk Analytics API now runs an internal partition provisioner on startup and every 12h so that `stream_ingest.ladder_levels` always has partitions for the next 30 days. No separate cron or container is required.

## 1. Prerequisites on VPS

Partition creation in Postgres requires the **table owner**. On the VPS, `stream_ingest.ladder_levels` is usually owned by `netbet_stream_writer` (streaming client) or `netbet`. The API runs as `netbet_analytics_reader` (read-only), so you must provide a second set of credentials for DDL.

**Option A – Use stream writer (recommended)**  
Use the same user that owns the table so the API can create partitions:

- `POSTGRES_PARTITION_USER=netbet_stream_writer`
- `POSTGRES_PARTITION_PASSWORD=<same as POSTGRES_STREAM_WRITER_PASSWORD>`

**Option B – Use superuser/owner**  
If the table is owned by `netbet`, set `POSTGRES_PARTITION_USER=netbet` and the corresponding password.

## 2. Env vars (already in root docker-compose.yml)

The root `docker-compose.yml` already sets:

- `POSTGRES_PARTITION_USER` (default `netbet_stream_writer`)
- `POSTGRES_PARTITION_PASSWORD` = `POSTGRES_STREAM_WRITER_PASSWORD`

So if your `.env` already has `POSTGRES_STREAM_WRITER_PASSWORD` for the streaming client, no extra env is needed. The API will use it only for the partition provisioner (DDL). To use a different role, set `POSTGRES_PARTITION_USER` and `POSTGRES_PARTITION_PASSWORD` in `.env`.

## 3. Deploy steps (on VPS)

From the repo root (e.g. `/opt/netbet`):

```bash
git pull
docker compose build risk-analytics-ui-api
docker compose up -d --no-deps risk-analytics-ui-api
```

## 4. Verify

- **Health (includes partition horizon):**
  ```bash
  curl -sS http://127.0.0.1:8000/health
  ```
  Expect `ladder_levels_partition_horizon_days` (e.g. 30) and `"status":"ok"`.

- **Metrics:**
  ```bash
  curl -sS http://127.0.0.1:8000/metrics
  ```
  Expect `ladder_levels_partition_horizon_days` gauge.

- **API logs (provisioner ran):**
  ```bash
  docker logs risk-analytics-ui-api --tail 50 2>&1 | grep -i partition
  ```
  Expect lines like: `partition provisioner started`, `partition provisioning acquired lock`, `coverage horizon: ...`.

## 5. If horizon is missing or errors in logs

- **Permission denied / must be owner:** Set `POSTGRES_PARTITION_USER` / `POSTGRES_PARTITION_PASSWORD` to the role that owns `stream_ingest.ladder_levels` (see step 1).
- **Table does not exist:** Ensure the streaming client (or migrations) have created the partitioned `stream_ingest.ladder_levels` on the VPS first.

## 6. Optional: one-off partition fix before deploy

If today’s partition is still missing and you want to fix it before deploying the API change, run on the VPS:

```bash
docker exec -i netbet-postgres psql -U netbet -d netbet -v ON_ERROR_STOP=1 < /opt/netbet/scripts/vps_add_stream_ingest_partitions.sql
```

(Or use the stream writer user if `netbet` does not own the table.)

After the API deploy, the provisioner will keep future partitions in place; no cron needed.
