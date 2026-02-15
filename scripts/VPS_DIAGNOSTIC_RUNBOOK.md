# VPS Diagnostic Runbook - Backend Issues Investigation

## Overview

This runbook provides step-by-step instructions to diagnose two backend issues on the VPS production environment:

1. **Snapshot ingestion appears to have stopped**
2. **Impedance (third-level index) not returned/rendered**

## Prerequisites

- SSH access to VPS
- Docker access on VPS
- PostgreSQL access (via Docker exec)

## Quick Start

### Option 1: Run Master Diagnostic Script

```bash
# SSH to VPS
ssh user@vps

# Navigate to project directory
cd /opt/netbet

# Run master diagnostic script
bash scripts/vps_diagnose_both_issues.sh
```

### Option 2: Run Individual Diagnostic Scripts

```bash
# Snapshot ingestion diagnostic
bash scripts/diagnose_snapshot_ingestion.sh

# Impedance diagnostic
bash scripts/diagnose_impedance.sh [market_id]

# Test API endpoint
bash scripts/test_api_impedance.sh [market_id]
```

### Option 3: Run SQL Queries Directly

```bash
# Snapshot ingestion check
docker exec -i netbet-postgres psql -U netbet -d netbet < scripts/check_snapshot_ingestion.sql

# Impedance data check
docker exec -i netbet-postgres psql -U netbet -d netbet < scripts/check_impedance_data.sql
```

---

## Issue 1: Snapshot Ingestion Investigation

### Step 1: Check Container Status

```bash
# Check if container is running
docker ps --filter "name=betfair-rest-client"

# Check container state details
docker inspect netbet-betfair-rest-client --format='{{.State.Status}}'

# If not running, check why
docker ps -a --filter "name=betfair-rest-client"
docker inspect netbet-betfair-rest-client --format='{{.State.ExitCode}}'
```

**Expected:** Container should be `running`

**If stopped:**
- Check logs: `docker logs netbet-betfair-rest-client`
- Check restart policy: `docker inspect netbet-betfair-rest-client --format='{{.HostConfig.RestartPolicy}}'`
- Restart: `docker restart netbet-betfair-rest-client`

### Step 2: Check Heartbeat Files

```bash
# Check heartbeat_alive
docker exec netbet-betfair-rest-client cat /app/data/heartbeat_alive
docker exec netbet-betfair-rest-client stat -c %Y /app/data/heartbeat_alive

# Check heartbeat_success
docker exec netbet-betfair-rest-client cat /app/data/heartbeat_success
docker exec netbet-betfair-rest-client stat -c %Y /app/data/heartbeat_success

# Calculate age
ALIVE_TS=$(docker exec netbet-betfair-rest-client stat -c %Y /app/data/heartbeat_alive)
NOW=$(date +%s)
AGE=$((NOW - ALIVE_TS))
echo "Age: ${AGE} seconds ($(($AGE / 60)) minutes)"
```

**Expected:** 
- Both files should exist
- Age should be < 20 minutes (default interval is 900s = 15 min)

**If stale:**
- Container may have stopped processing
- Check logs for errors

### Step 3: Check Latest Snapshot Timestamp

```bash
docker exec netbet-postgres psql -U netbet -d netbet -c "
SELECT 
    MAX(snapshot_at) as latest_snapshot_at,
    COUNT(*) as total_snapshots,
    NOW() - MAX(snapshot_at) as age,
    EXTRACT(EPOCH FROM (NOW() - MAX(snapshot_at)))::int as seconds_since_latest
FROM rest_ingest.market_book_snapshots;
"
```

**Expected:**
- Latest snapshot should be within last 15-30 minutes
- Total snapshots should be increasing

**If stale:**
- Ingestion has stopped
- Check container logs for errors

### Step 4: Check Container Logs

