# Final Production Smoke Test & Connectivity Audit

Run this after the **full stack** (auth-service + netbet-postgres + netbet-streaming-client) is up at `/opt/netbet/` to verify real-time data flow into partitioned tables.

---

## 1. Stack integration & networking

**Full stack:** From `/opt/netbet/` use the compose that includes all three services (see `docker-compose.full-stack.yml`). Start with:

```bash
cd /opt/netbet
docker compose up -d
```

**Network:** `netbet-streaming-client` must use the auth service via the **Docker service name**:

- `BETFAIR_TOKEN_URL=http://auth-service:8080/token` (not the public IP)

This is set in the full-stack compose so token requests stay on the Docker network and avoid loopback/firewall issues.

---

## 2. Auth-service blocker (cert permissions)

If auth-service is in a **restart loop**, check logs:

```bash
docker logs netbet-auth-service --tail 40
```

**Typical error:** `PermissionError: [Errno 13] Permission denied: '/certs/client-2048.p12'`

**Fix on the VPS:** Ensure the cert is readable by the user that runs the process inside the container (e.g. `appuser` or root). Example:

```bash
# On the VPS
sudo chmod 644 /opt/netbet/auth-service/certs/client-2048.p12
# If the container runs as a specific UID, ensure that user can read the file
sudo chown -R $(id -u):$(id -g) /opt/netbet/auth-service/certs
# Restart auth-service
docker restart netbet-auth-service
```

Then confirm it stays up: `docker ps` (no "Restarting" for netbet-auth-service).

---

## 3. Live stream & ingestion audit

**Monitor logs** for this sequence:

1. Successfully retrieved session token from auth-service.
2. Subscription successful (Betfair API connection).
3. Successful batch inserts into Postgres (no repeated write errors).

```bash
docker logs -f netbet-streaming-client --tail 100
```

**Telemetry (after 2–5 minutes uptime):**

```bash
curl -s -u admin:changeme http://localhost:8081/metadata/telemetry
```

**Success:** `postgres_sink_inserted_rows` &gt; 0 and increasing.

---

## 4. Database partition audit

**Row count in today’s partition (UTC date):**

```bash
docker exec netbet-postgres psql -U netbet -d netbet -t -c "SELECT count(*) FROM ladder_levels_20260205;"
```

(Replace `20260205` with current UTC date `YYYYMMDD` if different.)

**Success:** Count &gt; 0 and growing; no batch-insert errors in logs (V3 partition keys working under load).

**5 market types diversity** (ladder_levels has no market_type; join with `markets`):

```bash
docker exec netbet-postgres psql -U netbet -d netbet -c "SELECT m.market_type, count(*) FROM ladder_levels_20260205 l JOIN markets m ON l.market_id = m.market_id GROUP BY m.market_type ORDER BY m.market_type;"
```

(Replace `20260205` with current UTC date `YYYYMMDD` if different.) Expect all 5 types: MATCH_ODDS_FT, OVER_UNDER_25_FT, OVER_UNDER_05_HT, MATCH_ODDS_HT, NEXT_GOAL.

---

## 5. Final health summary checklist

| Check | Status | Notes |
|-------|--------|--------|
| auth-service connectivity | ☐ Pass / ☐ Fail | Container healthy; token URL `http://auth-service:8080/token` |
| Betfair stream stability | ☐ Pass / ☐ Fail | Logs show subscription and sustained connection |
| Non-zero telemetry metrics | ☐ Pass / ☐ Fail | `postgres_sink_inserted_rows` &gt; 0 |
| Correct partition routing | ☐ Pass / ☐ Fail | Rows in `ladder_levels_YYYYMMDD` for current UTC day |

Once auth-service is healthy and the checklist passes, the smoke test is complete and the system is verified for production data flow.
