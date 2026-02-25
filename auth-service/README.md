# NetBet Auth Service

Betfair API authentication service for the NetBet project. Handles certificate-based login, session keep-alive, and token exposure for the future Java Streaming Service.

## Features

- **Certificate authentication** – Non-interactive login via Betfair Identity API (`identitysso-cert.betfair.com`)
- **Session keep-alive** – Background heartbeat every 15–20 minutes to prevent session expiry
- **Token exposure** – Internal API (`/token`, `/ssoid`) and shared volume file (`/data/ssoid`) for Java service
- **Health check** – `/health` endpoint for container monitoring

## Prerequisites

- Docker and Docker Compose
- Betfair API application key (from [Betfair Developer](https://developer.betfair.com/))
- Self-signed SSL certificate and private key (uploaded to your Betfair account)

### Certificate Setup

```bash
# Generate private key and certificate (upload .crt to Betfair)
openssl genrsa -out client-2048.key 2048
openssl req -new -x509 -key client-2048.key -out client-2048.crt -days 365
```

Place `client-2048.crt` and `client-2048.key` in `./certs/` before running.

## Quick Start

1. Copy environment template:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your Betfair credentials:
   ```
   BETFAIR_APP_KEY=your_app_key
   BETFAIR_USERNAME=your_username
   BETFAIR_PASSWORD=your_password
   ```

3. Place SSL certificates in `./certs/`:
   ```
   certs/
   ├── client-2048.crt
   └── client-2048.key
   ```

4. Build and run:
   ```bash
   docker-compose up -d
   ```

## API Endpoints

| Endpoint   | Description                           |
|-----------|----------------------------------------|
| `GET /health` | Health check (returns `{"status":"ok"}`) |
| `GET /token`  | Current session token (ssoid)         |
| `GET /ssoid`  | Alias for `/token`                    |

## Deployment (VPS)

1. **SSH setup** – Use SSH keys; disable password auth for `root` or use a deployment user.

2. **Deploy**:
   ```bash
   scp -r . user@158.220.83.195:/opt/netbet/auth-service/
   ssh user@158.220.83.195 "cd /opt/netbet/auth-service && docker-compose up -d"
   ```

3. **Token retrieval** – Java Streaming Service can:
   - Call `http://auth-service:8080/token` (when on same Docker network)
   - Read `/data/ssoid` from shared volume

## Environment Variables

| Variable                 | Required | Default                | Description              |
|--------------------------|----------|------------------------|--------------------------|
| BETFAIR_APP_KEY          | Yes      | -                      | Betfair application key  |
| BETFAIR_USERNAME         | Yes      | -                      | Betfair username         |
| BETFAIR_PASSWORD         | Yes      | -                      | Betfair password         |
| BETFAIR_CERT_PATH        | No       | `/certs/client-2048.crt` | Certificate path       |
| BETFAIR_KEY_PATH         | No       | `/certs/client-2048.key` | Private key path       |
| KEEP_ALIVE_INTERVAL_SEC  | No       | 1020 (17 min)          | Keep-alive interval      |
| TOKEN_FILE_PATH          | No       | `/data/ssoid`          | Token file for Java      |
| API_PORT                 | No       | 8080                   | API server port          |

## Local Development

```bash
# Create venv and install deps
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt

# Set env vars and run (ensure certs in ./certs)
$env:BETFAIR_APP_KEY="..."; $env:BETFAIR_USERNAME="..."; $env:BETFAIR_PASSWORD="..."
$env:BETFAIR_CERT_PATH="certs/client-2048.crt"; $env:BETFAIR_KEY_PATH="certs/client-2048.key"
$env:TOKEN_FILE_PATH="data/ssoid"
python -m src.main
```
