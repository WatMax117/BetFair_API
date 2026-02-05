"""
Certificate loader - supports .crt+.key (PEM) or .p12 (PKCS12).
Matches the Java/betfair-bot credential format.
"""
import tempfile
from pathlib import Path
from typing import Optional, Tuple

# Logging
import logging
logger = logging.getLogger("auth_service")


def _p12_to_pem(p12_path: Path, password: str) -> Tuple[Path, Path]:
    """Extract .crt and .key from .p12 to temporary files. Returns (cert_path, key_path)."""
    try:
        from cryptography.hazmat.primitives.serialization import (
            Encoding,
            PrivateFormat,
            NoEncryption,
            pkcs12,
        )
        from cryptography.hazmat.backends import default_backend
    except ImportError:
        raise RuntimeError("Install cryptography: pip install cryptography") from None

    with open(p12_path, "rb") as f:
        p12_data = f.read()

    try:
        key, cert, _ = pkcs12.load_key_and_certificates(
            p12_data,
            (password or "").encode() if password else None,
            default_backend(),
        )
    except Exception as e:
        logger.error("Failed to load .p12: %s (check path and CERT_PASSWORD)", e)
        raise

    tmpdir = Path(tempfile.mkdtemp(prefix="netbet_certs_"))
    cert_file = tmpdir / "client.crt"
    key_file = tmpdir / "client.key"
    cert_file.write_bytes(cert.public_bytes(Encoding.PEM))
    key_file.write_bytes(
        key.private_bytes(
            Encoding.PEM,
            PrivateFormat.TraditionalOpenSSL,
            NoEncryption(),
        )
    )
    return cert_file, key_file


def resolve_cert_and_key(
    cert_path: str,
    key_path: Optional[str],
    cert_password: Optional[str],
) -> Tuple[str, str, Optional[object]]:
    """
    Resolve certificate and key paths for requests.
    Supports:
      - .crt + .key (PEM): pass both cert_path and key_path
      - .p12: pass cert_path to .p12, cert_password; key_path ignored

    Returns: (cert_file_path, key_file_path, cleanup_fn)
    cleanup_fn is callable to remove temp files (or None).
    """
    cert_p = Path(cert_path)
    if not cert_p.exists():
        raise FileNotFoundError(f"Certificate file not found: {cert_path}")

    if cert_p.suffix.lower() == ".p12":
        if not cert_password:
            raise ValueError("CERT_PASSWORD required when using .p12 certificate")
        cert_file, key_file = _p12_to_pem(cert_p, cert_password)
        tmpdir = cert_file.parent

        def cleanup():
            try:
                import shutil
                shutil.rmtree(tmpdir, ignore_errors=True)
            except Exception:
                pass

        return str(cert_file), str(key_file), cleanup
    else:
        # PEM .crt + .key
        key_p = Path(key_path) if key_path else cert_p.with_suffix(".key")
        if not key_p.exists():
            raise FileNotFoundError(f"Private key file not found: {key_p}")
        return str(cert_p), str(key_p), None
