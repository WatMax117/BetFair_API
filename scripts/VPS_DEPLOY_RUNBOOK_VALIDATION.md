# VPS Deploy Runbook — Validation Outputs

Run all commands **on the Linux VPS** via SSH, under `/opt/netbet`.  
Do not proceed to the next stage unless the current one **passes**.  
Paste the requested outputs back for acceptance.

---

## Step 1 — Apply Postgres credentials

```bash
cd /opt/netbet
./scripts/vps_apply_postgres_env.sh
```

**Validation output to paste:**

```bash
grep -E 'POSTGRES_.*_PASSWORD' /opt/netbet/.env
```

👉 **Paste the output here.** (Values may be masked as `***`; keys must be present and non-empty.)

---

## Step 2 — Restart REST client

```bash
cd /opt/netbet
docker compose up -d --force-recreate --no-deps betfair-rest-client
```

**Wait 15–20 minutes** for at least one snapshot cycle before Step 3.

---

## Step 3 — Stage 1 validation (DB + data)

```bash
cd /opt/netbet
VALIDATE_ONLY=1 ./scripts/vps_stage1_deploy_and_validate.sh
```

**Validation output to paste:** **Full output** of the script.

**Stage 1 PASS criteria:**
- All 6 impedance columns exist.
- At least one recent row has non-null impedance values.
- [Impedance] entries appear in REST client logs (or WARN if none yet).

If it fails, also run and paste:

```bash
docker logs netbet-betfair-rest-client --tail=100
```

---

## Step 4 — Stage 2 validation (API)

```bash
cd /opt/netbet
./scripts/vps_stage2_deploy_and_validate.sh
```

**Validation output to paste:** **Full output** of the script.

**Stage 2 PASS criteria:**
- `imbalance` is always present.
- `impedanceNorm` is present when `include_impedance=true`.
- No 5xx errors.

---

## Step 5 — Stage 3 validation (Web/UI)

```bash
cd /opt/netbet
./scripts/vps_stage3_deploy_and_validate.sh
```

Then validate **manually** from a browser (hard refresh or incognito).

**Confirmation to provide (textual):**
- [ ] Imbalance (H/A/D) is unchanged.
- [ ] "Impedance (norm) (H/A/D)" appears as a separate row/block when enabled.
- [ ] Imbalance and Impedance are visible side by side.

---

## Acceptance checklist

Task is complete when you have provided:

1. **Step 1** — `grep -E 'POSTGRES_.*_PASSWORD'` output  
2. **Stage 1** — Full Stage 1 validation script output  
3. **Stage 2** — Full Stage 2 validation script output  
4. **Stage 3** — Confirmation that UI checks pass (textual)

Paste all outputs **in order**. Do not proceed to the next stage unless the current one passes.
