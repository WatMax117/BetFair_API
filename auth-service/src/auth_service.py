"""
NetBet Auth Service - Betfair API Authentication
Handles certificate-based login, session keep-alive, and token exposure.
Supports .crt+.key (PEM) or .p12 (PKCS12) - matches Java/betfair-bot format.
"""
import atexit
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

from .cert_loader import resolve_cert_and_key

# Load environment variables
load_dotenv()

# Logging configuration - output to stdout for Docker log collection
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("auth_service")

# Betfair Identity API endpoints
CERT_LOGIN_URL = "https://identitysso-cert.betfair.com/api/certlogin"
KEEP_ALIVE_URL = "https://identitysso.betfair.com/api/keepAlive"

# Default configuration
DEFAULT_KEEP_ALIVE_INTERVAL = 17 * 60  # 17 minutes (between 15-20 min)
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_DELAY = 5
TOKEN_FILE_PATH = "/data/ssoid"  # Shared volume for Java Streaming Service


class BetfairAuthService:
    """Betfair authentication service with certificate login and keep-alive."""

    def __init__(
        self,
        app_key: str,
        username: str,
        password: str,
        cert_path: str,
        key_path: Optional[str] = None,
        cert_password: Optional[str] = None,
        keep_alive_interval: int = DEFAULT_KEEP_ALIVE_INTERVAL,
        token_file_path: str = TOKEN_FILE_PATH,
    ):
        self.app_key = app_key
        self.username = username
        self.password = password
        self.keep_alive_interval = keep_alive_interval
        self.token_file_path = Path(token_file_path)

        cert_file, key_file, self._cert_cleanup = resolve_cert_and_key(
            cert_path, key_path, cert_password
        )
        self._cert_path = Path(cert_file)
        self._key_path = Path(key_file)
        if self._cert_cleanup:
            atexit.register(self._cert_cleanup)

        self._session_token: Optional[str] = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._keep_alive_thread: Optional[threading.Thread] = None

    def _request_with_retry(
        self,
        method: str,
        url: str,
        max_attempts: int = DEFAULT_RETRY_ATTEMPTS,
        **kwargs,
    ) -> Optional[requests.Response]:
        """Execute HTTP request with retry logic for network/timeout failures."""
        last_error = None
        for attempt in range(1, max_attempts + 1):
            try:
                response = requests.request(
                    method,
                    url,
                    timeout=30,
                    **kwargs,
                )
                return response
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                last_error = e
                logger.warning(
                    "Request attempt %d/%d failed: %s. Retrying in %ds...",
                    attempt,
                    max_attempts,
                    str(e),
                    DEFAULT_RETRY_DELAY,
                )
                if attempt < max_attempts:
                    time.sleep(DEFAULT_RETRY_DELAY)
        logger.error("All %d request attempts failed. Last error: %s", max_attempts, last_error)
        return None

    def login(self) -> bool:
        """Perform certificate-based login to Betfair Identity API."""
        if not self._cert_path.exists():
            logger.error("Certificate file not found: %s", self._cert_path)
            return False
        if not self._key_path.exists():
            logger.error("Private key file not found: %s", self._key_path)
            return False

        headers = {
            "X-Application": self.app_key,
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "username": self.username,
            "password": self.password,
        }

        logger.info("Attempting certificate login for user: %s", self.username)

        response = self._request_with_retry(
            "POST",
            CERT_LOGIN_URL,
            headers=headers,
            data=data,
            cert=(str(self._cert_path), str(self._key_path)),
        )

        if response is None:
            return False

        try:
            result = response.json()
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON response from Betfair: %s", e)
            return False

        login_status = result.get("loginStatus")
        session_token = result.get("sessionToken")

        if login_status == "SUCCESS" and session_token:
            with self._lock:
                self._session_token = session_token
            self._write_token_file(session_token)
            logger.info("Login successful. Session token obtained.")
            return True

        logger.error(
            "Login failed. Status: %s, Error: %s",
            login_status,
            result.get("error", result.get("errorCode", "UNKNOWN")),
        )
        return False

    def keep_alive(self) -> bool:
        """Send keep-alive request to extend session."""
        with self._lock:
            token = self._session_token

        if not token:
            logger.warning("No session token available for keep-alive")
            return False

        headers = {
            "X-Application": self.app_key,
            "X-Authentication": token,
            "Accept": "application/json",
        }

        response = self._request_with_retry("GET", KEEP_ALIVE_URL, headers=headers)

        if response is None:
            return False

        try:
            result = response.json()
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON response from keep-alive: %s", e)
            return False

        status = result.get("status", "FAIL")
        if status == "SUCCESS":
            new_token = result.get("token")
            if new_token:
                with self._lock:
                    self._session_token = new_token
                self._write_token_file(new_token)
                logger.info("Keep-alive successful. Session extended.")
            else:
                logger.info("Keep-alive successful (token unchanged).")
            return True

        logger.error(
            "Keep-alive failed. Status: %s, Error: %s",
            status,
            result.get("error", result.get("errorCode", "UNKNOWN")),
        )
        return False

    def _keep_alive_loop(self) -> None:
        """Background loop to send keep-alive requests at configured interval."""
        logger.info("Keep-alive loop started (interval: %d seconds)", self.keep_alive_interval)
        while not self._stop_event.wait(timeout=self.keep_alive_interval):
            if not self.keep_alive():
                logger.warning("Keep-alive failed. Attempting re-login...")
                if self.login():
                    logger.info("Re-login successful after keep-alive failure.")
                else:
                    logger.error("Re-login failed. Will retry on next cycle.")

    def start_keep_alive(self) -> None:
        """Start the background keep-alive thread."""
        if self._keep_alive_thread and self._keep_alive_thread.is_alive():
            logger.warning("Keep-alive thread already running")
            return
        self._stop_event.clear()
        self._keep_alive_thread = threading.Thread(target=self._keep_alive_loop, daemon=True)
        self._keep_alive_thread.start()

    def stop_keep_alive(self) -> None:
        """Stop the background keep-alive thread."""
        self._stop_event.set()
        if self._keep_alive_thread:
            self._keep_alive_thread.join(timeout=5)

    def _write_token_file(self, token: str) -> None:
        """Write the current session token to a file for the Java Streaming Service."""
        try:
            self.token_file_path.parent.mkdir(parents=True, exist_ok=True)
            self.token_file_path.write_text(token.strip(), encoding="utf-8")
        except OSError as e:
            logger.warning("Could not write token file %s: %s", self.token_file_path, e)

    def get_session_token(self) -> Optional[str]:
        """Return the current valid session token."""
        with self._lock:
            return self._session_token
