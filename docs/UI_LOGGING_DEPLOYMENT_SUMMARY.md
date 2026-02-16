# UI Logging Deployment Summary

**Date:** 2026-02-16  
**Status:** Logging code added, deployment in progress

---

## Summary

Added comprehensive logging to all API fetch functions to diagnose why the UI shows stale data while the API returns fresh data. The logging will help identify:

1. Which endpoints are being called for list vs detail
2. What parameters are being used (date, market_id, etc.)
3. What responses are being received
4. Whether there are any filtering or caching issues

---

## Logging Added

### List Request (`fetchEventsByDateSnapshots`)
- Request URL, API base, date parameter
- Response status, body length, preview
- Parsed data structure (isArray, length, sample keys)

### Detail Requests

#### `fetchEventMeta`
- Request URL, marketId
- Response status, body preview
- Parsed meta data

#### `fetchEventTimeseries`
- Request URL, marketId, from/to dates, interval
- Response status, body preview
- Parsed timeseries data (length, first/last items)

#### `fetchMarketSnapshots`
- Request URL, marketId, from/to dates, limit
- Response status, body preview
- Parsed snapshots data (length, first item)

#### `fetchEventLatestRaw`
- Request URL, marketId
- Response status, body preview
- Parsed raw payload info

### Component Logging

#### `LeaguesAccordion`
- Date selection changes
- Event selection (market_id, event_id, event_name)
- Data received and set

#### `EventDetail`
- MarketId when component loads
- Meta, timeseries, and snapshots loading
- Data received for each fetch

---

## Files Modified

1. `risk-analytics-ui/web/src/api.ts`
   - Added logging to all fetch functions
   - Logs request URLs, parameters, response status, and parsed data

2. `risk-analytics-ui/web/src/components/EventDetail.tsx`
   - Added logging to useEffect hooks and callbacks
   - Logs marketId, dates, and received data

3. `risk-analytics-ui/web/src/components/LeaguesAccordion.tsx`
   - Added logging to event selection handler
   - Logs selected event details

---

## Deployment Status

- ✅ Logging code written
- ⚠️ TypeScript compilation errors (type annotations needed)
- ⏳ Build and deployment pending

---

## Next Steps

1. Fix TypeScript errors (add type annotations to callback parameters)
2. Rebuild container
3. Restart web container
4. Test in browser and review console logs
5. Identify root cause based on logged requests/responses

---

## Expected Console Output

When accessing `/stream` and selecting an event, the console should show:

```
[api] fetchEventsByDateSnapshots request { apiBase: '/api/stream', date: '2026-02-16', url: '...' }
[api] fetchEventsByDateSnapshots response { status: 200, bodyLength: ..., bodyPreview: '...' }
[api] fetchEventsByDateSnapshots parsed { isArray: true, length: ..., firstItem: [...] }
[LeaguesAccordion] load called { selectedDate: '2026-02-16' }
[LeaguesAccordion] data received { isArray: true, length: ..., sample: {...} }
[LeaguesAccordion] Event selected { market_id: '...', event_id: '...', event_name: '...', selectedDate: '2026-02-16' }
[EventDetail] Loading meta for marketId { marketId: '...' }
[api] fetchEventMeta request { apiBase: '/api/stream', marketId: '...', url: '...' }
[api] fetchEventMeta response { status: 200, bodyLength: ..., bodyPreview: '...' }
[EventDetail] Loading timeseries { marketId: '...', from: '...', to: '...' }
[api] fetchEventTimeseries request { apiBase: '/api/stream', marketId: '...', from: '...', to: '...', url: '...' }
[api] fetchEventTimeseries response { status: 200, bodyLength: ..., bodyPreview: '...' }
[EventDetail] Loading snapshots { marketId: '...', from: '...', to: '...' }
[api] fetchMarketSnapshots request { apiBase: '/api/stream', marketId: '...', from: '...', to: '...', url: '...' }
[api] fetchMarketSnapshots response { status: 200, bodyLength: ..., bodyPreview: '...' }
```

This will reveal:
- Exact URLs being called
- Parameters used (especially date and market_id)
- Response sizes and content
- Whether data is being filtered or cached
