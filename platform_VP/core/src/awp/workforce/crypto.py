"""API key parsing, hashing and the Fernet seal for secrets that must be read back.

API secrets are random and long, so a plain SHA-256 is enough and nothing but
the hash is stored. Provider signing secrets and MCP headers are different:
the platform has to use them, so they are sealed with `AWP_SECRET_KEY` (A7).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets

from cryptography.fernet import Fernet, InvalidToken

_KEY = re.compile(r"^ApiKey dp_([A-Za-z0-9_-]{6,64})\.([A-Za-z0-9_-]{16,128})$", re.IGNORECASE)
# What an unknown key id is compared against, so a miss costs the same as a hit.
_DUMMY = hashlib.sha256(b"awp-no-such-key").hexdigest()


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def verify_secret(secret: str, stored_hash: str | None) -> bool:
    return hmac.compare_digest(hash_secret(secret), stored_hash or _DUMMY) and stored_hash is not None


def parse_authorization(header: str | None) -> tuple[str, str] | None:
    """`ApiKey dp_<key-id>.<secret>` -> (key_id, secret); None when it is not one."""
    m = _KEY.match(header.strip()) if header else None
    return (m.group(1), m.group(2)) if m else None


def new_api_key() -> tuple[str, str, str]:
    """(key_id, secret, the full `dp_<id>.<secret>` shown once)."""
    key_id, secret = secrets.token_hex(8), secrets.token_urlsafe(32)
    return key_id, secret, f"dp_{key_id}.{secret}"


def new_signing_secret() -> tuple[str, str]:
    return "sk_" + secrets.token_hex(8), secrets.token_urlsafe(32)


class SecretKeyMissing(RuntimeError):
    """AWP_SECRET_KEY is not set and the platform is not in dev mode."""


# A fixed key for AWP_DEV_OPEN only: dev data stays readable across restarts.
_DEV_KEY = base64.urlsafe_b64encode(hashlib.sha256(b"awp-dev-open-secret-key").digest())


class Sealer:
    """Fernet seal. Without a key it refuses to seal, so no secret is stored in clear."""

    def __init__(self, secret_key: str = "", dev_open: bool = False) -> None:
        if secret_key:
            self._fernet = Fernet(secret_key.encode())  # a bad key fails at startup
        else:
            self._fernet = Fernet(_DEV_KEY) if dev_open else None

    @property
    def ready(self) -> bool:
        return self._fernet is not None

    def seal(self, plain: str) -> str:
        if self._fernet is None:
            raise SecretKeyMissing("AWP_SECRET_KEY is not set")
        return self._fernet.encrypt(plain.encode()).decode()

    def open(self, token: str) -> str:
        if self._fernet is None:
            raise SecretKeyMissing("AWP_SECRET_KEY is not set")
        try:
            return self._fernet.decrypt(token.encode()).decode()
        except InvalidToken as e:
            raise ValueError("sealed secret cannot be opened with this key") from e
