# Initial Diagnosis: 500 Internal Server Error — by-date-snapshots

**Endpoint:** `GET /api/stream/events/by-date-snapshots?date=YYYY-MM-DD`  
**Date:** 2026-02-16  
**Status:** Root cause identified (DB connectivity; no application bug).

---

## Step 1 — Full stack trace (captured)

```
INFO:     172.18.0.1:41064 - "GET /stream/events/by-date-snapshots?date=2026-02-16 HTTP/1.1" 500 Internal Server Error
ERROR:    Exception in ASGI application
Traceback (most recent call last):
  File "/usr/local/lib/python3.11/site-packages/uvicorn/protocols/http/httptools_impl.py", line 416, in run_asgi
    result = await app(  # type: ignore[func-returns-value]
  File "/usr/local/lib/python3.11/site-packages/uvicorn/middleware/proxy_headers.py", line 60, in __call__
    return await self.app(scope, receive, send)
  File "/usr/local/lib/python3.11/site-packages/fastapi/applications.py", line 1134, in __call__
    await super().__call__(scope, receive, send)
  File "/usr/local/lib/python3.11/site-packages/starlette/applications.py", line 107, in __call__
    await self.app(scope, receive, send)
  File "/usr/local/lib/python3.11/site-packages/starlette/middleware/errors.py", line 186, in __call__
    raise exc
  File "/usr/local/lib/python3.11/site-packages/starlette/middleware/errors.py", line 164, in __call__
    await self.app(scope, receive, _send)
  File "/usr/local/lib/python3.11/site-packages/starlette/middleware/cors.py", line 87, in __call__
    return await self.app(scope, receive, send)
  File "/usr/local/lib/python3.11/site-packages/starlette/middleware/gzip.py", line 29, in __call__
    await responder(scope, receive, send)
  File "/usr/local/lib/python3.11/site-packages/starlette/middleware/gzip.py", line 46, in __call__
    return await self.app(scope, receive, self.send_with_compression)
  File "/usr/local/lib/python3.11/site-packages/starlette/middleware/exceptions.py", line 63, in __call__
    await await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)
  File "/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py", line 53, in wrapped_app
    raise exc
  File "/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py", line 42, in wrapped_app
    await app(scope, receive, sender)
  File "/usr/local/lib/python3.11/site-packages/fastapi/middleware/asyncexitstack.py", line 18, in __call__
    await self.app(scope, receive, send)
  File "/usr/local/lib/python3.11/site-packages/starlette/routing.py", line 716, in __call__
    await self.middleware_stack(scope, receive, send)
  File "/usr/local/lib/python3.11/site-packages/starlette/routing.py", line 736, in app
    await await route.handle(scope, receive, send)
  File "/usr/local/lib/python3.11/site-packages/starlette/routing.py", line 290, in handle
    await self.app(scope, receive, send)
  File "/usr/local/lib/python3.11/site-packages/fastapi/routing.py", line 119, in app
    response = await wrap_app_handling_exceptions(app, request)(scope, receive, send)
  File "/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py", line 53, in wrapped_app
    raise exc
  File "/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py", line 42, in wrapped_app
    await app(scope, receive, sender)
  File "/usr/local/lib/python3.11/site-packages/fastapi/routing.py", line 105, in app
    response = await f(request)
  File "/usr/local/lib/python3.11/site-packages/fastapi/routing.py", line 424, in app
    raw_response = await run_endpoint_function(
  File "/usr/local/lib/python3.11/site-packages/fastapi/routing.py", line 314, in run_endpoint_function
    return await run_in_threadpool(dependant.call, **values)
  File "/usr/local/lib/python3.11/site-packages/starlette/concurrency.py", line 32, in run_in_threadpool
    return await anyio.to_thread.run_sync(func)
  File "/usr/local/lib/python3.11/site-packages/anyio/to_thread.py", line 63, in run_sync
    return await get_async_backend().run_sync_in_worker_thread(
  File "/usr/local/lib/python3.11/site-packages/anyio/_backends/_asyncio.py", line 2502, in run_sync_in_worker_thread
    return await future
  File "/usr/local/lib/python3.11/site-packages/anyio/_backends/_asyncio.py", line 986, in run
    result = context.run(func, *args)
  File "/app/app/stream_router.py", line 34, in stream_events_by_date_snapshots
    events = get_events_by_date_snapshots_stream(date)
  File "/app/app/stream_data.py", line 448, in get_events_by_date_snapshots_stream
    with cursor() as cur:
  File "/usr/local/lib/python3.11/contextlib.py", line 137, in __enter__
    return next(self.gen)
  File "/app/app/db.py", line 27, in cursor
    conn = psycopg2.connect(**get_conn_kwargs(), cursor_factory=RealDictCursor)
  File "/usr/local/lib/python3.11/site-packages/psycopg2/__init__.py", line 122, in connect
    conn = _connect(dsn, connection_factory=connection_factory, **kwasync)
psycopg2.OperationalError: could not translate host name "postgres" to address: Temporary failure in name resolution
```

