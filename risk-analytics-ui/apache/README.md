# Apache setup for Risk Analytics UI (temporary, validation only)

Expose the Risk Analytics Web UI at **http://&lt;VPS_PUBLIC_IP&gt;/** (e.g. http://158.220.83.195/). Apache is the reverse proxy. No auth, no HTTPS (temporary validation only).

---

## ⚠️ IMPORTANT: Avoid locking yourself out (SSH port 22)

**Always allow SSH (port 22) before or together with any UFW changes.** If you enable or reload UFW without allowing 22/tcp, you can lose SSH access. Restoring access then requires the **provider’s out-of-band console** (e.g. Contabo VNC). When adding firewall rules, run:

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp   # or your other rules
sudo ufw reload
```

---

## Recovery: Restore SSH and complete UI deployment

If SSH to the VPS is **timing out or refused** (e.g. port 22 was blocked by UFW or the service was interrupted), use the **Contabo VNC console** to get in and fix it. SSH is the foundation for deployment and for the API daemon talking to the Docker database.

### Step 1: Log in via Contabo VNC console

1. Open the **Contabo** customer panel.
2. Go to your **server** → **VNC console** (or **Console** / **KVM**).
3. Open the in-browser or downloadable VNC session and log in as **root** (or your admin user) with the server password.

You are now on the VPS without using SSH.

### Step 2: Restore SSH access (UFW)

Run these in the VNC console so port 22 is allowed again:

```bash
sudo ufw allow 22/tcp
sudo ufw reload
sudo ufw status
```

Confirm that **22/tcp** appears as ALLOW. Test SSH from your local machine (e.g. `ssh -i your_key root@158.220.83.195`). Once SSH works again, you can close VNC and continue over SSH.

### Step 3: Complete UI deployment (Apache + port 80)

Still in the same session (VNC or SSH), run:

```bash
# Allow HTTP so the UI is reachable from the internet
sudo ufw allow 80/tcp
sudo ufw reload

# Ensure Apache is running and Risk Analytics vhost is active
sudo systemctl start apache2
sudo systemctl enable apache2
sudo a2enmod proxy proxy_http
sudo a2ensite risk-analytics.conf
sudo systemctl reload apache2

# If the vhost file is not yet on the server, copy it from the repo (clone or scp first), then:
# sudo cp /path/to/risk-analytics-ui/apache/risk-analytics.conf /etc/apache2/sites-available/risk-analytics.conf
# sudo a2ensite risk-analytics.conf
# sudo systemctl reload apache2
```

Verify on the server:

```bash
curl -sS -o /dev/null -w "UI: HTTP %{http_code}\n" http://127.0.0.1/
curl -sS -o /dev/null -w "API: HTTP %{http_code}\n" http://127.0.0.1/api/health
```

Then from any browser:

- **UI:** http://158.220.83.195/
- **API health:** http://158.220.83.195/api/health

Once SSH is stable and the UI is reachable, you can continue with REST API integration.

For **when to rebuild images vs recreate containers vs reload Apache**, see the main **risk-analytics-ui/README.md** section **“VPS: Rebuild and redeploy”**.

---

## Start Apache – interface accessible from anywhere

On the VPS, from the **repo root**, run:

```bash
chmod +x risk-analytics-ui/apache/vps_start_apache_public.sh
./risk-analytics-ui/apache/vps_start_apache_public.sh
```

This will:

1. Start and enable Apache  
2. Enable proxy modules and activate the Risk Analytics vhost (port 80 → UI on 8080, /api/ on 8081)  
3. Open TCP port 80 to **0.0.0.0/0** (UFW: `allow 80/tcp`) so the interface can be accessed from anywhere on the internet  

After that, use **http://&lt;VPS_PUBLIC_IP&gt;/** and **http://&lt;VPS_PUBLIC_IP&gt;/api/health** from any browser.

**To turn off public access:**

```bash
./risk-analytics-ui/apache/vps_disable_public_access.sh
```

(If the provider firewall, e.g. Contabo, blocks port 80, add an inbound rule there: TCP 80, source 0.0.0.0/0.)

### Run from your machine (SSH one-liner or already on VPS)

If you run these from your **local Windows** (e.g. PowerShell), use your SSH key and the VPS IP. One-liner (disable default site, reload Apache, open SSH + HTTP, verify):

```powershell
ssh -i C:\Users\WatMax\.ssh\id_ed25519_contabo root@158.220.83.195 "a2dissite 000-default.conf 2>/dev/null; systemctl reload apache2; ufw allow 22/tcp; ufw allow 80/tcp; ufw --force reload; echo 'Done. Verifying:'; curl -sS -o /dev/null -w 'UI root: HTTP %{http_code}' http://127.0.0.1/; echo ''; curl -sS -o /dev/null -w 'API health: HTTP %{http_code}' http://127.0.0.1/api/health; echo ''"
```

Or, if you’re **already logged in on the VPS** via SSH, run:

```bash
# 1. Disable default Apache site
sudo a2dissite 000-default.conf

