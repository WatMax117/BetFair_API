# Deploy: Debug events/markets endpoint fix (SSH)

Use this to deploy the backend-only fix for `GET /api/debug/events/{event_or_market_id}/markets` so the UI flow **League → Event → Market → Snapshot** no longer hits 404.

## On the server (via SSH)

Adjust `USER`, `SERVER_IP`, and `REPO_PATH` for your environment. Example:

```bash
ssh <user>@<server-ip>

cd <REPO_PATH>   # e.g. /opt/netbet or parent of risk-analytics-ui
git pull

# Rebuild and restart the API container
docker compose build risk-analytics-ui-api
docker compose up -d risk-analytics-ui-api
```

## Verify container

```bash
docker ps | grep risk-analytics-ui-api
```

## Optional quick test (on server)

The **public** path (browser, reverse proxy) is **`/api/debug/...`**. The API container serves at root, so when calling the container directly use **`/debug/...`**:

```bash
# Direct to API container (no /api prefix)
curl -i http://localhost:8000/debug/events/<known-event-id>/markets
```

When testing via the public site (e.g. Apache in front), use the same path as the UI:

```bash
# Via proxy (same path as browser: /api/debug/...)
curl -i http://localhost/api/debug/events/<known-event-id>/markets
```

### Proxy / routing sanity check

If the direct call works but the proxy call returns 404 or different behaviour:

- **Direct:** `http://localhost:8000/debug/events/1.253200629/markets` (or the API host/port on the server)
- **Via proxy:** `http://localhost/api/debug/events/1.253200629/markets` (or your public URL)

Compare status and `X-Lookup-Mode` header. They should be the same. If they differ, the proxy may be stripping the path, rewriting the ID, or routing to a different backend.

- Response **body**: array of market objects `[ { "event_id", "market_id", ... }, ... ]` (backward-compatible).
- Response **header**: `X-Lookup-Mode: event_id | market_id | fallback_single_market` for debugging.
- Server log: `debug: markets lookup via <mode> for id=...` (no payload logging).

## Acceptance (from browser)

1. Open the Risk Debug View.
2. Expand a league → select an event.
3. **Markets list should load (no 404)** — response is an array, no frontend changes needed.
4. Selecting a market should load the snapshot timeseries table.
5. Confirm lookup logic:
   - **DevTools → Network** → select the markets request → **Response Headers** → `X-Lookup-Mode`.
   - Server logs: line `debug: markets lookup via ... for id=...`.
