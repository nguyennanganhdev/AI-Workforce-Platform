"""ApiKey authentication for the partner API (contract 5.1, 6).

The router authenticates; SecurityMiddleware lets /workforce/ through. A
customer key and a provider key are different kinds and never cross over.
"""
from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable

from fastapi import Request
from sqlalchemy import select

from . import crypto, tables as t
from .common import now
from .errors import WorkforceError, unauthenticated

CUSTOMER_OPS = ("submit_request", "reply", "read_result", "receive_events", "submit_consent",
                "close_workflow", "confirm_route", "sync_residence",
                "attach_asset")  # the last one is the image extension (spec A3): of use only to a client with that capability
PROVIDER_OPS = ("publish_job_event", "read_event_receipt")
# What a confirmed route lets a customer key do at run time (contract 8.1).
RUNTIME_OPS = CUSTOMER_OPS[:6]
OPS = {"customer": CUSTOMER_OPS, "provider": PROVIDER_OPS}


@dataclass(frozen=True)
class Client:
    id: str
    tenant: str
    domain: str
    environment: str
    capabilities: tuple[str, ...]


@dataclass(frozen=True)
class PartnerPrincipal:
    client: Client
    key_id: str
    kind: str
    operations: frozenset[str]
    routes: tuple[str, ...]  # ("*",) or route ids
    integration_id: str | None
    request_id: str

    def covers(self, route_id: str) -> bool:
        return "*" in self.routes or route_id in self.routes


def route_denied(**details) -> WorkforceError:
    return WorkforceError("ROUTE_NOT_AUTHORIZED", 403,
                          "Request is not authorized for the configured management route.", details)


class RateLimiter:
    """Sliding one-minute window per key, in this process."""

    def __init__(self, per_minute: int, clock: Callable[[], float] = time.monotonic) -> None:
        self.per_minute, self.clock = per_minute, clock
        self._hits: dict[str, deque[float]] = {}

    def hit(self, key: str) -> int | None:
        """None when allowed, else the seconds until the next call would be."""
        if self.per_minute <= 0:
            return None
        t0, hits = self.clock(), self._hits.setdefault(key, deque())
        while hits and hits[0] <= t0 - 60:
            hits.popleft()
        if len(hits) >= self.per_minute:
            return max(1, math.ceil(hits[0] + 60 - t0))
        hits.append(t0)
        return None


def lacks(operation: str) -> WorkforceError:
    return WorkforceError("PERMISSION_DENIED", 403, "This credential lacks the required operation.",
                          {"operation": operation})


def need(p: PartnerPrincipal, operation: str) -> None:
    if operation not in p.operations:
        raise lacks(operation)


async def authenticate(request: Request, kind: str, operation: str | None) -> PartnerPrincipal:
    """`operation=None` authenticates only: the caller checks the operation (when it depends on the body)."""
    ctx = request.app.state.wf
    parsed = crypto.parse_authorization(request.headers.get("authorization"))
    if parsed is None:
        raise unauthenticated()
    key_id, secret = parsed
    async with ctx.db.engine.connect() as conn:
        key = (await conn.execute(select(t.keys).where(t.keys.c.key_id == key_id))).mappings().first()
        # Always compare, even for an unknown id, so a miss looks like a hit.
        if not crypto.verify_secret(secret, key["secret_hash"] if key else None):
            raise unauthenticated()
        if key["status"] != "active":
            raise unauthenticated("revoked")
        if key["expires_at"] is not None and key["expires_at"] <= now():
            raise unauthenticated("expired")
        integration_id, client_id = key["integration_id"], key["client_id"]
        if integration_id:
            integ = (await conn.execute(select(t.integrations).where(
                t.integrations.c.id == integration_id))).mappings().first()
            if integ is None or integ["status"] != "active":
                raise unauthenticated("integration_disabled")
            client_id = integ["client_id"]
        row = (await conn.execute(select(t.clients).where(t.clients.c.id == client_id))).mappings().first()
    if row is None or row["status"] != "active":
        raise unauthenticated("client_disabled")

    wait = ctx.limiter.hit(key_id)
    if wait is not None:
        raise WorkforceError("RATE_LIMITED", 429, "Too many requests for this credential.",
                             {"retry_after_seconds": wait}, retryable=True,
                             headers={"Retry-After": str(wait)})
    if key["kind"] != kind:
        raise WorkforceError("PERMISSION_DENIED", 403, "This credential cannot be used on this endpoint.",
                             {"reason": "wrong_credential_kind"})
    ops = frozenset(key["operations"])
    if operation is not None and operation not in ops:
        raise lacks(operation)
    return PartnerPrincipal(
        client=Client(row["id"], row["tenant"], row["domain"], row["environment"],
                      tuple(row["capabilities"] or ())),
        key_id=key_id, kind=kind, operations=ops, routes=tuple(key["routes"]),
        integration_id=integration_id, request_id=request.state.request_id)


def require(operation: str, kind: str = "customer"):
    """A FastAPI dependency: the authenticated principal, who must hold `operation`."""
    if operation not in OPS[kind]:
        raise ValueError(f"{operation} is not a {kind} operation")

    async def dependency(request: Request) -> PartnerPrincipal:
        return await authenticate(request, kind, operation)

    return dependency


async def still_valid(ctx, p: PartnerPrincipal, operations: tuple[str, ...], route_id: str) -> bool:
    """Re-check a credential that is already in use (a long SSE stream): still active, unexpired,
    holding `operations`, covering the route, with its client and integration still active."""
    async with ctx.db.engine.connect() as conn:
        key = (await conn.execute(select(t.keys).where(t.keys.c.key_id == p.key_id))).mappings().first()
        if key is None or key["status"] != "active":
            return False
        if key["expires_at"] is not None and key["expires_at"] <= now():
            return False
        client = (await conn.execute(select(t.clients.c.status).where(
            t.clients.c.id == p.client.id))).first()
    covers = "*" in key["routes"] or route_id in key["routes"]
    return (client is not None and client[0] == "active" and covers
            and all(op in key["operations"] for op in operations))
