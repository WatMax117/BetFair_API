# Risk Debug View

Read-only debug inspector for existing 15-minute snapshots (rest-client tables). No new index logic, no ingestion changes, no streaming integration.

## Location

`<project-root>/post-apache/`

## Data Loading (lazy)

- **Leagues** — on Search click (window hours, optional search term)
- **Events** — when a league is expanded
- **Markets** — when an event is selected (Match Odds preferred)
- **Timeseries table** — when a market is selected: one row per snapshot (chronological), columns auto-generated from all scalar DB fields (excludes `snapshot_id`, `raw_payload`, and non-scalar values). Sticky header and first column; optional show/hide columns.
- **raw_payload** — when a snapshot row is clicked (on demand only)

## Performance Guardrails

- Max snapshot window: 24h default, 7d (168h) max
- Max snapshot points: 500 per request
- Window and search filters available

---

## Quick run without Apache

If nothing is listening on port 80 (e.g. Apache not installed), you can still open the Risk Debug View:

1. **Start the Risk Analytics API** (must be listening on port 8000):
   ```bash
   cd risk-analytics-ui && docker compose up -d risk-analytics-ui-api
   ```
   Or run the API directly with uvicorn from the repo root.

2. **Serve the static files** from `post-apache/` (e.g. on port 9000):
   ```powershell
   cd c:\Users\WatMax\NetBet\post-apache
   python -m http.server 9000
   ```

3. **Open in Chrome/Edge:**
   ```
   http://localhost:9000/?api=http://localhost:8000
   ```
   The `?api=http://localhost:8000` tells the page to call the API on port 8000 (CORS is allowed). You get a clear, working URL without Apache.

---

## Local Apache Setup

To serve `post-apache/` under a stable URL with default `/api` base path, run it behind **local Apache** (or equivalent reverse proxy).

### On the machine (Windows) – quick checklist

| Step | Action |
|------|--------|
| **A** | Enable the vhost: in `httpd.conf` add `Include "c:/Users/WatMax/NetBet/post-apache/post-apache-vhost.conf"` **or** copy contents of `post-apache/post-apache-vhost.conf` into `conf/extra/httpd-vhosts.conf` and ensure that file is included from `httpd.conf`. |
| **B** | In `httpd.conf`, uncomment or add: `LoadModule proxy_module modules/mod_proxy.so` and `LoadModule proxy_http_module modules/mod_proxy_http.so`. |
| **C** | Restart Apache (service or `httpd -k restart` from Apache’s `bin`). |
| **D** | Allow port 80 in Windows Firewall (PowerShell as Administrator): `New-NetFirewallRule -DisplayName "Apache HTTP" -Direction Inbound -Protocol TCP -LocalPort 80 -Action Allow`. |
| **E** | In the vhost, proxy `/api/` to the **server** (e.g. `http://<SERVER-IP>:<API-PORT>/`). API + DB run on the server (Docker); no local Docker. |

**Checks:** Run `netstat -an | findstr ":80 "` — you should see `0.0.0.0:80` or `[::]:80` in LISTENING. From another device on the LAN, open `http://<machine-ip>/` (use this PC’s IPv4 from `ipconfig`). Risk Debug View should load; in DevTools → Network, `/api/...` requests return 200 with no CORS or connection errors.

**External URL:** `http://<machine-ip>/` (LAN-only unless you forward port 80 on your router).

### Port and URL

| Setting | Value |
|---------|-------|
| **Port** | 80 (defined in `post-apache.conf.example` via `<VirtualHost *:80>`) |
| **Exact URL** | **http://localhost/** |
| **Binding** | `*` = all interfaces (0.0.0.0). For local-only access, change to `127.0.0.1:80` in the vhost. |

