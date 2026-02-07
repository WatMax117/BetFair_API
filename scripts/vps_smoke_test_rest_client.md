# VPS Smoke Test – betfair-rest-client

After tests pass locally, deploy and run one cycle to capture real Risk Index logs.

## 1. Deploy to VPS

From your machine (with Docker and access to VPS):

```bash
# From NetBet repo root
rsync -avz --exclude '.git' -e "ssh -i YOUR_KEY" . deploy@YOUR_VPS_IP:/opt/netbet/
# Or use your existing deploy script, e.g. scripts/deploy_full.ps1
```

On VPS:

```bash
cd /opt/netbet
docker compose build betfair-rest-client
docker compose up -d betfair-rest-client
```

## 2. Wait one cycle (15 min)

Default interval is 900 seconds. Wait ~15 minutes for at least one full tick.

## 3. Print last Risk Index log lines

To see the last 3 log lines that show the calculated Risk Index for active markets:

```bash
docker logs netbet-betfair-rest-client 2>&1 | tail -20
```

Then pick the last 3 lines that match the format:

`[Risk Index] Market: {market_id} | H: {home_risk} | A: {away_risk} | D: {draw_risk} | Vol: {total_volume}`

Example (actual format):

```
2025-02-06 14:15:00 [INFO] betfair_rest_client: [Risk Index] Market: 1.234567890 | H: -125.50 | A: -89.20 | D: -210.30 | Vol: 45230.00
2025-02-06 14:15:00 [INFO] betfair_rest_client: [Risk Index] Market: 1.234567891 | H: -98.10 | A: -156.40 | D: -87.20 | Vol: 32100.50
2025-02-06 14:15:00 [INFO] betfair_rest_client: [Risk Index] Market: 1.234567892 | H: -201.00 | A: -112.30 | D: -95.60 | Vol: 28700.00
```

One-liner to show only the last 3 `[Risk Index]` lines:

```bash
docker logs netbet-betfair-rest-client 2>&1 | grep "\[Risk Index\]" | tail -3
```

## 4. Database unique index (if not already applied)

On VPS, ensure the unique index exists to prevent duplicate snapshots on retries:

```bash
docker exec -i netbet-postgres psql -U netbet -d netbet << 'EOF'
CREATE UNIQUE INDEX IF NOT EXISTS idx_market_risk_snapshots_market_snapshot
ON market_risk_snapshots (market_id, snapshot_at);
EOF
```

Or from repo (from NetBet root):

```bash
docker exec -i netbet-postgres psql -U netbet -d netbet -f - < betfair-rest-client/scripts/ensure_unique_index.sql
```
