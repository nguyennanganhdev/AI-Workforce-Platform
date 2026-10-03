"""Opt-in HMAC source proof contract; peers must agree to it before deployment.

Issuers authenticate user/run before signing. Semantic dedup/current business
rights belong to authority/storage. This is not a JWT implementation or proof
that an existing backend supports this format.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from typing import Callable, Mapping

from adapters.backend.errors import AdapterError
from adapters.backend.messages import fingerprint, snapshot


@dataclass(frozen=True)
class SourceProof:
    token: str = field(repr=False)


class HmacSourceAuthentication:
    def __init__(self, *, keys: Mapping[str, bytes], audience: str,
                 header: str, purposes: set[str], max_lifetime: int = 300,
                 clock: Callable[[], float] = time.time) -> None:
        reserved = {"authorization", "content-type", "accept", "idempotency-key",
                    "x-request-id", "x-trace-id", "x-message-id", "x-correlation-id"}
        if (not keys or any(not k or not isinstance(v, bytes) or len(v) < 32 for k, v in keys.items())
                or not audience or not purposes or not purposes <= {"reception", "event", "tool"}
                or type(max_lifetime) is not int or max_lifetime <= 0 or not header
                or not all(c.isascii() and (c.isalnum() or c == "-") for c in header)
                or header.lower() in reserved):
            raise ValueError("invalid proof configuration")
        self._keys = dict(keys)
        self._audience, self._header = audience, header
        self._purposes, self._lifetime, self._clock = frozenset(purposes), max_lifetime, clock

    def _claims(self, authentication: object) -> dict:
        try:
            if not isinstance(authentication, SourceProof) or len(authentication.token) > 32768:
                raise ValueError()
            encoded, signature = authentication.token.split(".")
            raw = base64.b64decode(encoded + "=" * (-len(encoded) % 4), altchars=b"-_", validate=True)
            claims = json.loads(raw)
            if (set(claims) != {"version", "issuer", "audience", "purpose", "subject",
                              "issued_at", "expires_at", "fingerprint", "scope"}
                    or claims["version"] != "1" or claims["audience"] != self._audience
                    or claims["purpose"] not in self._purposes
                    or not isinstance(claims["subject"], str) or not claims["subject"].strip()
                    or type(claims["issued_at"]) is not int or type(claims["expires_at"]) is not int
                    or not isinstance(claims["scope"], dict)):
                raise ValueError()
            expected = hmac.new(self._keys[claims["issuer"]], encoded.encode("ascii"), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, signature):
                raise ValueError()
            now = self._clock()
            if not (claims["issued_at"] <= now < claims["expires_at"]
                    and 0 < claims["expires_at"] - claims["issued_at"] <= self._lifetime):
                raise ValueError()
            return claims
        except Exception:
            raise AdapterError("source_not_authorized") from None

    async def headers(self, authentication: object) -> dict[str, str]:
        self._claims(authentication)
        return {self._header: authentication.token}

    async def headers_for(self, authentication: object, message: Mapping, *, purpose: str) -> dict[str, str]:
        claims = self._claims(authentication)
        wire = snapshot(message)
        scope = wire.get("context", wire)
        required = ({"tenant_id", "aggregate_id"} if purpose == "event"
                    else {"tenant_id", "workspace_id", "ticket_id", "ticket_generation"})
        if (claims["purpose"] != purpose or not isinstance(scope, dict)
                or set(claims["scope"]) != required
                or any(not isinstance(claims["scope"][key], str) or not claims["scope"][key].strip()
                       for key in required - {"ticket_generation"})
                or ("ticket_generation" in required
                    and type(claims["scope"]["ticket_generation"]) is not int)
                or any(claims["scope"][key] != scope.get(key) for key in required)
                or claims["fingerprint"] != fingerprint(wire)):
            raise AdapterError("source_not_authorized")
        return {self._header: authentication.token}


async def proof_headers(provider, authentication: object, message: Mapping, *, purpose: str):
    """Existing providers remain injectable; HMAC binds the entire body."""
    if hasattr(provider, "headers_for"):
        return await provider.headers_for(authentication, message, purpose=purpose)
    return await provider.headers(authentication)
