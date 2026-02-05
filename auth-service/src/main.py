"""
NetBet Auth Service - Entry point
Runs authentication, keep-alive, and token API in a single process.
"""
import logging
import os
import signal
import sys
import threading

from .auth_service import BetfairAuthService
from .api_server import run_api_server

logger = logging.getLogger("auth_service")


def main() -> int:
    """Main entry point."""
    # Required environment variables
    app_key = os.getenv("BETFAIR_APP_KEY")
    username = os.getenv("BETFAIR_USERNAME")
    password = os.getenv("BETFAIR_PASSWORD")
    cert_path = os.getenv("BETFAIR_CERT_PATH", "/certs/client-2048.p12")
    key_path = os.getenv("BETFAIR_KEY_PATH")
    cert_password = os.getenv("CERT_PASSWORD")

    # Support .p12 (from Java/betfair-bot) or .crt+.key (PEM)
    use_p12 = cert_path.lower().endswith(".p12")
    if use_p12 and not cert_password:
        logger.error("CERT_PASSWORD required when using .p12 certificate")
        return 1

    if not all([app_key, username, password]):
        logger.error(
            "Missing required env vars: BETFAIR_APP_KEY, BETFAIR_USERNAME, BETFAIR_PASSWORD"
        )
        return 1

    keep_alive_interval = int(os.getenv("KEEP_ALIVE_INTERVAL_SEC", str(17 * 60)))
    token_file_path = os.getenv("TOKEN_FILE_PATH", "/data/ssoid")
    api_host = os.getenv("API_HOST", "0.0.0.0")
    api_port = int(os.getenv("API_PORT", "8080"))

    auth_service = BetfairAuthService(
        app_key=app_key,
        username=username,
        password=password,
        cert_path=cert_path,
        key_path=key_path if not use_p12 else None,
        cert_password=cert_password if use_p12 else None,
        keep_alive_interval=keep_alive_interval,
        token_file_path=token_file_path,
    )

    if not auth_service.login():
        logger.error("Initial login failed. Exiting.")
        return 1

    auth_service.start_keep_alive()

    def shutdown(signum=None, frame=None):
        logger.info("Shutdown signal received. Stopping keep-alive...")
        auth_service.stop_keep_alive()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    api_thread = threading.Thread(
        target=run_api_server,
        args=(api_host, api_port, auth_service),
        daemon=True,
    )
    api_thread.start()

    logger.info("Application started on port %d. Use /token or /health", api_port)

    # Keep main thread alive; API runs in daemon thread
    try:
        api_thread.join()
    except KeyboardInterrupt:
        shutdown()

    return 0


if __name__ == "__main__":
    sys.exit(main())