# 2. Reload Apache
sudo systemctl reload apache2

# 3. Ensure SSH and HTTP are open
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw reload
```

Then from any browser:

- **UI:** http://158.220.83.195/
- **API health:** http://158.220.83.195/api/health

SSH (22) stays open so you can keep using the server.

---

## Temporary public access for visual validation (1–2 minutes)

Use this to get **brief public browser access** for screenshots (logic/parameter validation). Not for production.

**Assumptions:** Docker exposes UI on host port **8080** and API on host port **8081**. No domain, no HTTPS, no auth.

### 1. Apache reverse proxy on port 80

The vhost **risk-analytics.conf** is already set up to:

- Listen on **\*:80** (mod_proxy, mod_proxy_http; no ServerName).
- **/** → proxy to **http://127.0.0.1:8080** (UI).
- **/api/** → proxy to **http://127.0.0.1:8081** (API; prefix stripped so backend gets `/health`, `/leagues`, etc.).
- Logs: **risk-analytics-error.log**, **risk-analytics-access.log**.

On the VPS, ensure the vhost is deployed and enabled:

```bash
sudo cp risk-analytics-ui/apache/risk-analytics.conf /etc/apache2/sites-available/risk-analytics.conf
sudo a2enmod proxy proxy_http
sudo a2ensite risk-analytics.conf
sudo systemctl reload apache2
```

### 2. Firewall – temporary open access

Open TCP 80 to everyone (for validation only):

**UFW (on VPS):**

```bash
sudo ufw allow 80/tcp
sudo ufw reload
```

**Provider (Contabo):** If needed, in the panel add an inbound rule: TCP port 80, source **0.0.0.0/0**.

### 3. Verification (must work)

**On the VPS:**

```bash
ss -lntp | grep :80          # Apache listening on 0.0.0.0:80
curl -I http://127.0.0.1/   # HTTP 200 or 301
curl http://127.0.0.1/api/health   # JSON e.g. {"status":"ok"}
```

**From an external browser:**

- http://&lt;VPS_PUBLIC_IP&gt;/ → UI loads  
- http://&lt;VPS_PUBLIC_IP&gt;/api/health → API responds with JSON  

### 4. Easy shutdown / rollback (after screenshots)

**One-command disable (recommended):**

```bash
./risk-analytics-ui/apache/vps_disable_public_access.sh
```

This: removes **ufw allow 80/tcp**, disables the **risk-analytics** vhost, and reloads Apache. Port 80 is closed again; Docker ports 8080/8081 stay internal.

**Optional – stop Apache entirely:**

```bash
./risk-analytics-ui/apache/vps_disable_public_access.sh --stop-apache
```

**Manual rollback:**

```bash
sudo ufw delete allow 80/tcp
sudo ufw reload
sudo a2dissite risk-analytics.conf
sudo systemctl reload apache2
# Optional: sudo systemctl stop apache2
```

**Result:** Port 80 closed; no public access. Docker 8080/8081 remain internal only.

**Out of scope:** HTTPS, domain/DNS, authentication, zero-trust/VPN, production hardening.

---

## Quick enable (one script on VPS)

From the **repo root** on the VPS:

```bash
chmod +x risk-analytics-ui/apache/vps_enable_risk_analytics.sh
./risk-analytics-ui/apache/vps_enable_risk_analytics.sh
```

The script starts Apache, enables proxy modules, activates the Risk Analytics vhost, verifies port 80, sets UFW to allow port 80 only from one IP (default 94.26.26.147), and runs a local curl check.

**Remove IP restriction (allow access from any IP):**

```bash
./risk-analytics-ui/apache/vps_ufw_allow_all_port80.sh
```

Then try http://&lt;VPS_PUBLIC_IP&gt;/ again. To restrict to your IP later: `./risk-analytics-ui/apache/vps_ufw_allow_single_ip.sh 94.26.26.147`

---

## Open the UI in your local browser via SSH (no port 80 open to internet)

If you have SSH access to the VPS but port 80 is blocked by the provider firewall (or you prefer not to expose it), use **SSH local port forwarding**: your machine’s browser talks to `localhost`, and SSH forwards that to the VPS’s Apache on port 80.

**On your local machine (Windows PowerShell or any terminal with `ssh`):**

1. Start the tunnel (replace `USER` and `VPS_PUBLIC_IP` with your SSH user and VPS IP):

   ```bash
   ssh -L 8080:127.0.0.1:80 USER@VPS_PUBLIC_IP
   ```

   Example:

   ```bash
   ssh -L 8080:127.0.0.1:80 root@158.220.83.195
   ```

   Keep this SSH session open while you use the UI.

2. In your **local browser** open:

   - **UI:** http://localhost:8080/
   - **API health:** http://localhost:8080/api/health

Traffic goes through the SSH connection, so the provider does not need to allow inbound TCP 80. Apache must be running on the VPS and listening on port 80 (e.g. after running the enable script there).

**To inspect an error:** Keep the tunnel open and open http://localhost:8080/ in your browser to see the exact page (e.g. 502, 503, or HTML). For raw response from the shell (tunnel must be running): `curl -i http://localhost:8080/` or in PowerShell: `(Invoke-WebRequest -Uri http://localhost:8080/ -UseBasicParsing).Content`.

