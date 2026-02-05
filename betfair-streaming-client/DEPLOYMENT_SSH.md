# Final Production Deployment Execution (SSH)

Clean-slate deployment on the VPS so the new partitioned architecture (V3/V4) starts without legacy interference.

**VPS:** `158.220.83.195` (connect as **root**).

---

## Prerequisites on your PC

- SSH client (`ssh`, `scp`) – e.g. Git Bash, WSL, or PowerShell with OpenSSH.
- Access to the project: `C:\Users\WatMax\NetBet\betfair-streaming-client`.
- SSH key or password for `root@158.220.83.195`.

---

## 1. Upload the codebase to the VPS

From **PowerShell** or **Git Bash** on your Windows machine:

```powershell
# Ensure /opt/netbet exists on the VPS
ssh root@158.220.83.195 "mkdir -p /opt/netbet"

# Upload project contents into /opt/netbet (all files: migrations V1–V4, scripts, docker-compose, etc.)
scp -r "C:\Users\WatMax\NetBet\betfair-streaming-client\*" root@158.220.83.195:/opt/netbet/
```

Or with **rsync** (if available):

```bash
rsync -avz --exclude '.git' "C:/Users/WatMax/NetBet/betfair-streaming-client/" root@158.220.83.195:/opt/netbet/
```

**Checklist:** On the VPS, `/opt/netbet/` must contain at least:

- `docker-compose.yml`
- `Dockerfile`, `pom.xml`, `mvnw`, `.mvn/`
- `src/` (including `src/main/resources/db/migration/` with V1–V4)
- `scripts/` with `manage_partitions.sql`, `verify_partitions.sql`, `backup_db.sh`, `deploy_clean_slate.sh`
- `/opt/netbet/auth-service/.env` (create or copy separately if needed – required for Betfair keys and DB)

---

## 2. SSH in and run the deployment script

```bash
ssh root@158.220.83.195
```

On the VPS:

```bash
cd /opt/netbet
bash scripts/deploy_clean_slate.sh
```

The script will:

1. **Deep clean:** stop/remove all containers, `docker volume prune -f`, `docker system prune -a -f`
2. **Build & launch:** `docker compose up -d --build`
3. **DB init:** run `manage_partitions.sql` (today + tomorrow), then `verify_partitions.sql`
4. **Verification:** tail `netbet-streaming-client` logs for 20s, then `curl` telemetry on port **8081**

---

## 3. Manual steps (if you prefer not to use the script)

After SSH and upload:

```bash
cd /opt/netbet

# Step 1: Deep clean
docker stop $(docker ps -aq) 2>/dev/null || true
docker rm $(docker ps -aq) 2>/dev/null || true
docker volume prune -f
docker system prune -a -f

# Step 2 & 3: Build & launch
docker compose up -d --build
sleep 15

# Step 4: Partitions
docker exec -i netbet-postgres psql -U netbet -d netbet -f - < scripts/manage_partitions.sql
docker exec -i netbet-postgres psql -U netbet -d netbet -f - < scripts/verify_partitions.sql

# Step 5: Verify
timeout 20 docker logs -f netbet-streaming-client --tail 100
curl -s -u "admin:changeme" http://localhost:8081/metadata/telemetry
```

---

## 4. Confirm success

- **Logs:** No repeated connection or Postgres errors; Betfair streaming and batch inserts reported.
- **Telemetry:** `curl -u admin:changeme http://localhost:8081/metadata/telemetry` shows `postgres_sink_inserted_rows` (value will increase as data flows).
- **Partitions:** Output of `verify_partitions.sql` shows `ladder_levels_initial` and `ladder_levels_YYYYMMDD` with no range overlaps.

---

**Note:** Cursor cannot open an SSH session to your VPS (no stored credentials). Run the upload and `deploy_clean_slate.sh` (or the manual commands) from your machine after connecting as root.
