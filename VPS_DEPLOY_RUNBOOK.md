# VPS Staged Deploy — Runbook

Run all commands **on the VPS** (after SSH) from `/opt/netbet`, unless noted.

---

## Step 0 — SSH

From your local machine (NetBet folder):

```bash
ssh <your-vps-user>@<your-vps-host>
cd /opt/netbet
pwd   # must show /opt/netbet
```

---

## Step 1 — Postgres credentials

```bash
cd /opt/netbet
./scripts/vps_apply_postgres_env.sh
```

**Validate:**

```bash
grep -E 'POSTGRES_.*_PASSWORD' /opt/netbet/.env
```

**Pass:** All three keys with non-empty values:

- `POSTGRES_REST_WRITER_PASSWORD=...`
- `POSTGRES_STREAM_WRITER_PASSWORD=...`
- `POSTGRES_ANALYTICS_READER_PASSWORD=...`

**Fail:** Stop; fix `.env` or script, re-run and re-check.

---

## Step 2 — Restart REST client only

```bash
cd /opt/netbet
docker compose up -d --force-recreate --no-deps betfair-rest-client
```

**Check:**

```bash
docker ps --filter name=betfair-rest-client
```

**If unhealthy:**

```bash
docker logs netbet-betfair-rest-client --tail=100
```

---

## Step 3 — Wait then Stage 1 validate

Wait **15–20 minutes** for at least one snapshot with the new REST client.

Then:

```bash
cd /opt/netbet
VALIDATE_ONLY=1 ./scripts/vps_stage1_deploy_and_validate.sh
```

**Pass:**

- 1.1: 6 impedance columns in `market_derived_metrics`
- 1.2: ≥1 recent row with non-null impedance (last 7 days)
- 1.3: `[Impedance]` in last 200 REST client log lines (or WARN if no markets yet)

**Fail:** Capture full script output and:

```bash
docker logs netbet-betfair-rest-client --tail=100
```

Do not proceed to Stage 2 until Stage 1 passes.

---

## Step 4 — Stage 2 (API)

```bash
cd /opt/netbet
./scripts/vps_stage2_deploy_and_validate.sh
```

**Pass:**

- No HTTP 5xx on `/leagues`, `/leagues/.../events`, `/events/.../timeseries`
- `imbalance` present in event and timeseries responses
- `impedanceNorm` present when `include_impedance=true`

**Fail:** Capture full script output and API container logs; do not proceed to Stage 3.

---

## Step 5 — Stage 3 (Web/UI)

```bash
cd /opt/netbet
./scripts/vps_stage3_deploy_and_validate.sh
```

**From your machine (browser):**

- Hard refresh (Ctrl+F5) or Incognito.
- Confirm:
  - Imbalance (H/A/D) unchanged.
  - “Impedance (norm) (H/A/D)” appears when “Include Impedance” is on.
  - Imbalance and Impedance shown side by side.

**Script pass:** HTTP 200 on UI root and SPA `#root` present.

---

## Completion

Deployment is complete when:

- Stage 1 script and checks pass
- Stage 2 script and checks pass  
- Stage 3 script passes and UI checks (above) pass

---

## If something fails

Collect and share:

1. Full output of the failing step (e.g. `VALIDATE_ONLY=1 ./scripts/vps_stage1_deploy_and_validate.sh`).
2. If REST-related: `docker logs netbet-betfair-rest-client --tail=100`.
3. If Stage 2: API container logs if the script or errors point to the API.
4. If Stage 3 (UI): page/route, filters/toggles, what you see vs expected (or screenshots).
