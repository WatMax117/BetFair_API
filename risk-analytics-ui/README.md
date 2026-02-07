# Risk Analytics Web UI

MVP web interface for the Risk Analytics team: **3-layer navigation** (Leagues → Events → Event detail with 15‑min history charts). Read-only access to the existing PostgreSQL 3-layer schema (metadata, raw snapshots, derived metrics).

## Stack

- **Backend:** Python FastAPI (read-only DB)
- **Frontend:** React + TypeScript, Material UI, Recharts
- **DB:** PostgreSQL (existing `market_event_metadata`, `market_book_snapshots`, `market_derived_metrics`)

## How to run

### With main stack (recommended)

From the **repo root** (NetBet):

```bash
docker compose up -d
```

This starts Postgres, auth, streaming client, rest client, **risk-analytics-ui-api** (port 8000), and **risk-analytics-ui-web** (port 3000).

- **Web UI:** http://localhost:3000  
- **API:** http://localhost:8000 (e.g. http://localhost:8000/health — API routes are at `/health`, `/leagues`, etc.; the UI and Apache proxy use `/api/*` which is stripped to these paths)

### Standalone (API + Web only)

If Postgres is already running (e.g. on the host or another compose):

```bash
cd risk-analytics-ui
POSTGRES_HOST=host.docker.internal POSTGRES_PASSWORD=netbet docker compose up -d
```

Then open http://localhost:3000 (ensure the web container proxies `/api` to the API container; see `web/Dockerfile`).

### Local dev (no Docker)

**API:**

```bash
cd risk-analytics-ui/api
pip install -r requirements.txt
export POSTGRES_HOST=localhost POSTGRES_PORT=5432 POSTGRES_DB=netbet POSTGRES_USER=netbet POSTGRES_PASSWORD=...
uvicorn app.main:app --reload --port 8000
```

**Web:**

```bash
cd risk-analytics-ui/web
npm install
npm run dev
```

Vite proxies `/api` to `http://localhost:8000`. Open http://localhost:3000.

## VPS: Rebuild and redeploy

When you change files or config on the repo, use these rules on the VPS (e.g. in `/opt/netbet` with the Risk Analytics services in the same compose).

### 1. Application source code changed (UI/TS/React, API code)

Examples: `EventDetail.tsx`, API handlers, anything under `risk-analytics-ui/web` or `risk-analytics-ui/api`.

**Rebuild the image(s) and recreate the container(s):**

```bash
# UI
docker compose build risk-analytics-ui-web
docker compose up -d --no-deps risk-analytics-ui-web

# API
docker compose build risk-analytics-ui-api
docker compose up -d --no-deps risk-analytics-ui-api
```

### 2. Only environment variables changed in docker-compose.yml

Examples: `POSTGRES_HOST`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`.

No image rebuild; recreate the container so it picks up the new env:

```bash
docker compose up -d --no-deps --force-recreate risk-analytics-ui-api
```

### 3. Only Apache reverse-proxy config changed

No Docker changes; reload Apache:

```bash
sudo systemctl reload apache2
```

### Recommended workflow after code/config fixes

1. **Commit and push** fixes to the repo.
2. **On the VPS:**
   ```bash
   git pull
   docker compose build risk-analytics-ui-api risk-analytics-ui-web
   docker compose up -d --no-deps risk-analytics-ui-api risk-analytics-ui-web
   ```

Commit TypeScript/source fixes so they are not lost on the next clean build.

### If the UI still shows `/api/api/*` 404s after redeploy

1. **On the VPS, confirm the source has the fix** (no extra `/api` in paths):
   ```bash
   cd /opt/netbet
   git log -1 --oneline risk-analytics-ui/web/src/api.ts
   grep -n 'API_BASE.*leagues' risk-analytics-ui/web/src/api.ts
   ```
   You should see `${API_BASE}/leagues` (not `${API_BASE}/api/leagues`). If you still see `/api/leagues` in the grep, run `git pull` and ensure you're on `master` with the latest commit.

2. **Rebuild the UI image from that directory (no cache)** and recreate the container:
   ```bash
   docker compose build --no-cache risk-analytics-ui-web
   docker compose up -d --no-deps risk-analytics-ui-web
   ```

3. **In the browser:** Hard refresh so the new JS is loaded (e.g. Ctrl+Shift+R or DevTools → Network → "Disable cache" then refresh). The old bundle (`index-Bj5rbbWR.js`) is cached; the new build will have a different hash.

---

## Env vars (API / backend)

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_HOST` | `localhost` | DB host |
| `POSTGRES_PORT` | `5432` | DB port |
| `POSTGRES_DB` | `netbet` | DB name |
| `POSTGRES_USER` | `netbet` | DB user |
| `POSTGRES_PASSWORD` | (none) | DB password (required for real DB) |

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/leagues` | List leagues (competition_name) with event counts. Query: `from_ts`, `to_ts` (UTC ISO), `q` (optional search) |
| GET | `/leagues/{league}/events` | Events in league with latest snapshot (odds, index, total_volume). Query: `from_ts`, `to_ts` |
| GET | `/events/{market_id}/meta` | Event metadata for detail header |
| GET | `/events/{market_id}/timeseries` | 15‑min downsampled time series. Query: `from_ts`, `to_ts`, `interval_minutes` (default 15) |
| GET | `/events/{market_id}/latest_raw` | Latest raw marketBook JSON (raw_payload) for the market. Read-only. |

When using the UI or Apache, requests go to `/api/*` and are proxied to these paths (prefix stripped).

Leagues and events endpoints also accept: `include_in_play` (default true), `in_play_lookback_hours` (default 6).

**DB index (optional):** For growth, ensure `(market_id, snapshot_at DESC)` exists on `market_derived_metrics`. From repo root: `psql -U netbet -d netbet -f betfair-rest-client/scripts/ensure_mdm_index_desc.sql`

## How Risk Analytics should use this UI

- **Liquidity Imbalance Index** (Home / Away / Draw) is a microstructure signal: it compares liability on the selection’s back side vs stakes on the other selections (from order book depth). It is **not** a probability or “value” metric; use it for liquidity and order-flow context. Positive/negative values indicate direction of imbalance; magnitude is in currency units.
- **total_volume** is **market-level** `totalMatched` from the market book (total matched on the whole market). It is **not** per-runner matched volume. Use it for overall market activity.
- **Per-runner matched volume** (e.g. runner-level `totalMatched`) may be **unavailable or zero** when using the REST API; the exchange often does not expose it in listMarketBook for all markets. Do not rely on it for analysis; treat total_volume as the only volume metric from this pipeline.

## UI overview

1. **Layer 0 — Leagues:** Accordion of leagues; time window (default 24h); **Include in-play events** toggle (default ON) with in-play lookback hours; **Index highlight threshold** (default 500); search; refresh.
2. **Layer 1 — Events:** Per league, table of events with start time, name, best back odds (H/A/D), liquidity index (H/A/D), total volume, last update; sort by start time; highlight rows where any index exceeds the threshold; info icon with tooltip for depth_limit and calculation_version.
3. **Layer 2 — Event detail:** Header (league, event, market_id); **Copy market_id** and **View latest raw snapshot (JSON)** buttons; current odds (back/lay), **spreads** (lay − back), index, volume; time range 6h / 24h / 72h; Chart A (best back odds), Chart B (index), Chart C (total_volume); **Last 10 snapshots** table (copy-friendly); data notes (depth_limit, calculation_version, snapshot interval).

No auth/roles in this MVP.