---

## Step 2 — Endpoint and failing function

- **Handler:** `stream_router.py` line 34 → `stream_events_by_date_snapshots(date)`  
- **Called function:** `get_events_by_date_snapshots_stream(date)` in `stream_data.py`  
- **Failing line:** `stream_data.py` **line 448**: `with cursor() as cur:`  
- **Context:** First use of the DB in `get_events_by_date_snapshots_stream()` (before any stream_markets query runs).

So the failing request is the by-date-snapshots endpoint, and the failure is at the very first database connection in `get_events_by_date_snapshots_stream()`.

---

## Step 3 — Failure type

- **Exception type:** `psycopg2.OperationalError` (database / connectivity).  
- **Message:** `could not translate host name "postgres" to address: Temporary failure in name resolution`

This is **not**:

- `TypeError` (e.g. None handling)  
- `KeyError` (missing dict field)  
- `ZeroDivisionError`  
- `AttributeError`  
- `ValueError`  

It is a **database connectivity** error: the API container cannot resolve the hostname `"postgres"` to an IP address.

---

## Step 4 — Impedance / median / None handling

- The traceback never reaches:
  - `compute_impedance_index_from_medians()`
  - `compute_book_risk_from_medians()`
  - Any median calculation or bucket loop.
- Failure occurs at the **first** `with cursor() as cur:` in `get_events_by_date_snapshots_stream()` (line 448), before any business logic runs.
- So the 500 is **not** caused by:
  - Accessing fields on a `None` return from impedance/book_risk.
  - Division by zero in impedance.
  - Missing guards on median values.

No code change is required in `stream_data.py` for impedance/median/None handling to fix this 500.

---

## Step 5 — DB connectivity

- **API container env (relevant):**
  - `POSTGRES_HOST=postgres`
  - `POSTGRES_PORT=5432`
  - `POSTGRES_DB=netbet`
  - `POSTGRES_USER=netbet_analytics_reader`
  - `POSTGRES_PASSWORD=` (empty in captured env)
- **Ping from API container:** `ping` is not available in the API image; not run.
- **Logs:** Show exactly the error above: `could not translate host name "postgres" to address: Temporary failure in name resolution`. No “connection refused” or “authentication failed” in the captured traceback; the failure is at **name resolution**.

**Conclusion:** The 500 is caused by the API container being unable to resolve the hostname `"postgres"`. Common causes:

- The API is run with `risk-analytics-ui/docker-compose.yml` only, which does not define a `postgres` service and does not join an external network where a Postgres container is reachable.
- The real Postgres container may be named differently (e.g. `netbet-postgres`) and/or on another compose stack/network.

Fixing this requires environment/network configuration (e.g. set `POSTGRES_HOST` to the resolvable DB host/service name and ensure the API is on the same Docker network as Postgres). No application code change is needed for this specific 500.

---

## Step 6 — Report summary

| Item | Value |
|------|--------|
| **Full traceback** | Above (unchanged). |
| **Exception type** | `psycopg2.OperationalError` |
| **File** | `stream_data.py` (entry at line 448); underlying connect in `db.py` line 27. |
| **Occurs inside** | **DB query section** — specifically the **first** acquisition of a DB connection in `get_events_by_date_snapshots_stream()`. Not inside impedance computation, book risk computation, or median calculation. |
| **Root cause** | Hostname `"postgres"` cannot be resolved inside the API container (DNS/network configuration). |
| **Next step** | Set `POSTGRES_HOST` (and optionally network) so the API can reach the actual Postgres service (e.g. `netbet-postgres` if that is the container name). No code fix required for this 500. |

---

Once `POSTGRES_HOST` and the API’s network are fixed so the API can connect to Postgres, the same endpoint and code path can be re-tested; any subsequent failure would be a new, separate issue.
