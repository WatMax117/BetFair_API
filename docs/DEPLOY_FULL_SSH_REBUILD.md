# Full Deployment Procedure (SSH → Rebuild All Docker Services)

Deploy the latest NetBet project (frontend, backend, DB migrations, REST discovery, streaming client) from the local `NetBet` folder to the VPS and rebuild all Docker services.

## Summary of deployed behavior (bulk buckets)

- **Queries:** 3 DB queries total for buckets (metadata, ladder, liquidity). No per-bucket N+1.
- **total_volume:** Option A — one bulk query against `stream_ingest.market_liquidity_history`; per-bucket value = latest `total_matched` with `publish_time <= bucket_end`. Null when no liquidity rows → UI shows "—".
- **Side/level scope:** Impedance and Book Risk use only top-of-book back: `side = 'B'`, `level = 0`. See `docs/BULK_BUCKETS_EXPLAIN_ANALYZE.md` and `stream_data.get_event_buckets_stream_bulk()`.
- **Validation:** Logging includes `market_id`, `bucket_count`, `db_query_count`, `total_ms`, `payload_bytes`. Use 180‑min (default) or 24‑h (`from_ts`/`to_ts`) as in `docs/BULK_BUCKETS_EXPLAIN_ANALYZE.md` and `docs/INDEX_AND_BUCKETS_PERFORMANCE.md`.

---

## 0. Preconditions

- Local project path: `~/NetBet` (or `C:\Users\WatMax\NetBet` on Windows)
- VPS access via SSH
- Docker and `docker compose` installed on VPS
- `.env` (and `auth-service/.env`) already configured on VPS
- Git used for code sync

---

## 1. Push Local Changes

On local machine:

```bash
cd ~/NetBet   # or cd C:\Users\WatMax\NetBet on Windows
git add .
git status
git commit -m "Deploy: bulk buckets + NEXT_GOAL follow-up + REST alignment fixes"
git push origin main
```

Replace `main` if using a different branch.

---

## 2. Connect to VPS

```bash
ssh user@your-vps-ip
```

Example (adjust key and host):

```bash
ssh -i ~/.ssh/id_ed25519_contabo root@158.220.83.195
```

Navigate to project directory:

```bash
cd /opt/netbet
```

---

## 3. Pull Latest Code

```bash
git pull origin main
```

Confirm changes:

```bash
git log -1 --oneline
```

---

## 4. Database Migration

### 4.1 Flyway (streaming client)

Flyway runs on streaming-client container startup and applies migrations in `betfair-streaming-client/src/main/resources/db/migration/` (V6, V7, V8, V9, etc.). No manual step needed.

### 4.2 Manual index (bulk buckets)

If the bulk buckets index has not been applied yet:

```bash
docker exec -i netbet-postgres psql -U netbet -d netbet -f - < risk-analytics-ui/scripts/add_bulk_buckets_index.sql
```

Or:

```bash
cat risk-analytics-ui/scripts/add_bulk_buckets_index.sql | docker exec -i netbet-postgres psql -U netbet -d netbet
```

Apply this before or after rebuild; Postgres must be running.

---

## 5. Stop All Services

```bash
docker compose down
```

Use `docker-compose` if that is your command.

---

## 6. Rebuild All Images (No Cache)

```bash
docker compose build --no-cache
```

This rebuilds:

- `risk-analytics-ui-api`
- `risk-analytics-ui-web`
- `betfair-streaming-client`
- `betfair-rest-client`
- `auth-service`

---

## 7. Start All Services

```bash
docker compose up -d
```

---

## 8. Verify Containers

```bash
docker ps
```

Expected services (among others):

- `netbet-postgres`
- `netbet-auth-service`
- `netbet-streaming-client`
- `netbet-betfair-rest-client`
- `risk-analytics-ui-api`
- `risk-analytics-ui-web`

Check logs:

```bash
docker compose logs -f risk-analytics-ui-api
docker compose logs -f netbet-streaming-client
docker compose logs -f netbet-betfair-rest-client
```

Press `Ctrl+C` to stop following logs.

---

## 9. Smoke Tests

### A. DB tables and views

```bash
docker exec -it netbet-postgres psql -U netbet -d netbet -c "\dt public.rest_* public.next_goal*"
```

Confirm presence of:

- `rest_events`
- `rest_markets`
- `next_goal_followup` (V9 migration)

### B. API health

```bash
curl -s http://localhost:8000/health
```

Expected JSON with `"status":"ok"` or similar.

### C. Buckets endpoint (bulk mode)

```bash
curl -s "http://localhost:8000/stream/events/1.253378204/buckets" | head -c 500
```

Check API logs:

```bash
docker compose logs --tail 50 risk-analytics-ui-api
```

Verify:

- `db_query_count=3` (metadata, ladder, liquidity)
- `bucket_count` present
- `total_ms` and `payload_bytes` present

---

## 10. REST Discovery (Cron)

REST discovery (`discovery_hourly.py`) is usually scheduled via cron, not Docker. Ensure cron is configured, e.g.:

```bash
0 * * * * cd /opt/netbet/betfair-rest-client && . ../.env 2>/dev/null; python discovery_hourly.py >> /var/log/discovery_hourly.log 2>&1
```

---

## 11. Optional: Force Clean Rebuild

Only if you need a full reset (removes unused images/containers):

```bash
docker compose down -v
docker system prune -af
docker compose build --no-cache
docker compose up -d
```

Warning: `-v` removes named volumes; `prune -af` removes all unused images. Use with care.

---

## Expected Result

- Frontend loads at `http://<vps-ip>:3000` (or via reverse proxy)
- Events list aligned with REST discovery
- NEXT_GOAL appears after 117s follow-up
- Buckets load significantly faster (3 queries, no per-bucket N+1)
- `impedance_index_15m` computed and returned
- No HT markets
- `total_volume` populated from liquidity query

---

## Rollback

```bash
git checkout <previous-commit>
docker compose down
docker compose build --no-cache
docker compose up -d
```

---

## Zero-Downtime Deployment (Optional)

For rolling restarts instead of full stop:

1. Rebuild images
2. Restart services one at a time: `docker compose up -d --no-deps <service>`
3. Start with `risk-analytics-ui-web`, then `risk-analytics-ui-api`, then `netbet-streaming-client`, etc.
4. Keep `postgres` running throughout