**After enabling Apache, open: [http://localhost/](http://localhost/)**

### If you see "Failed: Service Unavailable"

The Risk Debug View is served by Apache; **leagues/data come from the Risk Analytics API**. The vhost must proxy `/api/` to the **server** where the API runs (Docker), not to `127.0.0.1`. Ensure:

1. **Proxy in vhost** points to the server: `ProxyPass /api/ http://<SERVER-IP>:<API-PORT>/` (replace with your server’s IP/host and API port).
2. **On the server:** `risk-analytics-ui-api` listens on `0.0.0.0:<API-PORT>` and the port is reachable from this machine (LAN/VPN/firewall).
3. **Validate from this PC:** `curl http://<SERVER-IP>:<API-PORT>/health` — if this works, the UI will work after restarting Apache.

### Reference config

- **`post-apache-vhost.conf`** — ready-to-use vhost for this machine: `DocumentRoot` and paths set for `c:\Users\WatMax\NetBet\post-apache`, binds to **\*:80** (all interfaces) for access via machine IP. Use this for network access.
- **`post-apache.conf.example`** — template with placeholder paths; copy and adjust for your OS if needed.

### Enable steps (Linux / WSL)

1. Copy the config and set paths:
   ```bash
   sudo cp post-apache/post-apache.conf.example /etc/apache2/sites-available/post-apache-debug.conf
   sudo sed -i "s|/path/to/NetBet|$(pwd)|g" /etc/apache2/sites-available/post-apache-debug.conf
   ```

2. Enable the site and required modules:
   ```bash
   sudo a2enmod proxy proxy_http
   sudo a2ensite post-apache-debug.conf
   sudo systemctl reload apache2
   ```

3. Ensure the Risk Analytics API is running (e.g. port 8000):
   ```bash
   docker compose up -d risk-analytics-ui-api
   ```

4. Open: **http://localhost/**

### Enable steps (Windows)

1. **Use the vhost config**  
   Either include the project vhost file from `httpd.conf`:
   ```apache
   Include "c:/Users/WatMax/NetBet/post-apache/post-apache-vhost.conf"
   ```
   Or copy the contents of `post-apache/post-apache-vhost.conf` into your Apache vhosts file:
   - XAMPP: `C:\xampp\apache\conf\extra\httpd-vhosts.conf`
   - Apache: `C:\Apache24\conf\extra\httpd-vhosts.conf` (ensure `Include conf/extra/httpd-vhosts.conf` is present in `httpd.conf`).

2. **Enable proxy modules** in `httpd.conf` (uncomment or add):
   ```apache
   LoadModule proxy_module modules/mod_proxy.so
   LoadModule proxy_http_module modules/mod_proxy_http.so
   ```

3. **Restart Apache** (e.g. from XAMPP Control Panel, or `httpd -k restart` from Apache `bin`).

4. **Verify** Apache is listening on port 80:
   ```powershell
   netstat -an | findstr ":80 "
   ```
   You should see `0.0.0.0:80` or `[::]:80` in LISTENING state.

5. **Open:** **http://localhost/** (or **http://&lt;machine-ip&gt;/** from another device; see below).

### Disable steps

**Linux / WSL:**
```bash
sudo a2dissite post-apache-debug.conf
sudo systemctl reload apache2
```

**Windows:** Comment out or remove the vhost block from `httpd-vhosts.conf`, then restart Apache.

### Access via machine IP (network)

To reach the Risk Debug View from other devices (e.g. **http://&lt;machine-ip&gt;/**):

1. **Vhost must bind to all interfaces:** use `post-apache-vhost.conf` as-is (it uses `<VirtualHost *:80>`). Do **not** bind only to `127.0.0.1`.

2. **Ensure Apache is listening on port 80** (all interfaces):
   ```powershell
   netstat -an | findstr ":80 "
   ```
   Expect something like `0.0.0.0:80` or `[::]:80` in LISTENING state.

3. **Open port 80 in Windows Firewall** (run PowerShell as Administrator if needed):
   ```powershell
   New-NetFirewallRule -DisplayName "Apache HTTP" -Direction Inbound -Protocol TCP -LocalPort 80 -Action Allow
   ```
   Or: Windows Security → Firewall → Advanced settings → Inbound Rules → New Rule → Port → TCP 80 → Allow.

4. **Risk Analytics API** must be running on this machine (e.g. `docker compose up -d risk-analytics-ui-api` on port 8000). Apache proxies `/api/` to `http://127.0.0.1:8000/`.

5. **From another machine on the same LAN**, open:
   ```
   http://<machine-ip>/
   ```
   Replace `<machine-ip>` with this PC’s IP (e.g. from `ipconfig`: IPv4 Address). The Risk Debug View should load and `/api/...` calls in browser dev tools should succeed (no CORS errors when using the same origin).

**Exact external URL:** `http://<machine-ip>/` (no port when using 80).  
**Scope:** Typically **LAN-only** unless you forward port 80 on your router to this PC; then it can be internet-facing (consider security and exposure).

### Apache not installed

**Ubuntu / Debian:**
```bash
sudo apt install apache2
```

**Windows:** Install XAMPP or Apache HTTP Server from [apache.org](https://httpd.apache.org/).

**macOS:** Apache is preinstalled; use `sudo apachectl start`.

---

## API Base

Defaults to `/api` when served behind Apache. **Intended setup:** Apache proxies `/api/` to the **server** where the Risk Analytics API runs (Docker), not to localhost. No local Docker required. In the vhost, set `ProxyPass /api/ http://<SERVER-IP>:<API-PORT>/` (and `ProxyPassReverse`) to your server’s host and API port.

Override with `?api=http://<server>:<port>` when opening the file directly or from another origin.

## Raw payload size and IDE previews

Raw payload responses can be **large**. To avoid Cursor/VS Code agent serialization errors (`serialize binary: invalid int 32`):

- **Do not** open `/api/debug/snapshots/{id}/raw` responses in the IDE HTTP client or chat preview.
- Test the Risk Debug View **in a browser** (Chrome/Edge): `http://localhost/` or `http://localhost:8080/`.
- The API returns a **truncated preview** (first 50 KB) when the payload is larger; full payload is for inspection in browser DevTools only.

## Prerequisites

- Risk Analytics API running (e.g. `docker compose up risk-analytics-ui-api` on port 8000)
- PostgreSQL with `market_event_metadata`, `market_derived_metrics`, `market_book_snapshots`

## API Endpoints (debug)

| Endpoint | Description |
|----------|-------------|
| `GET /api/debug/events/{market_id}/markets` | Markets for same event (Match Odds first) |
| `GET /api/debug/markets/{market_id}/snapshots` | All scalar columns (mbs + mdm + metadata), limit 500 |
| `GET /api/debug/snapshots/{snapshot_id}/raw` | raw_payload for one snapshot (on row click) |