---

## Fix external access (connection refused on port 80)

If from your machine **ping** works but **http://&lt;VPS_PUBLIC_IP&gt;/** gives *connection refused* and **Test-NetConnection &lt;VPS_PUBLIC_IP&gt; -Port 80** shows **TcpTestSucceeded: False**, then the VPS is reachable but nothing is accepting TCP 80 from the outside. Run these checks **on the VPS** in order.

### 1. Verify Apache is running and listening

```bash
sudo systemctl status apache2
sudo ss -lntp | grep :80
```

**Expected:** `LISTEN ... 0.0.0.0:80` (Apache). If nothing is listening → fix Apache (install, enable, see Manual steps below) before continuing.

### 2. Verify the vhost is enabled

```bash
sudo apachectl -S
```

Ensure **risk-analytics.conf** is the active/default vhost on :80. If not:

```bash
sudo a2ensite risk-analytics.conf
sudo systemctl reload apache2
```

### 3. Verify local firewall (UFW)

```bash
sudo ufw status verbose
```

For testing, temporarily allow port 80 from anywhere:

```bash
sudo ufw allow 80/tcp
sudo ufw reload
```

(You can restrict back to a single IP after validation with `./risk-analytics-ui/apache/vps_ufw_allow_single_ip.sh 94.26.26.147`.)

### 4. Check Contabo / provider firewall (most likely cause)

Even if Apache and UFW are correct, **Contabo’s firewall** (or your VPS provider’s) must allow **inbound TCP 80**.

- In the **Contabo panel:** Server → Network / Firewall / Security.
- Add an **inbound** rule:
  - **Protocol:** TCP  
  - **Port:** 80  
  - **Source:** your IP (e.g. 94.26.26.147) or temporarily **0.0.0.0/0** for testing.

Without this rule, external connections to port 80 will not reach the server.

### 5. Local sanity check on the VPS

```bash
curl -I http://127.0.0.1/
```

- **Fails** → Apache or proxy config issue (check Apache logs, Docker containers on 8080/8081).
- **Succeeds (HTTP/1.1 200)** → Apache is fine; the block is UFW and/or the **provider firewall** (step 4).

**Expected final result:** From your machine, http://&lt;VPS_PUBLIC_IP&gt;/ loads the Risk Analytics UI and http://&lt;VPS_PUBLIC_IP&gt;/api/health returns `{"status":"ok"}`. Temporary validation only; no HTTPS, domain, or auth. Only Apache on port 80 should be externally reachable; Docker ports 8080/8081 stay internal.

---

## Manual steps (runbook)

If you prefer to run each step yourself:

1. **Apache running and enabled**
   ```bash
   sudo systemctl start apache2
   sudo systemctl enable apache2
   sudo systemctl status apache2
   ```

2. **Enable proxy modules**
   ```bash
   sudo a2enmod proxy
   sudo a2enmod proxy_http
   sudo systemctl restart apache2
   ```

3. **Activate the Risk Analytics vhost**  
   Config file: `risk-analytics-ui/apache/risk-analytics.conf`
   ```bash
   sudo cp risk-analytics-ui/apache/risk-analytics.conf /etc/apache2/sites-available/risk-analytics.conf
   sudo a2ensite risk-analytics.conf
   sudo systemctl reload apache2
   ```

4. **Verify Apache is listening on port 80**
   ```bash
   sudo ss -lntp | grep :80
   ```
   Expected: Apache listening on 0.0.0.0:80.

5. **Firewall: allow port 80**  
   To allow from any IP (no restriction):
   ```bash
   sudo ufw allow 80/tcp
   sudo ufw reload
   ```
   To allow only your IP (e.g. 94.26.26.147) instead:
   ```bash
   sudo ufw delete allow 80/tcp || true
   sudo ufw allow from 94.26.26.147 to any port 80 proto tcp
   sudo ufw reload
   ```

6. **Local sanity check on the VPS**
   ```bash
   curl -I http://127.0.0.1/
   ```
   Expected: `HTTP/1.1 200 OK`.

