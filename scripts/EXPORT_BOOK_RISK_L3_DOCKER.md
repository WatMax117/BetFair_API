# Book Risk L3 Export — Docker Run (VPS)

Export runs inside a one-off `python:3.11-slim` container with `/opt/netbet` mounted. No system Python on host required.

## Run Export

```bash
ssh root@158.220.83.195
cd /opt/netbet

# Default: 2026-02-06..2026-02-08, env=vps
bash scripts/run_export_docker.sh

# With market filter
bash scripts/run_export_docker.sh --market-ids 1.253489253

# Custom date range
bash scripts/run_export_docker.sh --date-from 2026-02-14 --date-to 2026-02-16
```

## Output Location

`/opt/netbet/data_exports/book_risk_l3/`

## Validation

```bash
python scripts/validate_export_book_risk_l3.py book_risk_l3__vps<YYYY-MM-DD><HHMMSS>
```

(Inside same Docker setup or on host with Python.)

## Download to Local

```powershell
scp -i C:\Users\WatMax\.ssh\id_ed25519_contabo root@158.220.83.195:/opt/netbet/data_exports/book_risk_l3/book_risk_l3__vps* "c:\Users\WatMax\NetBet\data_exports\book_risk_l3\"
```
