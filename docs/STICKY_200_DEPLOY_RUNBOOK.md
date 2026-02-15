# Sticky Pre-Match K=200: Implement, Validate, and Deploy

This runbook covers code/config confirmation, local validation, Docker build/tag, production deployment via SSH, post-deploy validation, and rollback.

---

## 1. Code & Configuration (Confirm)

### 1.1 Defaults in `betfair-rest-client/main.py`

| Variable | Default | Status |
|----------|---------|--------|
| `BF_STICKY_K` | 200 | ✓ |
| `BF_KICKOFF_BUFFER_SECONDS` | 60 | ✓ |
| `BF_STICKY_CATALOGUE_MAX` | 400 | ✓ |
| `BF_MARKET_BOOK_BATCH_SIZE` | 50 | unchanged |
| `BF_INTERVAL_SECONDS` | (e.g. 900) | set via env |

### 1.2 Optional env (safe defaults if missing)

| Variable | Default | Description |
|----------|---------|-------------|
| `BF_STICKY_NEAR_KICKOFF_HOURS` | 2 | Use relaxed maturity when kickoff within this many hours |
| `BF_STICKY_NEAR_KICKOFF_CONSECUTIVE_TICKS` | 1 | Consecutive ticks required in that window |

### 1.3 Maturity rule

- `hours_to_kickoff` = from `event_start_utc`.
- If `hours_to_kickoff ≤ BF_STICKY_NEAR_KICKOFF_HOURS` → `required_consecutive_ticks = BF_STICKY_NEAR_KICKOFF_CONSECUTIVE_TICKS` (default 1).
- Else → `required_consecutive_ticks = BF_STICKY_REQUIRE_CONSECUTIVE_TICKS` (default 2).

### 1.4 Removal and refill

- **No eviction by rank.** Markets drop only if:
  - `now_utc >= event_start_utc + BF_KICKOFF_BUFFER_SECONDS`, or
  - invalid / not found in API response.
- Refill: when `tracked_count < K`, candidates are admitted until full (see `sticky_prematch.admit_markets`).

---

## 2. Local Validation Before Build

Run the collector locally with sticky K=200 so that logs can be checked before building and pushing an image.

### 2.1 Environment

Set (e.g. in `.env` or export):

```bash
BF_STICKY_PREMATCH=1
BF_STICKY_K=200
BF_STICKY_CATALOGUE_MAX=400
BF_KICKOFF_BUFFER_SECONDS=60
BF_STICKY_NEAR_KICKOFF_HOURS=2
BF_STICKY_NEAR_KICKOFF_CONSECUTIVE_TICKS=1
BF_MARKET_BOOK_BATCH_SIZE=50
BF_INTERVAL_SECONDS=900
```

Ensure Postgres and (if used) auth-service are running and credentials are set (`POSTGRES_*`, cert paths, etc.).

### 2.2 Run

From repo root:

```bash
docker compose up betfair-rest-client
# or, if running Python directly:
# cd betfair-rest-client && export $(cat ../.env | xargs) && python -u main.py
```

### 2.3 What to verify

- `tracked_count` increases toward **200** over ticks.
- When full:
  - `markets_polled ≈ 200`
  - `requests_per_tick = 4` (200 / 50).
- Around kickoff:
  - `expired > 0`
  - `admitted_per_tick > 0` until `tracked_count` returns to ~200.
- No in-play polling after kickoff+buffer (markets disappear from poll set after expiry).

**Target stable log line (full capacity):**

```
[Sticky] tick_id=... tracked_count=200 admitted_per_tick=0 expired=0 requests_per_tick=4 markets_polled=200
```

If this behavior is observed consistently, proceed to build and deploy.

---

## 3. Docker Build & Tagging

Use a versioned tag so the previous stable tag is not overwritten.

### 3.1 Tag format

```
sticky200-YYYYMMDD-<short_sha>
```

Example: `sticky200-20250215-a1b2c3d`

### 3.2 Build (from repo root)

```bash
# Replace <registry>/<image> with your registry and image name (e.g. ghcr.io/myorg/betfair-rest-client or myregistry.net/netbet/betfair-rest-client)
export SHORT_SHA=$(git rev-parse --short HEAD)
export DATE_TAG=$(date +%Y%m%d)
export IMAGE_TAG=sticky200-${DATE_TAG}-${SHORT_SHA}
export IMAGE_NAME=<registry>/<image>   # e.g. ghcr.io/myorg/betfair-rest-client

docker build -t "${IMAGE_NAME}:${IMAGE_TAG}" ./betfair-rest-client
```

