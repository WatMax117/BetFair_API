# Backend Issues Investigation Summary

## Issue 1: Snapshot Ingestion Appears Stopped

### Investigation Steps

1. **Check Container Status**
   ```bash
   docker ps --filter "name=betfair-rest-client"
   docker logs --tail 100 netbet-betfair-rest-client
   ```

2. **Check Heartbeat Files**
   - `/app/data/heartbeat_alive` - Should be updated every tick
   - `/app/data/heartbeat_success` - Updated after successful tick
   - Age should be < 20 minutes (default interval is 900s = 15 min)

3. **Check Database Activity**
   ```sql
   -- Latest snapshot timestamp
   SELECT MAX(snapshot_at), COUNT(*), NOW() - MAX(snapshot_at) as age
   FROM rest_ingest.market_book_snapshots;
   ```

4. **Check Logs for Errors**
   - Look for: `ERROR`, `WARNING`, `Exception`, `failed`, `Session expired`
   - Check for API authentication failures
   - Check for database connection errors

### Possible Causes

1. **Container Stopped/Crashed**
   - Container may have exited
   - Check: `docker ps -a` for exited containers

2. **Authentication Failure**
   - Betfair API credentials expired
   - Certificate issues
   - Check logs for: `INVALID_SESSION`, `LOGIN_REQUIRED`

3. **Database Connection Issues**
   - PostgreSQL connection failures
   - Schema/permission issues
   - Check logs for: `psycopg2`, `connection`, `permission denied`

4. **No Markets Available**
   - Betfair API returning empty catalogue
   - All markets filtered out (not 3-way)
   - Check logs for: `No markets with exactly 3 runners`

5. **Tick Deadline Exceeded**
   - API calls taking too long
   - Check logs for: `Tick deadline exceeded`

### Diagnostic Scripts

- `scripts/diagnose_snapshot_ingestion.sh` - Full diagnostic
- `scripts/check_snapshot_ingestion.sql` - Database queries
- `scripts/diagnose_both_issues.ps1` - PowerShell version

---

## Issue 2: Impedance Not Returned/Rendered

### Investigation Steps

1. **Check Database Schema**
   ```sql
   SELECT column_name FROM information_schema.columns
   WHERE table_name = 'market_derived_metrics'
   AND column_name LIKE '%impedance%';
   ```

2. **Check Impedance Data Availability**
   ```sql
   SELECT 
       COUNT(*) as total,
       COUNT(home_impedance) as with_impedance,
       MAX(snapshot_at) as latest
   FROM rest_ingest.market_derived_metrics;
   ```

3. **Test API Endpoint**
   ```bash
   curl "http://localhost:8000/events/{market_id}/timeseries?include_impedance=true"
   ```
   - Check if `impedance` and `impedanceNorm` fields are present
   - Verify field structure matches frontend expectations

4. **Check Recent Snapshots**
   ```sql
   SELECT snapshot_id, snapshot_at, market_id,
          home_impedance, home_impedance_norm
   FROM rest_ingest.market_derived_metrics
   ORDER BY snapshot_at DESC LIMIT 10;
   ```

### Possible Causes

1. **Impedance Not Computed**
   - `compute_impedance_index()` failing silently
   - SelectionId matching failing (line 740-746 in main.py)
   - Check logs for: `[Impedance]` log entries

2. **SelectionId Mismatch**
   - `runner_metadata` mapping not matching impedance output
   - Type mismatch (int vs str) in selectionId
   - Code tries both: `runner_metadata.get(sid)` and `runner_metadata.get(int(sid))`

3. **API Not Returning Impedance**
   - `include_impedance` flag not handled correctly
   - SQL query not selecting impedance columns
   - Check API code: `risk-analytics-ui/api/app/main.py` lines 447-450, 522-538

4. **Database Columns Missing**
   - Impedance columns not created in schema
   - Migration not applied
   - Check: `_ensure_three_layer_tables()` in main.py (lines 396-404)

5. **Frontend Not Requesting Impedance**
   - API call missing `include_impedance=true`
   - Check frontend API calls in `risk-analytics-ui/web/src/api.ts`

### Code Flow

1. **Computation** (`betfair-rest-client/main.py:720`)
   ```python
   impedance_out = compute_impedance_index(runners, snapshot_ts=snapshot_at)
   ```

2. **Mapping** (`betfair-rest-client/main.py:739-767`)
   - Maps impedance output by selectionId to HOME/AWAY/DRAW roles
   - Uses `runner_metadata` dict from database

3. **Storage** (`betfair-rest-client/main.py:792`)
   ```python
   _insert_derived_metrics(conn, snapshot_id, snapshot_at, market_id, metrics)
   ```

4. **API Retrieval** (`risk-analytics-ui/api/app/main.py:447-450`)
   - SQL query conditionally includes impedance columns
   - Returns in response if `include_impedance=true`

### Diagnostic Scripts

- `scripts/diagnose_impedance.sh` - Full diagnostic
- `scripts/check_impedance_data.sql` - Database queries
- `scripts/test_api_impedance.sh` - API endpoint test

---

## Quick Diagnostic Commands

### Snapshot Ingestion
```bash
# Check container
docker ps | grep betfair-rest-client

# Check latest snapshot
docker exec netbet-postgres psql -U netbet -d netbet -c \
  "SELECT MAX(snapshot_at), NOW() - MAX(snapshot_at) FROM rest_ingest.market_book_snapshots;"

# Check logs
docker logs --tail 50 netbet-betfair-rest-client | grep -i error
```

### Impedance
```bash
# Check impedance data
docker exec netbet-postgres psql -U netbet -d netbet -c \
  "SELECT COUNT(*), COUNT(home_impedance) FROM rest_ingest.market_derived_metrics;"

# Test API (replace MARKET_ID)
curl "http://localhost:8000/events/MARKET_ID/timeseries?include_impedance=true" | jq '.[0] | {impedance, impedanceNorm}'
```

---

## Next Steps

1. Run diagnostic scripts on VPS
2. Review container logs for errors
3. Check database for latest snapshots
4. Verify API endpoint responses
5. Check frontend API calls for `include_impedance` parameter
