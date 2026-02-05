"""
Simple internal API server to expose the current SSO token.
For use by the future Java Streaming Service.
"""
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional

logger = logging.getLogger("auth_service")


class TokenHandler(BaseHTTPRequestHandler):
    """HTTP handler that serves the current session token."""

    auth_service = None  # Injected by main

    def log_message(self, format, *args):
        logger.info("%s - %s", self.address_string(), format % args)

    def do_GET(self):
        if self.path == "/health":
            self._send_json({"status": "ok"}, 200)
            return
        if self.path in ("/token", "/ssoid"):
            token = self._get_token()
            if token:
                self._send_json({"ssoid": token, "status": "valid"}, 200)
            else:
                self._send_json({"ssoid": None, "status": "no_session"}, 503)
            return
        self._send_json({"error": "Not found"}, 404)

    def _get_token(self) -> Optional[str]:
        if self.auth_service:
            return self.auth_service.get_session_token()
        return None

    def _send_json(self, data: dict, status: int):
        import json
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run_api_server(host: str, port: int, auth_service) -> None:
    """Run the token API server."""
    TokenHandler.auth_service = auth_service
    server = HTTPServer((host, port), TokenHandler)
    logger.info("Token API server listening on %s:%d", host, port)
    server.serve_forever()
