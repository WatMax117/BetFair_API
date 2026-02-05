#!/usr/bin/env python3
"""
Verify Betfair certificate login with migrated credentials.
Run from project root: python scripts/verify_login.py
"""
import os
import sys
from pathlib import Path

# Add project root to path
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))
os.chdir(_project_root)

# Load .env
from dotenv import load_dotenv
load_dotenv(_project_root / ".env")

# Determine cert path (Docker uses /certs, local uses ./certs)
def _resolve_cert_path():
    cert_path = os.getenv("BETFAIR_CERT_PATH", "/certs/client-2048.p12")
    if cert_path.startswith("/certs/"):
        local = _project_root / "certs" / Path(cert_path).name
        if local.exists():
            return str(local)
    return cert_path


def main():
    from src.auth_service import BetfairAuthService

    app_key = os.getenv("BETFAIR_APP_KEY")
    username = os.getenv("BETFAIR_USERNAME")
    password = os.getenv("BETFAIR_PASSWORD")
    cert_path = _resolve_cert_path()
    cert_password = os.getenv("CERT_PASSWORD")

    missing = []
    if not app_key:
        missing.append("BETFAIR_APP_KEY")
    if not username:
        missing.append("BETFAIR_USERNAME")
    if not password:
        missing.append("BETFAIR_PASSWORD")
    if not cert_password:
        missing.append("CERT_PASSWORD")
    if not Path(cert_path).exists():
        missing.append(f"Certificate file: {cert_path}")

    if missing:
        print("Missing:", ", ".join(missing))
        print("\nEnsure .env is configured and client-2048.p12 is in certs/")
        print("See MIGRATION.md for how to obtain the .p12 file.")
        return 1

    print("Verifying Betfair login with migrated credentials...")
    auth = BetfairAuthService(
        app_key=app_key,
        username=username,
        password=password,
        cert_path=cert_path,
        cert_password=cert_password,
    )
    if auth.login():
        token = auth.get_session_token()
        print("SUCCESS: Login verified. Session token obtained.")
        print(f"Token preview: {token[:20]}..." if token and len(token) > 20 else token)
        return 0
    else:
        print("FAILED: Login failed. Check credentials and certificate.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