```bash
# Last 100 lines
docker logs --tail 100 netbet-betfair-rest-client

# Search for errors
docker logs netbet-betfair-rest-client 2>&1 | grep -i error | tail -20

# Search for warnings
docker logs netbet-betfair-rest-client 2>&1 | grep -i warning | tail -20

# Check for session/auth errors
docker logs netbet-betfair-rest-client 2>&1 | grep -i "session\|auth\|login" | tail -20
```

**Common Issues:**
- `INVALID_SESSION` / `SESSION_EXPIRED` → Authentication failure
- `Connection refused` → Database connectivity issue
- `No markets with exactly 3 runners` → Filtering out all markets
- `Tick deadline exceeded` → API calls taking too long

### Step 5: Check Snapshot Rate

```bash
docker exec netbet-postgres psql -U netbet -d netbet -c "
SELECT 
    DATE_TRUNC('minute', snapshot_at) as minute_bucket,
    COUNT(*) as snapshot_count
FROM rest_ingest.market_book_snapshots
WHERE snapshot_at >= NOW() - INTERVAL '1 hour'
GROUP BY minute_bucket
ORDER BY minute_bucket DESC
LIMIT 10;
"
```

**Expected:** Regular snapshots every 15 minutes (or configured interval)

---

## Issue 2: Impedance Data Investigation

### Step 1: Check Impedance Column Existence

```bash
docker exec netbet-postgres psql -U netbet -d netbet -c "
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'rest_ingest'
  AND table_name = 'market_derived_metrics'
  AND column_name LIKE '%impedance%'
ORDER BY column_name;
"
```

**Expected:** Should see columns:
- `home_impedance`, `away_impedance`, `draw_impedance`
- `home_impedance_norm`, `away_impedance_norm`, `draw_impedance_norm`
- `home_back_stake`, `home_back_odds`, `home_lay_stake`, `home_lay_odds`
- (and same for away/draw)

### Step 2: Check Impedance Data Availability

```bash
docker exec netbet-postgres psql -U netbet -d netbet -c "
SELECT 
    COUNT(*) as total_rows,
    COUNT(home_impedance) as rows_with_home_impedance,
    COUNT(home_impedance_norm) as rows_with_home_impedance_norm,
    ROUND(100.0 * COUNT(home_impedance) / NULLIF(COUNT(*), 0), 2) as pct_with_impedance,
    MAX(snapshot_at) as latest_snapshot_with_impedance
FROM rest_ingest.market_derived_metrics;
"
```

**Expected:**
- `rows_with_home_impedance` > 0 if impedance is being computed
- `pct_with_impedance` should be > 0%

**If 0%:**
- Impedance is not being computed
- Check logs for impedance computation errors

### Step 3: Check Sample Impedance Values

```bash
docker exec netbet-postgres psql -U netbet -d netbet -c "
SELECT 
    snapshot_id,
    snapshot_at,
    market_id,
    home_impedance,
    home_impedance_norm,
    away_impedance,
    draw_impedance
FROM rest_ingest.market_derived_metrics
WHERE home_impedance IS NOT NULL
ORDER BY snapshot_at DESC
LIMIT 5;
"
```

**Expected:** Should see non-null impedance values

### Step 4: Check Recent Snapshots Without Impedance

```bash
docker exec netbet-postgres psql -U netbet -d netbet -c "
SELECT 
    snapshot_id,
    snapshot_at,
    market_id
FROM rest_ingest.market_derived_metrics
WHERE home_impedance IS NULL
  AND away_impedance IS NULL
  AND draw_impedance IS NULL
ORDER BY snapshot_at DESC
LIMIT 10;
"
```

**If recent snapshots lack impedance:**
- Impedance computation may have stopped
- Check logs for `[Impedance]` entries

### Step 5: Check Impedance Computation Logs

```bash
# Search for impedance logs
docker logs netbet-betfair-rest-client 2>&1 | grep -i "impedance" | tail -20

# Check for errors during computation
docker logs netbet-betfair-rest-client 2>&1 | grep -i "impedance\|selectionId\|role" | tail -30
```

