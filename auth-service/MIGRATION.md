# Credential Migration – betfair-bot / .fly → auth-service

## Data Audit Summary

Credentials were extracted from **Cursor History** (previous betfair-bot project and .fly production deployment).

### Extracted Credentials

| Item | Value | Source |
|------|-------|--------|
| BETFAIR_APP_KEY | `WftFC5jIOJMsORVD` | .env.vps |
| BETFAIR_USERNAME | `gorog@mail.bg` | .env.vps |
| BETFAIR_PASSWORD | `BerbaBet#777` | .env.vps |
| CERT_PASSWORD | `surebet-betfair` | .env.vps |
| Certificate (.crt) | WatMaxBetfair PEM | client-2048.crt (History) |

### SSL Certificate

- **client-2048.crt** – Restored to `certs/client-2048.crt` (PEM, upload to Betfair if needed).
- **client-2048.p12** – Required for login. Contains cert + private key. **Not in local repo** – copy from VPS or local backup.

## Obtain client-2048.p12

The Java/betfair-bot project used `.p12`. It was typically located at:

- **VPS:** `/root/NetBet/betfair-bot/certs/client-2048.p12`
- **Local (if present):** `NetBet/betfair-bot/certs/client-2048.p12` or `Desktop` / `Downloads`

### Option A: Copy from VPS via SCP (if betfair-bot was deployed there)

```powershell
scp -i "C:\Users\WatMax\.ssh\id_ed25519_contabo" root@158.220.83.195:/root/NetBet/betfair-bot/certs/client-2048.p12 "C:\Users\WatMax\NetBet\auth-service\certs\"
```

Or run: `.\scripts\fetch_certs_from_vps.ps1`

**Note:** If the betfair-bot folder is not on the VPS (e.g. it was deployed via Fly.io), check your local machine: `Desktop`, `Downloads`, or any `betfair-bot/certs` folder.

### Option B: Regenerate from .crt + .key (if you have .key)

If you have `client-2048.key`:

```powershell
cd C:\Users\WatMax\NetBet\auth-service\certs
openssl pkcs12 -export -out client-2048.p12 -inkey client-2048.key -in client-2048.crt -password pass:surebet-betfair
```

## Verify Login

After `client-2048.p12` is in `certs/`:

```powershell
cd C:\Users\WatMax\NetBet\auth-service
pip install -r requirements.txt
python scripts/verify_login.py
```

Or with Docker:

```powershell
docker compose up -d
docker compose logs -f auth-service
```

Look for: `Login successful. Session token obtained.`