**Expected result:** http://&lt;VPS_PUBLIC_IP&gt;/ loads the Risk Analytics UI; http://&lt;VPS_PUBLIC_IP&gt;/api/health returns `{"status":"ok"}`.

---

## Prerequisites on VPS

- Docker (and Compose) running the main stack so that:
  - **Risk Analytics UI** is reachable on the host at `http://127.0.0.1:3000`
  - **Risk Analytics API** is reachable on the host at `http://127.0.0.1:8000`
- Apache 2.4 with `mod_proxy` and `mod_proxy_http` (typical on Debian/Ubuntu).

## 1. Install Apache (if needed)

**Debian/Ubuntu:**

```bash
sudo apt update
sudo apt install -y apache2
sudo a2enmod proxy proxy_http
sudo systemctl enable apache2
```

## 2. Deploy the vhost config

Copy the vhost into Apache’s config and enable it:

```bash
# From the repo on the VPS (e.g. /home/user/NetBet or wherever you clone)
sudo cp risk-analytics-ui/apache/risk-analytics.conf /etc/apache2/sites-available/risk-analytics.conf
sudo a2ensite risk-analytics.conf
```

If Apache already has a default site on port 80, either disable it or make this the default:

```bash
sudo a2dissite 000-default.conf
```

Reload Apache:

```bash
sudo systemctl reload apache2
```

## 3. Firewall (single-IP restriction recommended)

Restrict port 80 to your IP only (e.g. for validation). From the repo on the VPS:

```bash
./risk-analytics-ui/apache/vps_ufw_allow_single_ip.sh
# Or with a custom IP:
./risk-analytics-ui/apache/vps_ufw_allow_single_ip.sh 94.26.26.147
```

This removes any global `allow 80/tcp` and adds `allow from <IP> to any port 80`. Then:

```bash
sudo ufw status
sudo ufw enable   # if UFW was inactive
```

## 4. Verification checklist

From your **local machine** (allowed IP):

1. **UI:** Open `http://<VPS_PUBLIC_IP>/`. The Risk Analytics UI (Leagues page) should load.
2. **API:** Open `http://<VPS_PUBLIC_IP>/api/health`. You should see `{"status":"ok"}`.
3. **Other IPs:** From another machine or IP, `http://<VPS_PUBLIC_IP>/` and `/api/health` should be unreachable (connection refused or timeout) if UFW is restricting port 80.

Docker services stay on host ports 8080 and 8081 only; no new public ports. If the UI loads but API calls fail, check that the UI and API containers are up and that Apache can reach `127.0.0.1:8080` and `127.0.0.1:8081`.

## Apache config in use

The vhost used is **`risk-analytics-ui/apache/risk-analytics.conf`**:

- **Listen:** HTTP on port 80 (no SSL).
- **`/`** → proxy to `http://127.0.0.1:8080/` (UI on host port 8080).
- **`/api/`** → proxy to `http://127.0.0.1:8081/` (API on host port 8081; prefix stripped so backend receives `/health`, `/leagues`, etc.).
- Logs: `risk-analytics-error.log` and `risk-analytics-access.log` under Apache’s log dir.

Docker ports 8080 and 8081 do **not** need to be exposed publicly; Apache runs on the host and proxies to localhost. (Ensure your Docker stack maps UI to 8080 and API to 8081 on the host, or edit risk-analytics.conf to match your ports.)

---

## Shutting down or restricting later

### Disable this access (keep Apache for other things)

```bash
sudo a2dissite risk-analytics.conf
sudo systemctl reload apache2
```

### Stop Apache entirely

```bash
sudo systemctl stop apache2
```

### Restrict access (when you add controls)

- **IP allowlist:** Use `Require ip ...` in the vhost (or a snippet in `sites-available`) and reload.
- **HTTP auth:** Enable `mod_auth_basic`, add `AuthType Basic`, `AuthUserFile`, `Require valid-user` in the vhost.
- **HTTPS / reverse proxy to a zero-trust endpoint:** Replace this vhost with an HTTPS server that terminates TLS and optionally forwards to an identity-aware proxy; document in a separate runbook.

Do **not** rely on this open setup for production; it is for temporary validation only.

**Out of scope (do not implement in this setup):** HTTPS/SSL, domain/DNS, authentication/zero-trust, and any changes to ingestion, DB, or Docker networking.

---

## UFW rules relevant to port 80 (after running vps_ufw_allow_single_ip.sh)

- **Removed:** `allow 80/tcp` (global).
- **Added:** `allow from 94.26.26.147 to any port 80 proto tcp`.

To show only port 80–related rules:

```bash
sudo ufw status | grep 80
```

Example output:

```
94.26.26.147          ALLOW IN       80/tcp
```
