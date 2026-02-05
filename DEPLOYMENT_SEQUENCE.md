# Master Instruction: VPS Production Deployment & Data Collection

Deploy the full NetBet ecosystem to the VPS (158.220.83.195) and execute a 10-minute automated live data collection to CSV files for database schema analysis.

Execute these steps in order. All commands assume SSH key at `C:\Users\WatMax\.ssh\id_ed25519_contabo` and VPS `root@158.220.83.195`.

---

## 1. File Synchronization & Build Preparation

**Status:** Already configured.

- **auth-service/Dockerfile**: `python:3.11-slim`, `WORKDIR /app`
- **betfair-streaming-client/Dockerfile**: Two-stage (Maven 3.9 builds JAR, JRE 21 runs it)
- **docker-compose.yml**: Absolute paths for `/opt/netbet/auth-service/.env`, `/opt/netbet/auth-service/certs`, `BETFAIR_TOKEN_URL=http://auth-service:8080/token`
- **run_production_test.sh**: Finds live market via discovery script, starts Java with Market IDs, runs 600 seconds (10 min)

---

## 2. Local-to-VPS Upload (SCP)

Ensure `/opt/netbet` exists on VPS, then upload entire NetBet folder:

```powershell
ssh -i "C:\Users\WatMax\.ssh\id_ed25519_contabo" root@158.220.83.195 "mkdir -p /opt/netbet"
```

```powershell
scp -i "C:\Users\WatMax\.ssh\id_ed25519_contabo" -r "C:\Users\WatMax\NetBet\*" root@158.220.83.195:/opt/netbet/
```

**Important:** Ensure `auth-service/.env` and `auth-service/certs/client-2048.p12` exist locally before upload. The recursive copy includes subdirectories; if `.env` is excluded by `.gitignore`, copy it explicitly:

```powershell
scp -i "C:\Users\WatMax\.ssh\id_ed25519_contabo" "C:\Users\WatMax\NetBet\auth-service\.env" root@158.220.83.195:/opt/netbet/auth-service/
```

---

## 3. VPS Environment Sanitization (SSH)

```powershell
ssh -i "C:\Users\WatMax\.ssh\id_ed25519_contabo" root@158.220.83.195 "cd /opt/netbet && docker compose down -v && mkdir -p logs && chmod 777 logs"
```

---

## 4. Build and Orchestration (SSH)

```powershell
ssh -i "C:\Users\WatMax\.ssh\id_ed25519_contabo" root@158.220.83.195 "cd /opt/netbet && docker compose build --no-cache && docker compose up -d"
```

---

## 5. Health Check & Logging (SSH)

**Check both containers are running:**
```powershell
ssh -i "C:\Users\WatMax\.ssh\id_ed25519_contabo" root@158.220.83.195 "docker ps"
```

**Verify Auth Service (success = "Application started on port 8080"):**
```powershell
ssh -i "C:\Users\WatMax\.ssh\id_ed25519_contabo" root@158.220.83.195 "docker logs -f netbet-auth-service"
```

Press `Ctrl+C` to stop streaming logs.

---

## 6. Automated 10-Minute Data Collection (SSH)

```powershell
ssh -i "C:\Users\WatMax\.ssh\id_ed25519_contabo" root@158.220.83.195 "cd /opt/netbet && chmod +x scripts/run_production_test.sh && ./scripts/run_production_test.sh"
```

**Monitor CSV files in real-time** (in a separate SSH session):
```powershell
ssh -i "C:\Users\WatMax\.ssh\id_ed25519_contabo" root@158.220.83.195 "watch -n 2 'ls -la /opt/netbet/logs/ && wc -l /opt/netbet/logs/*.csv 2>/dev/null'"
```

Or tail a specific file:
```powershell
ssh -i "C:\Users\WatMax\.ssh\id_ed25519_contabo" root@158.220.83.195 "tail -f /opt/netbet/logs/prices_log.csv"
```

---

## Quick Reference (Copy-Paste Block)

```powershell
# 1. Create remote dir
ssh -i "C:\Users\WatMax\.ssh\id_ed25519_contabo" root@158.220.83.195 "mkdir -p /opt/netbet"

# 2. Upload
scp -i "C:\Users\WatMax\.ssh\id_ed25519_contabo" -r "C:\Users\WatMax\NetBet\*" root@158.220.83.195:/opt/netbet/
scp -i "C:\Users\WatMax\.ssh\id_ed25519_contabo" "C:\Users\WatMax\NetBet\auth-service\.env" root@158.220.83.195:/opt/netbet/auth-service/

# 3. Sanitize
ssh -i "C:\Users\WatMax\.ssh\id_ed25519_contabo" root@158.220.83.195 "cd /opt/netbet && docker compose down -v && mkdir -p logs && chmod 777 logs"

# 4. Build & start
ssh -i "C:\Users\WatMax\.ssh\id_ed25519_contabo" root@158.220.83.195 "cd /opt/netbet && docker compose build --no-cache && docker compose up -d"

# 5. Verify
ssh -i "C:\Users\WatMax\.ssh\id_ed25519_contabo" root@158.220.83.195 "docker ps"
ssh -i "C:\Users\WatMax\.ssh\id_ed25519_contabo" root@158.220.83.195 "docker logs -f netbet-auth-service"

# 6. Run 10-min data collection
ssh -i "C:\Users\WatMax\.ssh\id_ed25519_contabo" root@158.220.83.195 "cd /opt/netbet && ./scripts/run_production_test.sh"
```
