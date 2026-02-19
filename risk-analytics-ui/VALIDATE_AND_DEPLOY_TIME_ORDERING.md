# Time-Ordering Validation & Deployment (VPS)

## Pre-deployment validation (code-level)

Time-ordering changes are implemented as follows; no local API is required to confirm logic.

1. **Backend API** (`stream_data.py`): `get_event_buckets_stream` returns buckets in **ASC order** (oldest first). The previous `out.reverse()` was removed, so the last element is the latest snapshot.
2. **Frontend** (`EventDetail.tsx`): Latest bucket auto-selection uses `buckets[buckets.length - 1]`. Chart and bucket list use the same `buckets` array (no client-side re-sort), so chart is left→right (oldest→newest) and bucket buttons are top→bottom (oldest→newest).
3. **15-Minute Bucket Medians**: Still shows the **selected** bucket only; selection is by `bucket_start`, so it stays aligned with chart and list.
4. **Tick Audit View**: API returns ticks with `ORDER BY publish_time ASC`; table is oldest at top, newest at bottom.

---

## Validation checklist (run when API is available)

### 1. Backend API

```powershell
# From project root (PowerShell). Set $base to your API root (e.g. http://localhost:8000 or https://158.220.83.195).
$base = "http://localhost:8000"
.\risk-analytics-ui\scripts\validate_buckets_order.ps1 -BaseUrl $base -MarketId 1.253378204
```

Or on Linux/VPS:

```bash
curl -s "http://localhost:8000/stream/events/1.253378204/buckets" | python3 -c "
import sys, json
d = json.load(sys.stdin)
if not d: print('No buckets'); sys.exit(0)
starts = [b['bucket_start'] for b in d if b.get('bucket_start')]
for i in range(1, len(starts)):
    if starts[i] <= starts[i-1]:
        print('FAIL: not ASC'); sys.exit(1)
print('OK: ASC, first=', starts[0], 'last=', starts[-1])
"
```

- Confirm buckets are in **ASC order (oldest first)**.
- Confirm the **latest snapshot is the last element**.

### 2. History (15-min snapshots) chart

- Chart runs **left → right (oldest → newest)**.
- Rightmost point = latest bucket.

### 3. Select 15-minute bucket

- List is **top → bottom (oldest → newest)**.
- Selecting the **last** bucket matches the rightmost chart point.

### 4. 15-Minute Bucket Medians

- Select first, middle, and last bucket; medians match the selected bucket.

### 5. Tick Audit View

- Ticks ordered **oldest at top, newest at bottom**.

---

## Deployment (VPS via SSH)

SSH from your **local machine** (replace `<user>` if different):

```bash
ssh <user>@158.220.83.195
```

On the VPS (adjust `/path/to/project` to your repo path, e.g. `/opt/netbet` or `~/NetBet`):

```bash
cd /path/to/project
git pull
./risk-analytics-ui/scripts/vps_deploy_time_ordering.sh
```

Or step by step:

```bash
cd /path/to/project
git pull

docker compose -f docker-compose.yml -f risk-analytics-ui/docker-compose.yml build --no-cache risk-analytics-ui-api risk-analytics-ui-web
docker compose -f docker-compose.yml -f risk-analytics-ui/docker-compose.yml up -d --force-recreate risk-analytics-ui-api risk-analytics-ui-web

docker ps
```

Then run the validation script (or curl) against the production API (e.g. `http://localhost:8000` on the VPS or your public URL).

---

## Post-deployment validation

1. Hard refresh browser (Ctrl+Shift+R / Cmd+Shift+R).
2. Recheck chart direction and bucket list order in production.
3. Confirm no console errors.
4. Optionally run `validate_buckets_order.ps1` or the curl snippet against the production base URL.

---

## Rollback

On the VPS:

```bash
cd /path/to/project
git checkout <previous_commit>
docker compose -f docker-compose.yml -f risk-analytics-ui/docker-compose.yml build risk-analytics-ui-api risk-analytics-ui-web
docker compose -f docker-compose.yml -f risk-analytics-ui/docker-compose.yml up -d --force-recreate risk-analytics-ui-api risk-analytics-ui-web
```
