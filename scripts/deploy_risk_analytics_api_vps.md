# Rebuild and Redeploy risk-analytics-ui-api on VPS

**Method used:** Option B — Transfer via code + build on VPS (no local Docker required)

---

## Step 1 — Local Verification (Windows)

### Code confirmation

- [x] DB query selects L1 columns: `_l1_size_cols = ", home_best_back_size_l1, away_best_back_size_l1, draw_best_back_size_l1, home_best_lay_size_l1, away_best_lay_size_l1, draw_best_lay_size_l1"`
- [x] DTO/serializer includes: `*_best_back_size_l1`, `*_best_lay_size_l1`
- [x] impedanceInputs: `out["impedanceInputs"] = { "home": _impedance_inputs_from_row(r, "home"), ... }`

### Optional: Local Build (requires Docker Desktop)

If Docker Desktop is running on Windows:

```powershell
cd c:\Users\WatMax\NetBet\risk-analytics-ui\api
docker build -t netbet-risk-analytics-ui-api:latest .
docker images | findstr risk-analytics-ui-api
```

---

## Step 2 — Transfer to VPS

**Option A — Docker Registry (if available)**

```powershell
docker tag netbet-risk-analytics-ui-api:latest <registry>/netbet-risk-analytics-ui-api:latest
docker push <registry>/netbet-risk-analytics-ui-api:latest
# On VPS: docker pull <registry>/netbet-risk-analytics-ui-api:latest
```

**Option B — Docker Save (if local build)**

```powershell
docker save netbet-risk-analytics-ui-api:latest -o risk-analytics-ui-api.tar
scp -i C:\Users\WatMax\.ssh\id_ed25519_contabo risk-analytics-ui-api.tar root@158.220.83.195:/opt/netbet/
# On VPS: docker load -i /opt/netbet/risk-analytics-ui-api.tar
```

**Option C — Code Transfer + Build on VPS** (used when local Docker not available)

```powershell
scp -i C:\Users\WatMax\.ssh\id_ed25519_contabo -r risk-analytics-ui/api root@158.220.83.195:/opt/netbet/risk-analytics-ui/
```

---

## Step 3 — Redeploy on VPS (Linux)

```bash
cd /opt/netbet
docker compose build risk-analytics-ui-api --no-cache
docker compose stop risk-analytics-ui-api 2>/dev/null
docker compose rm -f risk-analytics-ui-api 2>/dev/null
docker compose up -d risk-analytics-ui-api --no-deps
docker ps | grep risk-analytics-ui-api
docker logs risk-analytics-ui-api --tail 30
```

---

## Step 4 — API Verification

```bash
curl -s 'http://127.0.0.1:8000/events/1.253002724/timeseries?include_impedance=true&include_impedance_inputs=true&limit=1' | tail -c 1500
```

Confirm JSON includes:
- `home_best_back_size_l1`, `away_best_back_size_l1`, `draw_best_back_size_l1`
- `home_best_lay_size_l1`, `away_best_lay_size_l1`, `draw_best_lay_size_l1`
- `impedanceInputs` with `backStake`, `layStake`, `backOdds`, `layOdds` per outcome

---

## Completion criteria

- [x] API container built from updated source (Option C: code transfer + build on VPS)
- [x] JSON response contains L1 size fields and impedanceInputs
- [x] No regression in impedance/risk output
- [x] Container runs without errors

---

## Deployment Report (2026-02-14)

| Item | Value |
|------|-------|
| **Method** | Option C — Code transfer via SCP, build on VPS |
| **Git commit hash** | ed6e8ee4e1fae42bf5c4aa7d6445a6e3773754c2 |
| **Deployment timestamp** | 2026-02-14 ~07:41 UTC |
| **Container** | risk-analytics-ui-api (netbet-risk-analytics-ui-api:latest) |

### JSON sample (newest snapshot 2026-02-14 06:28:16, market 1.253002724)

```json
{
  "home_best_back_size_l1": 533.92,
  "away_best_back_size_l1": 23.75,
  "draw_best_back_size_l1": 115.48,
  "home_best_lay_size_l1": 309.11,
  "away_best_lay_size_l1": 230.88,
  "draw_best_lay_size_l1": 10.87,
  "impedanceInputs": {
    "home": {"backStake": 1220.5, "backOdds": 2.12, "layStake": 875.19, "layOdds": 2.20, ...},
    "away": {"backStake": 283.87, "backOdds": 3.67, "layStake": 671.54, "layOdds": 3.91, ...},
    "draw": {"backStake": 941.98, "backOdds": 3.59, "layStake": 158.87, "layOdds": 3.78, ...}
  }
}
```

Values match DB (home_back_stake 1220.5, home_best_back_size_l1 533.92).
