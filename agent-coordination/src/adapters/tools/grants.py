"""Scoped callback grants supplied by a trusted published-release resolver.

The callback peer must reauthorize current grants and fence revoked executions.
This adapter never accepts grants or endpoint names from a model/request.
"""
from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from typing import Mapping, Protocol

from adapters.backend.client import BackendClient
from adapters.backend.errors import AdapterError, ValidationError
from adapters.backend.messages import snapshot, text, validate_context


@dataclass(frozen=True)
class ToolGrant:
    tool: str
    operation: str
    request_schema: str
    response_schema: str
    context: Mapping
    agent_version_id: str
    task_id: str
    run_id: str


class ToolGrantResolver(Protocol):
    async def resolve(self, request: Mapping, authentication: object) -> ToolGrant:
        """Verify current release/run assertion, grants, scope and revocation."""
        ...


class RemoteToolGrantResolver:
    def __init__(self, backend: BackendClient, *, authentication):
        if authentication is None:
            raise ValueError("grant source authentication required")
        self._backend, self._auth = backend, authentication

    async def resolve(self, request: Mapping, authentication: object) -> ToolGrant:
        from adapters.reception.authentication import proof_headers
        from adapters.backend.messages import fingerprint
        wire = snapshot(request)
        headers = await proof_headers(self._auth, authentication, wire, purpose="tool")
        data = await self._backend.call_contract("tool.grant.verify", wire,
            request_schema="tool_callback_request", response_schema="tool_grant_response",
            authentication_headers=headers)
        try:
            if set(data) != {"request_fingerprint", "grant"} or data["request_fingerprint"] != fingerprint(wire):
                raise ValueError()
            grant = data["grant"]
            if (set(grant) != {"tool", "operation", "request_schema", "response_schema", "context",
                               "agent_version_id", "task_id", "run_id"}
                    or any(not text(grant[key]) for key in set(grant) - {"context"})):
                raise ValueError()
            validate_context(grant["context"])
            return ToolGrant(**grant)
        except Exception:
            raise AdapterError("invalid_grant_response") from None


class GrantedToolClient:
    def __init__(self, backend: BackendClient, *, resolver: ToolGrantResolver,
                 authentication, allowed_operations: set[str], timeout: float = 15):
        if (not allowed_operations or authentication is None or resolver is None
                or not math.isfinite(timeout) or timeout <= 0):
            raise ValueError("trusted grants/authentication/operations required")
        self._backend, self._resolver, self._auth = backend, resolver, authentication
        self._operations, self._timeout = frozenset(allowed_operations), timeout

    async def invoke(self, request: Mapping, *, authentication: object) -> dict:
        from adapters.reception.authentication import proof_headers
        wire = snapshot(request)
        required = {"request_id", "idempotency_key", "correlation_id", "context",
                    "tool", "input", "agent_version_id", "task_id", "run_id"}
        if (set(wire) != required or not isinstance(wire["input"], dict)
                or any(not text(wire[key]) for key in required - {"input", "context"})):
            raise ValidationError()
        validate_context(wire["context"])
        try:
            headers = await asyncio.wait_for(
                proof_headers(self._auth, authentication, wire, purpose="tool"), self._timeout)
            grant = await asyncio.wait_for(
                self._resolver.resolve(snapshot(wire), authentication), self._timeout)
        except AdapterError:
            raise
        except TimeoutError:
            raise AdapterError("grant_verification_unavailable", retryable=True) from None
        except Exception:
            raise AdapterError("tool_not_authorized") from None
        if not isinstance(grant, ToolGrant):
            raise AdapterError("tool_not_authorized")
        try:
            validate_context(snapshot(grant.context))
        except AdapterError:
            raise AdapterError("tool_not_authorized") from None
        if (grant.operation not in self._operations
                or grant.tool != wire["tool"] or snapshot(grant.context) != wire["context"]
                or any(getattr(grant, key) != wire[key] for key in ("agent_version_id", "task_id", "run_id"))):
            raise AdapterError("tool_not_authorized")
        return await self._backend.call_contract(grant.operation, wire,
            request_schema=grant.request_schema, response_schema=grant.response_schema,
            authentication_headers=headers)
