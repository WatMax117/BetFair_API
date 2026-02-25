# Impedance Rendering Diagnostic Guide

## Issue
The third-level index (Impedance) visualization is not displayed in the event detail page.

## Frontend Checks (Browser DevTools)

### 1. Verify "Include Impedance" checkbox is checked
- Open an event detail page
- Look for the "Include Impedance" checkbox in the controls
- **It must be checked** for impedance to be fetched and displayed

### 2. Check Network request
- Open DevTools → Network
- Filter for `/api/events/{market_id}/timeseries`
- Click on the request
- Check **Request URL**: should include `include_impedance=true`
- Check **Response**: should contain `impedanceNorm` objects

Example response should look like:
```json
[
  {
    "snapshot_at": "2026-02-07T10:00:00Z",
    "home_risk": 123.45,
    "impedanceNorm": {
      "home": 0.85,
      "away": -0.23,
      "draw": 0.12
    }
  }
]
```

### 3. Check Console for errors
- Open DevTools → Console
- Look for:
  - Errors related to `impedanceNorm`
  - Chart rendering errors (Recharts/LineChart)
  - Type errors (e.g., `Cannot read property 'home' of undefined`)

### 4. Check React state
Add temporary logging in browser console:
```javascript
// In browser console, after page loads:
// Check if timeseries has impedance data
// (This requires React DevTools or adding console.log in code)
```

## Backend Checks (VPS)

### 1. Run diagnostic script
```bash
bash scripts/diagnose_impedance_rendering.sh
```

### 2. Manual API test
```bash
# Get a market_id
MARKET_ID=$(docker exec netbet-postgres psql -U netbet -d netbet -t -c "
SELECT market_id FROM rest_ingest.market_book_snapshots 
WHERE snapshot_at > NOW() - INTERVAL '24 hours' LIMIT 1;" | tr -d ' ')

# Test API endpoint
curl "http://127.0.0.1:8000/events/${MARKET_ID}/timeseries?include_impedance=true&interval_minutes=15" | jq '.[0] | {impedanceNorm, impedance}'
```

### 3. Check database
```bash
docker exec netbet-postgres psql -U netbet -d netbet -c "
SELECT 
    market_id,
    snapshot_at,
    home_impedance_norm,
    away_impedance_norm,
    draw_impedance_norm
FROM public.market_derived_metrics
WHERE snapshot_at > NOW() - INTERVAL '24 hours'
  AND (home_impedance_norm IS NOT NULL OR away_impedance_norm IS NOT NULL)
LIMIT 5;
"
```

## Common Issues

### Issue A: Checkbox not checked
**Symptom:** No impedance data in Network response  
**Fix:** Check the "Include Impedance" checkbox in the UI

### Issue B: API not returning impedanceNorm
**Symptom:** API response has no `impedanceNorm` field even with `include_impedance=true`  
**Possible causes:**
- Database has no impedance data (rest-client not computing it)
- API query not including impedance columns
- Impedance columns missing from `market_derived_metrics` table

**Fix:**
1. Verify rest-client is running and computing impedance
2. Check if `market_derived_metrics` has impedance columns
3. Run backfill if needed: `scripts/vps_backfill_impedance_and_validate.sh`

### Issue C: Frontend receives data but doesn't render
**Symptom:** Network shows `impedanceNorm` in response, but no chart appears  
**Possible causes:**
- `hasImpedance` check failing (all values are null)
- Chart component error (check console)
- Conditional render logic issue

**Fix:**
1. Check browser console for errors
2. Verify `hasImpedance` logic in `EventDetail.tsx` line 232
3. Check if `chartData` includes `home_impedance_norm` etc.

## Code Reference

**Frontend:** `risk-analytics-ui/web/src/components/EventDetail.tsx`
- Line 179: `includeImpedance` state (default: `false`)
- Line 196: `fetchEventTimeseries(..., includeImpedance)`
- Line 232: `hasImpedance` check
- Line 428: Conditional render: `{includeImpedance && hasImpedance && (...)}`

**Backend:** `risk-analytics-ui/api/app/main.py`
- Line 435: `/events/{market_id}/timeseries` endpoint
- Line 436: `include_impedance` query param
- Line 522: Impedance data extraction