**Expected:** Should see log entries like:
```
[Impedance] market=... selectionId=... impedance=... normImpedance=...
```

**If missing:**
- `compute_impedance_index()` may not be called
- SelectionId matching may be failing

### Step 6: Test API Endpoint

```bash
# First, get a market_id with impedance data
MARKET_ID=$(docker exec netbet-postgres psql -U netbet -d netbet -t -c "
SELECT market_id FROM rest_ingest.market_derived_metrics 
WHERE home_impedance IS NOT NULL 
ORDER BY snapshot_at DESC LIMIT 1;
" | tr -d ' ')

# Test API endpoint
curl -s "http://localhost:8000/events/$MARKET_ID/timeseries?include_impedance=true&limit=1" | jq '.[0] | {snapshot_at, has_impedance: (.impedance != null), has_impedanceNorm: (.impedanceNorm != null), impedance, impedanceNorm}'
```

**Expected:**
- Response should contain `impedance` and `impedanceNorm` fields
- Values should be non-null

**If missing:**
- API may not be handling `include_impedance=true` correctly
- Check API code: `risk-analytics-ui/api/app/main.py` lines 447-450, 522-538

### Step 7: Check Frontend API Calls

```bash
# Check API logs for requests
docker logs risk-analytics-ui-api 2>&1 | grep "timeseries" | tail -20

# Check if include_impedance parameter is present
docker logs risk-analytics-ui-api 2>&1 | grep "include_impedance" | tail -10
```

**Expected:** Frontend should be calling API with `include_impedance=true`

---

## Common Issues & Solutions

### Snapshot Ingestion Stopped

1. **Container Stopped**
   - Restart: `docker restart netbet-betfair-rest-client`
   - Check why it stopped: `docker logs netbet-betfair-rest-client`

2. **Authentication Failure**
   - Check Betfair API credentials in `.env`
   - Verify certificates: `docker exec netbet-betfair-rest-client ls -la /app/certs/`
   - Check logs for `INVALID_SESSION`

3. **Database Connection Issues**
   - Verify PostgreSQL is running: `docker ps | grep postgres`
   - Check connection: `docker exec netbet-postgres psql -U netbet -d netbet -c "SELECT 1;"`
   - Check credentials in environment

4. **No Markets Available**
   - Check logs for "No markets with exactly 3 runners"
   - Verify Betfair API is returning markets
   - Check time window configuration

### Impedance Not Returned

1. **Impedance Not Computed**
   - Check logs for `[Impedance]` entries
   - Verify `compute_impedance_index()` is being called
   - Check for SelectionId matching errors

2. **SelectionId Mismatch**
   - Verify `runner_metadata` mapping exists in database
   - Check logs for "Skipping market ... no metadata mapping"
   - Verify selectionId types match (int vs str)

3. **API Not Returning Impedance**
   - Verify `include_impedance=true` in API request
   - Check API SQL query includes impedance columns
   - Verify API response serialization includes impedance

4. **Database Columns Missing**
   - Run schema migration if needed
   - Verify columns exist: `SELECT column_name FROM information_schema.columns WHERE table_name = 'market_derived_metrics' AND column_name LIKE '%impedance%';`

---

## Output Files

After running diagnostics, review:

1. **Container logs**: `docker logs netbet-betfair-rest-client > rest_client_logs.txt`
2. **API logs**: `docker logs risk-analytics-ui-api > api_logs.txt`
3. **Database queries**: Save SQL query outputs to files

---

## Next Steps After Diagnosis

1. **If ingestion stopped:**
   - Fix root cause (auth, DB, etc.)
   - Restart container
   - Monitor logs for successful ticks

2. **If impedance missing:**
   - Verify computation is running
   - Check SelectionId matching
   - Verify API endpoint returns impedance
   - Check frontend requests include `include_impedance=true`

3. **Share findings:**
   - Container status
   - Latest snapshot timestamp
   - Impedance data statistics
   - API endpoint test results
   - Any errors from logs