### 3.3 Push

```bash
docker push "${IMAGE_NAME}:${IMAGE_TAG}"
```

### 3.4 Optional: build script

From repo root:

```bash
export IMAGE_NAME=<registry>/<image>   # e.g. ghcr.io/myorg/betfair-rest-client
./scripts/build_sticky200_image.sh
# Then run the docker push command the script prints.
```

Script: `scripts/build_sticky200_image.sh`.

---

## 4. Production Deployment (via SSH)

### 4.1 SSH and go to deployment directory

```bash
ssh <user>@<server>
cd /opt/netbet
# Or your actual deployment path, e.g. /path/to/deployment
```

### 4.2 Backup current config

```bash
cp .env .env.backup.$(date +%F_%H%M)
cp docker-compose.yml docker-compose.yml.backup.$(date +%F_%H%M)
```

### 4.3 Update environment configuration

Ensure `.env` (in the deployment directory) contains:

```bash
BF_STICKY_PREMATCH=1
BF_STICKY_K=200
BF_STICKY_CATALOGUE_MAX=400
BF_KICKOFF_BUFFER_SECONDS=60
BF_STICKY_NEAR_KICKOFF_HOURS=2
BF_STICKY_NEAR_KICKOFF_CONSECUTIVE_TICKS=1
BF_MARKET_BOOK_BATCH_SIZE=50
BF_INTERVAL_SECONDS=900
```

If any variable is omitted, the defaults in `docker-compose.yml` for `betfair-rest-client` apply (sticky 200 as above).

### 4.4 Use new image (if using pre-built image)

If you deploy a pre-built image instead of building on the server, set the image tag.

**Option A – in `.env`:**

```bash
BETFAIR_REST_CLIENT_IMAGE=<registry>/<image>:sticky200-YYYYMMDD-<sha>
```

Then in `docker-compose.yml` the `betfair-rest-client` service must use:

```yaml
image: ${BETFAIR_REST_CLIENT_IMAGE}
# comment out or remove the build: block when using pre-built image
```

**Option B – build on server:**

From the deployment directory (with updated code, e.g. from git pull):

```bash
docker compose build betfair-rest-client
```

No image tag needed; the built image will be used.

### 4.5 Pull and restart

```bash
docker compose pull
docker compose up -d
```

If you built on the server (no pull):

```bash
docker compose up -d --build betfair-rest-client
```

Use `docker-compose` instead of `docker compose` if your environment uses the legacy binary.

---

## 5. Post-Deployment Validation

### 5.1 Container running

```bash
docker ps
```

Confirm `netbet-betfair-rest-client` (or your container name) is running.

### 5.2 Logs (several ticks)

```bash
docker logs -f --tail=200 netbet-betfair-rest-client
```

Confirm:

- `tracked_count` reaches **200** (when candidate supply is sufficient).
- `requests_per_tick = 4` at full capacity.
- When markets expire around kickoff, `expired > 0` and `admitted_per_tick > 0` until capacity refills to ~200.
- No rate-limit or API error spikes.
- No unexpected early removal (only kickoff+buffer or invalid/not found).

### 5.3 Resources

```bash
docker stats --no-stream
```

Check that CPU/memory are within expected bounds (e.g. existing limits in compose).

---

## 6. Acceptance Criteria

Deployment is considered successful when:

- `tracked_count` stabilizes at **200** (given sufficient catalogue candidates).
- `markets_polled ≈ 200` per tick when full.
- `requests_per_tick = 4` when full.
- Markets remain tracked until kickoff+buffer (no rank-based eviction).
- Expired markets trigger refill (`admitted_per_tick > 0` until full again).
- No abnormal API errors or performance degradation.

---

## 7. Rollback Procedure

If issues occur:

1. Restore previous config and/or image tag:
   - Restore `.env`: `cp .env.backup.<timestamp> .env`
   - Or set previous image tag in `.env` / compose and pull that image.
   - Restore `docker-compose.yml` if needed: `cp docker-compose.yml.backup.<timestamp> docker-compose.yml`

2. Restart:

   ```bash
   docker compose up -d
   ```

3. Verify previous stable behavior in logs (`docker logs -f netbet-betfair-rest-client`).

---

## 8. Reference

- Sticky pre-match spec and runbook (env vars, metrics): `betfair-rest-client/STICKY_PREMATCH_SPEC.md` (§7 and §7a).
- Main compose: repo root `docker-compose.yml` (sticky env vars with defaults for K=200).
