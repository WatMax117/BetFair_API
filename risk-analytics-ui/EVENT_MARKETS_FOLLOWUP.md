# Event → Markets drill-down: follow-up

## 1) Validate DB environment (required)

Before treating 404s as logic bugs, confirm the Risk Analytics API uses the same DB that has the ingested markets.

**On the DB used by the API**, run:

```sql
SELECT market_id, event_id
FROM market_event_metadata
WHERE market_id = '1.251575028'
   OR event_id = '1.251575028';
```

- **No rows** → 404 is expected: either that market was never ingested, or the API is pointing at a different DB/environment than the one the UI assumes. Report which case applies.
- **Rows returned** → the id exists; if the UI still 404s, check routing / request URL.

**How to run:**

- **Docker (Postgres in container):**  
  `docker exec -i netbet-postgres psql -U netbet -d netbet -c "SELECT market_id, event_id FROM market_event_metadata WHERE market_id = '1.251575028' OR event_id = '1.251575028';"`

- **Python (same env as API):**  
  `python risk-analytics-ui/scripts/validate_market_event_id.py 1.251575028`  
  (Set `POSTGRES_HOST`, `POSTGRES_DB`, etc. as for the API, or use `api/.env`.)

See also: `risk-analytics-ui/scripts/validate_market_event_id.sql` and `validate_market_event_id.py`.

---

## 2) UI behavior (implemented)

The Risk Debug View (post-apache) now:

- Uses **event_id** for the markets request when the event row has a non-null `event_id`:  
  `GET /api/debug/events/{event_id}/markets`
- Falls back to **market_id** when `event_id` is null or missing.

The backend is unchanged (event_id → market_id → fallback single market; array body; `X-Lookup-Mode` header; logging).

---

## 3) Backend: debug endpoint SQL aligned with validation query

The debug endpoint `GET /api/debug/events/{event_or_market_id}/markets` was updated so its lookup matches the validation query exactly.

**Validation query (known-good):**
```sql
SELECT market_id, event_id
FROM market_event_metadata
WHERE market_id = '1.253200629'
   OR event_id  = '1.253200629';
```

**Endpoint (same table, same WHERE):**
- Table: `market_event_metadata` only (no joins, no snapshot/status filters).
- WHERE: `e.market_id = %s OR e.event_id = %s` with the same parameter for both (path param as string).
- Identifier: path param is used as a **string**, stripped of whitespace; no numeric casting. If empty after strip → 404.
- After finding row(s), the endpoint resolves to `event_id` and returns all markets for that event (with match-odds first ordering).

So any id that returns a row from the validation query will now be found by the endpoint. 404 only if the id is missing from `market_event_metadata`.

**Proxy check:** If direct `http://<api-host>:8000/debug/events/1.253200629/markets` works but `http://localhost/api/debug/events/1.253200629/markets` does not, compare responses and `X-Lookup-Mode`; see `DEPLOY_DEBUG_MARKETS.md` for the sanity-check steps.

---

## 4) Optional: debug-only fallback (not implemented)

If you want the drill-down to work even when the id is missing from `market_event_metadata`, you could add a **debug-only** fallback in the API:

- When both **event_id** and **market_id** lookups return no rows, try resolving by **event_name + event_open_date** (e.g. `WHERE event_name = %s AND event_open_date::date = %s` with normalised name/date).
- Clearly mark this path as debug-only (e.g. different `X-Lookup-Mode` value like `fallback_by_name_date` and only enabled for `/debug/` routes).

Not required for the current fix.

---

## Outcome

After running the DB check and deploying the UI change:

- Event → Markets should not hit unexpected 404s when the id exists in the same DB the API uses.
- Any remaining 404s indicate missing data (or wrong environment), not an ID mismatch.
- The Risk Debug View stays consistent and predictable.
