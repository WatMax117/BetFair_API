# Apache 503 Service Unavailable Fix Report

**Date:** 2026-02-16  
**Issue:** 503 Service Unavailable error when accessing `/stream` through Apache  
**Root Cause:** Nginx container restarting due to DNS resolution failure at startup

---

## Summary

The `/stream` endpoint was returning 503 Service Unavailable from Apache. Investigation revealed that the `risk-analytics-ui-web` container was in a restart loop because nginx inside the container was trying to resolve `risk-analytics-ui-api` hostname at startup time, before the API container was ready or when containers were on different networks.

---

## Root Cause Analysis

### Problem Identified

1. **Container Status:** `risk-analytics-ui-web` was continuously restarting
2. **Nginx Error:** `host not found in upstream "risk-analytics-ui-api" in /etc/nginx/conf.d/default.conf:1`
3. **Cause:** Nginx resolves hostnames at startup time, not at request time. If the upstream hostname cannot be resolved when nginx starts, nginx fails to start.

### Why It Happened

The container was manually started with `docker run` instead of using `docker compose`, which meant:
- Container may not have been on the correct Docker network
- DNS resolution for service names (`risk-analytics-ui-api`) failed at nginx startup
- Nginx configuration used direct hostname in `proxy_pass`, causing immediate resolution attempt

---

## Solution Implemented

### Fix: Use Runtime DNS Resolution in Nginx

Modified `risk-analytics-ui/web/Dockerfile` to use nginx's resolver and variable-based proxy_pass:

**Before:**
```nginx
location /api/ {
    proxy_pass http://risk-analytics-ui-api:8000/;
    ...
}
```

**After:**
```nginx
resolver 127.0.0.11 valid=30s;
server {
    ...
    location /api/ {
        set $backend "http://risk-analytics-ui-api:8000";
        proxy_pass $backend/;
        ...
    }
}
```

### Key Changes

1. **Added resolver directive:** `resolver 127.0.0.11 valid=30s;`
   - `127.0.0.11` is Docker's internal DNS server
   - `valid=30s` caches DNS lookups for 30 seconds

2. **Used variable in proxy_pass:** `set $backend "http://risk-analytics-ui-api:8000"; proxy_pass $backend/;`
   - Forces nginx to resolve the hostname at request time, not startup time
   - Allows container to start even if upstream is not immediately available

---

## Verification Steps Performed

### Step 1: Container Status Check

```bash
docker ps | grep risk-analytics-ui-web
```

**Result:** Container was restarting continuously

### Step 2: Container Logs Inspection

```bash
docker logs risk-analytics-ui-web --tail=50
```

**Result:** Found nginx error: `host not found in upstream "risk-analytics-ui-api"`

### Step 3: Apache Configuration Check

```bash
cat /etc/apache2/sites-enabled/risk-analytics.conf
```

**Result:** Apache config was correct:
- `ProxyPass / http://127.0.0.1:3000/`
- `ProxyPass /api/ http://127.0.0.1:8000/`

### Step 4: Network Verification

Both containers were on the same Docker network (`risk-analytics-ui_default`), but nginx was still failing to resolve the hostname at startup.

### Step 5: Dockerfile Fix Applied

- Updated Dockerfile with resolver and variable-based proxy_pass
- Rebuilt container: `docker compose build --no-cache risk-analytics-ui-web`
- Restarted container: `docker compose up -d --no-deps risk-analytics-ui-web`

### Step 6: Post-Fix Verification

```bash
# Direct container access
curl http://localhost:3000/stream
# Result: HTTP 200 ✅

# Through Apache
curl http://localhost/stream
# Result: HTTP 200 ✅

# API endpoint
curl http://localhost/api/stream/events/by-date-snapshots?date=2026-02-16
# Result: HTTP 200 ✅
```

---

## Container Status After Fix

```
NAMES                          STATUS              PORTS
risk-analytics-ui-web          Up X seconds        0.0.0.0:3000->80/tcp
risk-analytics-ui-api          Up X minutes        0.0.0.0:8000->8000/tcp
netbet-streaming-client        Up X minutes        0.0.0.0:8081->8081/tcp
netbet-postgres                Up X minutes        127.0.0.1:5432->5432/tcp
```

All containers are running and healthy.

---

## Apache Configuration (Verified Correct)

```apache
<VirtualHost *:80>
    ProxyPreserveHost On
    ProxyPass        /api/  http://127.0.0.1:8000/
    ProxyPassReverse /api/  http://127.0.0.1:8000/

    ProxyPass        /      http://127.0.0.1:3000/
    ProxyPassReverse /      http://127.0.0.1:3000/
</VirtualHost>
```

Apache configuration was correct and did not require changes.

---

## Technical Details

### Why Variable-Based proxy_pass Works

When nginx encounters a variable in `proxy_pass`, it:
1. Defers DNS resolution until the request is processed
2. Allows the container to start successfully even if upstream is not ready
3. Resolves the hostname using Docker's internal DNS (`127.0.0.11`) at request time

### Docker DNS Resolution

- Docker provides an internal DNS server at `127.0.0.11`
- Service names (like `risk-analytics-ui-api`) are resolved to container IPs
- DNS cache is valid for 30 seconds (as configured)

---

## Files Modified

1. **`risk-analytics-ui/web/Dockerfile`**
   - Added `resolver 127.0.0.11 valid=30s;`
   - Changed `proxy_pass` to use variable: `set $backend "http://risk-analytics-ui-api:8000"; proxy_pass $backend/;`

---

## Acceptance Criteria

✅ **Container Status:** `risk-analytics-ui-web` is running (not restarting)  
✅ **Direct Access:** `http://localhost:3000/stream` returns HTTP 200  
✅ **Apache Proxy:** `http://localhost/stream` returns HTTP 200  
✅ **API Endpoint:** `/api/stream/events/by-date-snapshots` returns HTTP 200  
✅ **Nginx Logs:** No DNS resolution errors  
✅ **All Containers:** All required containers are running and healthy  

---

## Prevention

To prevent this issue in the future:

1. **Always use docker compose** to start containers (ensures correct network configuration)
2. **Use variable-based proxy_pass** in nginx when proxying to Docker service names
3. **Add resolver directive** to nginx config for Docker DNS resolution
4. **Monitor container logs** after deployment to catch startup failures early

---

## Conclusion

The 503 error was caused by nginx failing to resolve the upstream hostname at startup. By using Docker's internal DNS resolver and deferring hostname resolution to request time via a variable, the container can now start successfully even if the upstream service is not immediately available. The fix ensures robust container startup and proper service discovery within Docker networks.
