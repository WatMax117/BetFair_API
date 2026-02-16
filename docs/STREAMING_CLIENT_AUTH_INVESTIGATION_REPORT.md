# Streaming Client Authentication Failure - Root Cause Analysis Report

**Date:** 2026-02-16  
**Issue:** Streaming client container restarting due to database authentication failure  
**Status:** ✅ **RESOLVED**

---

## Executive Summary

The streaming client was failing to authenticate to PostgreSQL because **the database role `netbet_stream_writer` did not exist**. The password configuration was correct, but the role itself was missing from the database.

**Root Cause:** Missing database role `netbet_stream_writer`  
**Resolution:** Created the role with appropriate privileges  
**Impact:** Streaming client can now authenticate and connect to the database

---

## Step 1 — Effective Runtime Configuration

### Container Environment Variables (from `docker inspect`)

```
SPRING_DATASOURCE_URL=jdbc:postgresql://netbet-postgres:5432/netbet?currentSchema=stream_ingest
SPRING_DATASOURCE_USERNAME=netbet_stream_writer (from POSTGRES_STREAM_WRITER_USER)
SPRING_DATASOURCE_PASSWORD=STREAM_WRITER_117 (from POSTGRES_STREAM_WRITER_PASSWORD)
```

**Findings:**
- ✅ Hostname: `netbet-postgres` (correct)
- ✅ Database: `netbet` (correct)
- ✅ Schema: `stream_ingest` (correct via `currentSchema` parameter)
- ✅ Password: `STREAM_WRITER_117` (present in environment)
- ❌ **Role: `netbet_stream_writer` did not exist in database**

### Docker Compose Configuration

From `docker compose config`:
- `env_file`: `./.env` and `./auth-service/.env` (both files exist)
- `POSTGRES_STREAM_WRITER_PASSWORD`: `STREAM_WRITER_117` (resolved correctly)
- `POSTGRES_STREAM_WRITER_USER`: `netbet_stream_writer` (resolved correctly)

---

## Step 2 — Database Role Verification

### Role Existence Check

```sql
SELECT rolname FROM pg_roles WHERE rolname = 'netbet_stream_writer';
-- Result: (0 rows) ❌ ROLE DID NOT EXIST
```

### Existing Roles

Found these roles in the database:
- `netbet` (main user)
- `netbet_analytics_reader`
- `netbet_rest_writer` ✅ (exists)
- `netbet_stream_writer` ❌ (missing)

**Finding:** The `netbet_stream_writer` role was never created, while `netbet_rest_writer` exists.

---

## Step 3 — Password Source Identification

### Environment Files

1. **`/opt/netbet/.env`** (exists, 1528 bytes, modified Feb 16 10:04)
   ```
   POSTGRES_STREAM_WRITER_USER=netbet_stream_writer
   POSTGRES_STREAM_WRITER_PASSWORD=STREAM_WRITER_117
   POSTGRES_DB=netbet
   ```

2. **`/opt/netbet/auth-service/.env`** (exists, 775 bytes, modified Feb 15 09:05)
   - Does not contain `POSTGRES_STREAM_WRITER_*` variables

**Finding:** Password is correctly defined in `/opt/netbet/.env` and is being read by docker-compose.

---

## Step 4 — Database Instance Verification

### Postgres Containers

```bash
docker ps | grep postgres
```

**Result:**
- ✅ Only one Postgres container: `netbet-postgres` (postgres:16-alpine)
- ✅ Status: Up 10 days (healthy)
- ✅ No external Postgres hosts referenced

**Finding:** Single database instance confirmed. No configuration drift.

---

## Step 5 — Error Analysis

### Log Error Pattern

```
Caused by: org.postgresql.util.PSQLException: FATAL: password authentication failed for user "netbet_stream_writer"
```

**Initial Hypothesis:** Password mismatch  
**Actual Root Cause:** Role does not exist (PostgreSQL returns "password authentication failed" even when the role is missing)

---

## Resolution

### Action Taken

Created the missing database role with appropriate privileges:

```sql
CREATE ROLE netbet_stream_writer LOGIN PASSWORD 'STREAM_WRITER_117';
GRANT USAGE ON SCHEMA stream_ingest TO netbet_stream_writer;
GRANT INSERT, SELECT, UPDATE ON ALL TABLES IN SCHEMA stream_ingest TO netbet_stream_writer;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO netbet_stream_writer;
ALTER DEFAULT PRIVILEGES IN SCHEMA stream_ingest GRANT INSERT, SELECT, UPDATE ON TABLES TO netbet_stream_writer;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE ON TABLES TO netbet_stream_writer;
```

**Script:** `scripts/create_netbet_stream_writer_role.sql`

### Verification

After role creation:
```sql
SELECT rolname, rolcanlogin FROM pg_roles WHERE rolname = 'netbet_stream_writer';
-- Result: netbet_stream_writer | t ✅
```

---

## Post-Resolution Verification

### Container Status

After restarting the streaming client:
- ✅ **Authentication resolved:** No more password authentication errors
- ⚠️ **New issue:** Flyway baseline required (schema exists but no history table)

### Current Status

**Authentication:** ✅ **RESOLVED** - Role created, password works  
**Flyway:** ⚠️ **NEEDS CONFIGURATION** - `stream_ingest` schema exists but Flyway history table missing

**Error after authentication fix:**
```
Found non-empty schema(s) "stream_ingest" but no schema history table. 
Use baseline() or set baselineOnMigrate to true to initialize the schema history table.
```

### Next Steps

1. ✅ **Authentication:** RESOLVED - Role created successfully
2. ⏳ **Flyway:** Configure `spring.flyway.baseline-on-migrate=true` or run Flyway baseline
3. ⏳ Verify streaming client starts completely
4. ⏳ Confirm writes go to `stream_ingest.ladder_levels` (schema-qualified SQL fix)
5. ⏳ Apply DB lock-down script (`scripts/lockdown_public_ladder_levels.sql`)
6. ⏳ Verify streaming data appears in UI

---

## Lessons Learned

1. **PostgreSQL error messages can be misleading:** "password authentication failed" can occur when the role doesn't exist, not just when the password is wrong.

2. **Role provisioning:** Database roles should be created as part of initial setup or migration scripts, not assumed to exist.

3. **Configuration vs. Database State:** Even when environment variables are correct, the database state (roles, permissions) must match.

---

## Files Created

- `scripts/create_netbet_stream_writer_role.sql` - Role creation script
- `docs/STREAMING_CLIENT_AUTH_INVESTIGATION_REPORT.md` - This report

---

## Conclusion

**Root Cause:** Missing database role `netbet_stream_writer`  
**Resolution:** Role created with password `STREAM_WRITER_117` and appropriate privileges  
**Status:** ✅ **AUTHENTICATION RESOLVED** - Streaming client can now authenticate

**Remaining Issue:** Flyway requires baseline configuration for existing `stream_ingest` schema. This is a separate configuration issue, not an authentication problem.
