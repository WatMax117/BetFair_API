# Stream UI Diagnostics Runbook

Use this to collect the findings requested for the /stream deployment (no events, no data/charts).

---

## 1. Verify API routing (browser DevTools)

1. Open the **/stream** UI in the browser (e.g. `https://<host>/stream`).
2. Open **DevTools → Network**.
3. Reload or pick a date and confirm:
   - All relevant requests go to **`/api/stream/...`** (not `/api/...`).
4. Check these requests and note **status code** and **response** (empty array vs error body):

| Request | Expected path | Report |
|--------|----------------|--------|
| Events for date | `GET /api/stream/events/by-date-snapshots?date=YYYY-MM-DD` | Status ___, Response (length/empty/error) ___ |
| Event meta | `GET /api/stream/events/<market_id>/meta` | Status ___, Response ___ |
| Timeseries | `GET /api/stream/events/<market_id>/timeseries?from_ts=...&to_ts=...&interval_minutes=15` | Status ___, Response ___ |

**Report:** Status codes for each; whether responses are empty arrays `[]` or error JSON.

---

## 2. Streaming data freshness (DB)

Run (e.g. `psql -U netbet -d netbet -f scripts/diagnose_stream_ui.sql` or paste in a client):

```sql
SELECT max(publish_time) AS last_publish_time
FROM stream_ingest.ladder_levels;

SELECT count(*) AS rows_last_60m
FROM stream_ingest.ladder_levels
WHERE publish_time > now() - interval '60 minutes';
```

**Report:**
- **last_publish_time:** ___
- **rows_last_60m:** ___

If `last_publish_time` is old or `rows_last_60m` is 0, streaming ingestion may not be active.

---

## 3. Staleness filter (STALE_MINUTES)

- **Change applied:** `STALE_MINUTES` in `api/app/stream_data.py` has been set to **120** (from 20).
- **Action:** Restart the Risk Analytics API backend so the new value is loaded.
- **Check:** Reload the /stream UI and see if events and event-detail data/charts appear.

**Report:** Did increasing `STALE_MINUTES` to 120 restore visibility? Yes / No ___

---

## 4. Metadata join (DB)

Run:

```sql
SELECT ll.market_id
FROM (
  SELECT DISTINCT market_id
  FROM stream_ingest.ladder_levels
  WHERE publish_time > now() - interval '6 hours'
) ll
LEFT JOIN public.market_event_metadata m ON m.market_id = ll.market_id
WHERE m.market_id IS NULL
LIMIT 20;
```

**Report:**
- If **no rows:** all ladder markets in the last 6h have metadata (join is not filtering them out).
- If **rows returned:** list the `market_id` values; these markets are dropped by the metadata join and need metadata populated (or join logic adjusted).

---

## 5. Timezone consistency (DB)

Run:

```sql
SELECT
  now() AS server_time,
  now() AT TIME ZONE 'utc' AS utc_time,
  max(publish_time) AS last_publish_time
FROM stream_ingest.ladder_levels;
```

**Report:** Confirm whether `publish_time` is in UTC and aligns with your UTC bucket expectations (e.g. server and UTC times match your environment).

---

## 6. Backend logs

After reproducing the issue (e.g. open /stream, pick a date, open an event):

- Check backend (Risk Analytics API) logs for any **errors** or **tracebacks** when:
  - `GET /stream/events/by-date-snapshots`
  - `GET /stream/events/<id>/timeseries`
  - `GET /stream/events/<id>/meta`
  are called.

**Report:** Any relevant error lines or stack traces.

---

## Optional: run Python diagnostic script

From `risk-analytics-ui` (with DB env vars set and API running if you want HTTP checks):

```bash
# DB only
PYTHONPATH=api python scripts/diagnose_stream_ui.py

# DB + API status codes (replace with your API base URL)
PYTHONPATH=api python scripts/diagnose_stream_ui.py --api-base http://localhost:8000
```

Or run only the SQL file:

```bash
psql -U netbet -d netbet -f scripts/diagnose_stream_ui.sql
```

---

Once you have:

1. API status results (and whether responses are empty/errors)  
2. DB freshness (last_publish_time, rows_last_60m)  
3. Outcome after STALE_MINUTES=120 and backend restart  
4. Metadata join result (any market_ids without metadata)  
5. Timezone query result  
6. Any backend errors  

you can isolate the root cause (e.g. no stream data, staleness too strict, metadata missing, or API/routing issue).
