# VPS Cleanup & Robust Re-Deployment

## 1. Upload Entire NetBet Directory

From PowerShell (run from any directory):

```powershell
scp -i "C:\Users\WatMax\.ssh\id_ed25519_contabo" -r "C:\Users\WatMax\NetBet\*" root@158.220.83.195:/opt/netbet/
```

Ensure `/opt/netbet` exists on the VPS first:
```powershell
ssh -i "C:\Users\WatMax\.ssh\id_ed25519_contabo" root@158.220.83.195 "mkdir -p /opt/netbet"
```

## 2. Run Cleanup (Optional - for fresh start)

```powershell
ssh -i "C:\Users\WatMax\.ssh\id_ed25519_contabo" root@158.220.83.195 "cd /opt/netbet && docker compose down && docker rm -f \$(docker ps -aq) 2>/dev/null; docker volume prune -f && docker network prune -f && mkdir -p /opt/netbet/logs && chmod 777 /opt/netbet/logs"
```

## 3. Build and Launch

```powershell
ssh -i "C:\Users\WatMax\.ssh\id_ed25519_contabo" root@158.220.83.195 "cd /opt/netbet && docker compose down && docker compose build --no-cache && docker compose up -d"
```

## 4. Verification

**Check both containers are running:**
```powershell
ssh -i "C:\Users\WatMax\.ssh\id_ed25519_contabo" root@158.220.83.195 "docker ps"
```

**Stream auth-service logs:**
```powershell
ssh -i "C:\Users\WatMax\.ssh\id_ed25519_contabo" root@158.220.83.195 "cd /opt/netbet && docker compose logs -f auth-service"
```

**Stream all logs:**
```powershell
ssh -i "C:\Users\WatMax\.ssh\id_ed25519_contabo" root@158.220.83.195 "cd /opt/netbet && docker compose logs -f"
```
