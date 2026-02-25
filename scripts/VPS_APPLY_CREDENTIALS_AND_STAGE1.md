# VPS: Apply Postgres credentials and run Stage 1–3

Run all steps **on the Linux VPS** (e.g. SSH into the box, then execute).

---

## 1) Update `/opt/netbet/.env` with Postgres credentials

### Option A – Script (one command)

From the repo root on the VPS:

```bash
cd /opt/netbet
./scripts/vps_apply_postgres_env.sh
```

This writes the three user/password pairs to `.env`. If you use other vars in `.env`, merge them manually or edit after.

### Option B – Manual edit

```bash
nano /opt/netbet/.env
```

Set exactly (copy as-is):

```
POSTGRES_REST_WRITER_USER=netbet_rest_writer
POSTGRES_REST_WRITER_PASSWORD=REST_WRITER_117

POSTGRES_STREAM_WRITER_USER=netbet_stream_writer
POSTGRES_STREAM_WRITER_PASSWORD=STREAM_WRITER_117

POSTGRES_ANALYTICS_READER_USER=netbet_analytics_reader
POSTGRES_ANALYTICS_READER_PASSWORD=ANALYTICS_READER_117
```

Save and exit (Ctrl+O, Enter, Ctrl+X).

---

## 2) Validate that credentials are set

```bash
grep -E 'POSTGRES_.*_PASSWORD' /opt/netbet/.env
```

**Pass criteria:** All three variables are present and none of the values are empty.

---

## 3) Restart the REST client only

```bash
cd /opt/netbet
docker compose up -d --force-recreate --no-deps betfair-rest-client
```

---

## 4) Wait, then re-run Stage 1 validation

Wait **15–20 minutes** for at least one snapshot cycle, then:

```bash
cd /opt/netbet
VALIDATE_ONLY=1 ./scripts/vps_stage1_deploy_and_validate.sh
```

**Stage 1 must pass:** 6 impedance columns exist, at least one recent row with non-null impedance, and `[Impedance]` lines appear in REST client logs.

---

## 5) If Stage 1 passes, continue with Stage 2 and Stage 3

```bash
cd /opt/netbet
./scripts/vps_stage2_deploy_and_validate.sh
./scripts/vps_stage3_deploy_and_validate.sh
```

---

## Acceptance

The blocker is resolved when **Stage 1 passes** and impedance data is written to Postgres.

If any step fails:

- Stop and capture the failing output.
- Capture the last 100 lines of REST client logs:  
  `docker logs netbet-betfair-rest-client --tail=100`
- Use that output to debug (e.g. credentials, DB connectivity, snapshot cycle).
