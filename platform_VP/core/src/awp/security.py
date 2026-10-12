"""Authentication and credential masking, as a pure ASGI middleware.

AgentScope identifies a caller by a self-declared X-User-ID header. Here the
caller proves who they are with a key, and the header is *replaced* by the
tenant's service user, so a caller cannot read another tenant's agents.

Pure ASGI (not BaseHTTPMiddleware) so server-sent event streams are not
buffered.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass

from .config import Settings
from .console import is_console


MANAGER_PREFIX = "mk_"  # a manager's operator key; it is looked up in the database, never among the admin keys


@dataclass(frozen=True)
class Principal:
    """An admin of one tenant, or (with `manager_id`) an operator of one management account of that tenant: that one
    reaches only the partner admin API and the profile list, and there only what belongs to its own routes."""

    tenant: str
    manager_id: str | None = None
    label: str = "admin"  # who, for the record of a release: which admin key (a short print of it), or the dev fallback

    @property
    def actor(self) -> str:
        return f"manager:{self.manager_id}" if self.manager_id else self.label


def manager_may(method: str, path: str) -> bool:
    """The paths a manager's key may reach at all. What it sees there is decided by each endpoint (workforce/adminkit.py);
    everything else, the AgentScope API included, is closed to it."""
    return (path.startswith("/platform/v1/wf/") or (method == "GET" and path == "/platform/v1/profiles")
            or path.startswith("/platform/v1/profiles/"))  # evaluating and releasing the profiles of its own routes


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

    def __init__(self, app, settings: Settings, internal_secret: str, managers=None) -> None:
        self.app, self.settings, self.internal_secret = app, settings, internal_secret
        self.managers = managers  # async (token) -> Principal | None, for keys that start with MANAGER_PREFIX

    def principal(self, key: str | None) -> Principal | None:
        s = self.settings
        if key:
            for known, tenant in s.admin_keys.items():
                if secrets.compare_digest(known.encode(), key.encode()):
                    # keyed with the deployment's secret: the label is stored and shown (also to manager keys), and
                    # must not be something a guessed admin key can be checked against
                    mark = hmac.new(s.secret_key.encode(), key.encode(), hashlib.sha256).hexdigest()[:8]
                    return Principal(tenant, label="admin:" + mark)
        # A partner key is never a dev key, even when dev mode lets keyless calls in.
        if s.dev_open and not (key or "").startswith("dp_"):
            return Principal("dev", label="dev")
        return None

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = list(scope["headers"])
        path = scope["path"]
        if path == "/workforce" or path.startswith("/workforce/"):
            return await self.app(scope, receive, send)  # the router authenticates (ApiKey)
        internal = any(k == b"x-awp-internal" and secrets.compare_digest(
            v, self.internal_secret.encode()) for k, v in headers)
        if internal:
            return await self.app(scope, receive, send)
        if is_console(scope["method"], path):
            return await self.app(scope, receive, send)  # the static page: it holds no data, its API calls carry the key

        if any(k == b"authorization" and v[:7].lower() == b"apikey " for k, v in headers):
            return await self._reply(send, 401, {"detail": "partner keys only work on /workforce"})
        if path == "/health" or path == "/platform/v1/health":
            return await self.app(scope, receive, send)
        token = _bearer(headers)
        if (token or "").startswith(MANAGER_PREFIX):  # never an admin key and never the dev fallback
            who = await self.managers(token) if self.managers is not None else None
        else:
            who = self.principal(token)
        if who is None:
            return await self._reply(send, 401, {"detail": "missing or unknown key"})
        if who.manager_id and not manager_may(scope["method"], path):
            return await self._reply(send, 403, {"detail": "a manager's key does not open this"})
        is_platform = path.startswith("/platform/")

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
