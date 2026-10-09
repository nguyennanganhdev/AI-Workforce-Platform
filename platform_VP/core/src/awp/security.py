"""Authentication and credential masking, as a pure ASGI middleware.

AgentScope identifies a caller by a self-declared X-User-ID header. Here the
caller proves who they are with a key, and the header is *replaced* by the
tenant's service user, so a caller cannot read another tenant's agents.

Pure ASGI (not BaseHTTPMiddleware) so server-sent event streams are not
buffered.
"""
from __future__ import annotations

import json
import secrets
from dataclasses import dataclass

from .config import Settings


@dataclass(frozen=True)
class Principal:
    tenant: str
    domain: str | None  # set for a domain connector key
    admin: bool


def mask_secrets(value):
    """Hide api keys and other secrets in a JSON-like structure."""
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if isinstance(v, str) and k.lower() in {"api_key", "secret", "token", "password"}:
                out[k] = ("*" * 8 + v[-4:]) if len(v) > 8 else "*" * 8
            else:
                out[k] = mask_secrets(v)
        return out
    if isinstance(value, list):
        return [mask_secrets(v) for v in value]
    return value


def _bearer(headers: list[tuple[bytes, bytes]]) -> str | None:
    for k, v in headers:
        if k == b"authorization" and v[:7].lower() == b"bearer ":
            return v[7:].decode("latin-1").strip()
    return None


class SecurityMiddleware:
    """Resolves the caller, fixes X-User-ID, masks secrets in credential replies."""

    def __init__(self, app, settings: Settings, internal_secret: str) -> None:
        self.app, self.settings, self.internal_secret = app, settings, internal_secret

    def principal(self, key: str | None) -> Principal | None:
        s = self.settings
        if key:
            for known, svc in s.service_keys.items():
                if secrets.compare_digest(known.encode(), key.encode()):
                    return Principal(svc.tenant, svc.domain, False)
            for known, tenant in s.admin_keys.items():
                if secrets.compare_digest(known.encode(), key.encode()):
                    return Principal(tenant, None, True)
        if s.dev_open:
            return Principal("dev", None, True)
        return None

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = list(scope["headers"])
        path = scope["path"]
        internal = any(k == b"x-awp-internal" and secrets.compare_digest(
            v, self.internal_secret.encode()) for k, v in headers)
        if internal:
            return await self.app(scope, receive, send)

        who = self.principal(_bearer(headers))
        if path == "/health" or path == "/platform/v1/health":
            return await self.app(scope, receive, send)
        if who is None:
            return await self._reply(send, 401, {"detail": "missing or unknown key"})
        is_platform = path.startswith("/platform/")
        if not is_platform and not who.admin:
            return await self._reply(send, 403, {"detail": "this key cannot use the agent API"})

        scope = dict(scope)
        scope["state"] = {**scope.get("state", {}), "principal": who}
        if not is_platform:
            # Whatever the caller sent, they act as their tenant's service user.
            headers = [(k, v) for k, v in headers if k != b"x-user-id"]
            headers.append((b"x-user-id", f"awp:{who.tenant}".encode()))
            scope["headers"] = headers

        if path.startswith("/credential"):
            return await self.app(scope, receive, self._masking(send))
        return await self.app(scope, receive, send)

    @staticmethod
    async def _reply(send, status: int, body: dict) -> None:
        raw = json.dumps(body).encode()
        await send({"type": "http.response.start", "status": status,
                    "headers": [(b"content-type", b"application/json"),
                                (b"content-length", str(len(raw)).encode())]})
        await send({"type": "http.response.body", "body": raw})

    @staticmethod
    def _masking(send):
        start: dict = {}
        chunks: list[bytes] = []

        async def wrapper(message):
            if message["type"] == "http.response.start":
                start.update(message)
                return
            if message["type"] != "http.response.body":
                return await send(message)
            chunks.append(message.get("body", b""))
            if message.get("more_body"):
                return
            raw = b"".join(chunks)
            ctype = dict(start.get("headers", [])).get(b"content-type", b"")
            if b"json" in ctype:
                try:
                    raw = json.dumps(mask_secrets(json.loads(raw))).encode()
                except ValueError:
                    pass
            headers = [(k, v) for k, v in start["headers"] if k != b"content-length"]
            headers.append((b"content-length", str(len(raw)).encode()))
            await send({**start, "headers": headers})
            await send({"type": "http.response.body", "body": raw})

        return wrapper
