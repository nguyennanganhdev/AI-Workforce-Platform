"""Signing secrets of provider credentials, encrypted at rest.

``wf_provider_credentials.secret_ref`` holds ``enc:v1:<Fernet token>``; the
key is derived from ``PARTNER_API_KEY_PEPPER`` (already a deployment secret),
so a database dump alone does not reveal the HMAC secrets.
"""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken

PREFIX = "enc:v1:"


def _fernet(pepper: str | None = None) -> Fernet:
    pepper = pepper if pepper is not None else os.getenv("PARTNER_API_KEY_PEPPER", "")
    if len(pepper) < 32:
        raise RuntimeError("PARTNER_API_KEY_PEPPER (32+ characters) is required for provider secrets")
    digest = hashlib.sha256(b"workforce-provider-signing:" + pepper.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def seal(secret: str, pepper: str | None = None) -> str:
    return PREFIX + _fernet(pepper).encrypt(secret.encode("utf-8")).decode("ascii")


def resolve_signing_secret(secret_ref: str, pepper: str | None = None) -> bytes:
    """``secret_resolver`` of ``HmacProviderAuth``."""

    if not secret_ref.startswith(PREFIX):
        raise RuntimeError("unknown provider secret reference")
    try:
        return _fernet(pepper).decrypt(secret_ref[len(PREFIX):].encode("ascii"))
    except InvalidToken as exc:
        raise RuntimeError("provider secret cannot be decrypted") from exc


__all__ = ["resolve_signing_secret", "seal"]
