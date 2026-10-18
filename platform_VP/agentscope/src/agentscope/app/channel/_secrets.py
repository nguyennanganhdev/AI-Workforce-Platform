"""Channel credential secrets (bot tokens, app secrets), encrypted at rest.

A credential field marked ``format: password`` is stored as
``enc:v1:<Fernet token>``. The key is derived from ``CHANNEL_CREDENTIALS_KEY``,
or else ``PARTNER_API_KEY_PEPPER`` (both deployment secrets, 32+ characters),
so a storage dump alone does not reveal a bot token. Without either key the
value is stored as given, as before; a stored plaintext value keeps working.
"""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken

PREFIX = "enc:v1:"


def _fernet() -> Fernet | None:
    key = os.getenv("CHANNEL_CREDENTIALS_KEY") or os.getenv("PARTNER_API_KEY_PEPPER") or ""
    if len(key) < 32:
        return None
    digest = hashlib.sha256(b"agentscope-channel-credentials:" + key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def secret_fields(credentials_model) -> set[str]:
    properties = credentials_model.model_json_schema().get("properties", {})
    return {name for name, spec in properties.items() if spec.get("format") == "password"}


def seal_credentials(credentials: dict, secrets: set[str]) -> dict:
    fernet = _fernet()
    if fernet is None:
        return dict(credentials)
    return {
        name: PREFIX + fernet.encrypt(value.encode("utf-8")).decode("ascii")
        if name in secrets and isinstance(value, str) and value and not value.startswith(PREFIX)
        else value
        for name, value in credentials.items()
    }


def open_credentials(credentials: dict) -> dict:
    sealed = [v for v in credentials.values() if isinstance(v, str) and v.startswith(PREFIX)]
    if not sealed:
        return dict(credentials)
    fernet = _fernet()
    if fernet is None:
        raise RuntimeError("Channel credentials are encrypted but CHANNEL_CREDENTIALS_KEY is not configured")
    try:
        return {
            name: fernet.decrypt(value[len(PREFIX):].encode("ascii")).decode("utf-8")
            if isinstance(value, str) and value.startswith(PREFIX) else value
            for name, value in credentials.items()
        }
    except InvalidToken as exc:
        raise RuntimeError("Channel credentials cannot be decrypted with the configured key") from exc
