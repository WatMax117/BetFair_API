# Deploy: Partition provisioner (stream_ingest.ladder_levels) - Variant A

The Risk Analytics API now runs an internal partition provisioner on startup and every 12h so that `stream_ingest.ladder_levels` always has partitions for the next 30 days. No separate cron or container is required.

**Variant A: Dedicated `netbet` user for partition provisioning**  
This implementation uses a dedicated DB user (`netbet`) for partition DDL, separate from the stream writer account.

## 1. Grant DB permissions to `netbet` (VPS)

Run as superuser or DB owner (e.g. `postgres` role):

```bash
# On VPS
docker exec -i netbet-postgres psql -U postgres -d netbet -v ON_ERROR_STOP=1 < /opt/netbet/scripts/grant_partition_permissions_netbet.sql
```

Or manually:

```sql
-- Grant CREATE on schema stream_ingest
GRANT CREATE ON SCHEMA stream_ingest TO netbet;

-- Grant ALTER on parent table (required to attach partitions)
GRANT ALTER ON TABLE stream_ingest.ladder_levels TO netbet;

-- If ladder_levels is owned by another role (e.g. netbet_stream_writer),
-- transfer ownership to netbet:
ALTER TABLE stream_ingest.ladder_levels OWNER TO netbet;
```

**Note:** If you prefer to keep `netbet_stream_writer` as the owner, you can skip the ownership transfer, but then `netbet` must be granted sufficient privileges. The cleanest approach is to use `netbet` as the partition manager (Variant A).

## 2. Set env vars in `/opt/netbet/.env` (VPS)

Add or update:

```bash
POSTGRES_PARTITION_USER=netbet
POSTGRES_PARTITION_PASSWORD=<netbet_password>
```

**Important:** The provisioner **requires** both `POSTGRES_PARTITION_USER` and `POSTGRES_PARTITION_PASSWORD` to be set. It will not fall back to stream writer credentials.

## 3. Docker Compose configuration

The root `docker-compose.yml` defaults to:

- `POSTGRES_PARTITION_USER` = `netbet` (if not set in `.env`)
- `POSTGRES_PARTITION_PASSWORD` = `${POSTGRES_PASSWORD}` (if not set in `.env`)

Ensure `/opt/netbet/.env` has `POSTGRES_PARTITION_PASSWORD` set explicitly (or `POSTGRES_PASSWORD` if using the default).

## 3. Deploy steps (on VPS)

From the repo root (e.g. `/opt/netbet`):

```bash
# Copy updated files (if not using git)
# Then rebuild and restart API
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
  Expect `ladder_levels_partition_horizon_days` gauge ≈ 30.

- **API logs (provisioner ran):**
  ```bash
  docker logs risk-analytics-ui-api --tail 50 2>&1 | grep -i partition
  ```
  Expect lines like:
  - `partition provisioner started`
  - `partition provisioning acquired lock`
  - `coverage horizon: YYYY-MM-DD`

- **Confirm partitions exist:**
  ```sql
  SELECT tablename
  FROM pg_tables
  WHERE schemaname = 'stream_ingest'
    AND tablename LIKE 'ladder_levels_%'
  ORDER BY tablename DESC
  LIMIT 10;
  ```
  Should show partitions through today + 30 days.

## 5. Troubleshooting

- **Authentication errors:** Ensure `POSTGRES_PARTITION_USER` and `POSTGRES_PARTITION_PASSWORD` are set correctly in `/opt/netbet/.env`.
- **Permission denied:** Run the grant script from step 1 to ensure `netbet` has `CREATE` on schema `stream_ingest` and `ALTER` on `stream_ingest.ladder_levels`.
- **"must be owner" error:** Transfer ownership: `ALTER TABLE stream_ingest.ladder_levels OWNER TO netbet;`
- **Table does not exist:** Ensure the streaming client (or migrations) have created the partitioned `stream_ingest.ladder_levels` on the VPS first.

## 6. Optional: one-off partition fix before deploy

If today’s partition is still missing and you want to fix it before deploying the API change, run on the VPS:

```bash
docker exec -i netbet-postgres psql -U netbet -d netbet -v ON_ERROR_STOP=1 < /opt/netbet/scripts/vps_add_stream_ingest_partitions.sql
```

After the API deploy, the provisioner will keep future partitions in place; no cron needed.

## Acceptance criteria

- ✅ No authentication errors in logs
- ✅ Horizon ≥ 30 days (`ladder_levels_partition_horizon_days` in `/health` and `/metrics`)
- ✅ No external cron/container required
- ✅ Inserts continue working across UTC midnight boundaries without manual intervention