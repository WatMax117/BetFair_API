# Hard Reset & Production Launch (v1.2.1)

**Goal:** Clean the VPS, run a fresh Flyway migration, and verify the live liquidity flow using the v1.2.1 Fallback logic.

---

## Step 1: Deep Cleanup (The "Clean Slate")

Run the automated cleanup script on the VPS. It stops containers, prunes networks, and deletes the database volume so Flyway can run a clean V1–V5 migration.

```bash
cd /opt/netbet
bash scripts/hard_reset_deploy_v1.2.1.sh
```

---

## Step 2: Sync & Build Unified Stack

After cleanup, sync the latest code (PostgresStreamEventSink fallback logic, `netbet-auth-service` in `docker-compose.yml`, scripts) to `/opt/netbet/`, then launch:

```bash
# In Cursor's terminal (VPS context)
cd /opt/netbet && docker compose up -d --build
```

---

## Step 3: The 2-Minute "Health" Audit

Once containers are up, run these checks to confirm the ingestion engine is running:

**A. Ingestion Trace** — confirm the Fallback is firing:

```bash
docker logs -f netbet-streaming-client | grep -i "Liquidity trace"
```

Look for **`Final: [X]`** with **X > 0**.

**B. Database Pulse** — confirm tables are filling:

```bash
docker exec -i netbet-postgres psql -U netbet -d netbet -c "
SELECT 
    (SELECT count(*) FROM market_liquidity_history) AS history_rows,
    (SELECT count(*) FROM markets WHERE coalesce(total_matched, 0) > 0) AS markets_with_vol,
    (SELECT max(total_matched) FROM markets) AS max_vol;"
```

---

## Step 4: Golden Audit (The Analytical Payoff)

After 5–10 minutes of stable data flow, run the final report. It uses **today’s UTC partition** and shows liquidity by segment:

```bash
docker exec -i netbet-postgres psql -U netbet -d netbet -f /opt/netbet/scripts/golden_audit.sql
```

---

## Summary of the Resulting Environment

| Aspect | Result |
|--------|--------|
| **Unified network** | Auth service and streaming client share the same Docker network and talk via service names (e.g. `http://auth-service:8080/token`). |
| **Reliable liquidity** | The system no longer depends on Betfair’s market definition; volume is derived from runner-level data (Fallback) when needed. |
| **Clean partitioning** | Database is built from scratch with Flyway V1–V5; numeric precision is consistent and today’s partition is active. |

---

## Quick Reference

| Step | Action |
|------|--------|
| 1 | `cd /opt/netbet` → `bash scripts/hard_reset_deploy_v1.2.1.sh` |
| 2 | Sync code → `cd /opt/netbet && docker compose up -d --build` |
| 3 | After ~2 min: Trace (A) + Pulse (B) |
| 4 | After 5–10 min: Golden Audit |
