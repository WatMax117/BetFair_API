# NetBet VPS Deployment & 10-Minute Data Collection

## Prerequisites

- SSH key: `C:\Users\WatMax\.ssh\id_ed25519_contabo`
- VPS: `158.220.83.195`
- auth-service `.env` and `certs/` configured on VPS

## 1. Upload Entire Project (Single Command)

From PowerShell:

```powershell
scp -i "C:\Users\WatMax\.ssh\id_ed25519_contabo" -r "C:\Users\WatMax\NetBet\*" root@158.220.83.195:/opt/netbet/
```

Or use the deploy script:
```powershell
cd C:\Users\WatMax\NetBet
.\scripts\deploy_full.ps1
```

**Note:** Ensure `.env` and `certs/` are present in auth-service before upload.

## 2. Rebuild & Launch

```powershell
ssh -i "C:\Users\WatMax\.ssh\id_ed25519_contabo" root@158.220.83.195 "cd /opt/netbet && mkdir -p logs && docker compose build && docker compose up -d"
```

## 3. Stream Java Service Logs (Verification)

```powershell
ssh -i "C:\Users\WatMax\.ssh\id_ed25519_contabo" root@158.220.83.195 "cd /opt/netbet && docker compose logs -f streaming-client"
```

Look for: **"Stream subscribed successfully"** and **"Stream connected"**.

## 4. Run 10-Minute Data Collection

```powershell
ssh -i "C:\Users\WatMax\.ssh\id_ed25519_contabo" root@158.220.83.195 "cd /opt/netbet && chmod +x scripts/run_production_test.sh && ./scripts/run_production_test.sh"
```

This script:
1. Ensures auth-service is running
2. Discovers highest-volume in-play football market (Python)
3. Runs streaming-client with datalogging profile for 10 minutes
4. Writes CSV files to `/opt/netbet/logs/`

## 5. CSV Output

After the 10-minute run, CSVs are in `/opt/netbet/logs/`:
- `prices_log.csv` – Full depth price ladder
- `volume_log.csv` – Traded volume per price
- `liquidity_events.csv` – Order size changes > 30%
