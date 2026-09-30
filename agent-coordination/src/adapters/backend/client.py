"""Core API client. Routes and credentials are injected; no guessed endpoints."""

from __future__ import annotations

import asyncio
import json
import math
from dataclasses import dataclass
from typing import Any, Mapping, Protocol
from urllib.parse import urlsplit

from .errors import AdapterError, ValidationError
from .messages import ContractValidator, JSON, snapshot, validate_request, validate_with


@dataclass(frozen=True)
class HttpResponse:
    status: int
    body: bytes


class HttpTransport(Protocol):
    async def post(
        self, url: str, *, headers: Mapping[str, str], body: bytes, timeout: float
    ) -> HttpResponse: ...


class HeaderProvider(Protocol):
    async def headers(self) -> Mapping[str, str]:
        """Return current service credentials; never derived from request payload."""
        ...


@dataclass(frozen=True)
class BackendResult:
    request_id: str
    status: str
    data: JSON
    # 'completed' means this API operation completed, not ticket closure.


ERROR_CODES = frozenset({
    "forbidden", "not_found", "validation_error", "conflict", "stale_version",
    "routing_unresolved", "policy_missing", "rate_limited", "unavailable",
})
HTTP_ERRORS = {
    400: "validation_error", 401: "forbidden", 403: "forbidden", 404: "not_found",
    409: "conflict", 422: "validation_error", 429: "rate_limited",
}


class BackendClient:
    def __init__(
        self, *, base_url: str, routes: Mapping[str, str], transport: HttpTransport,
        headers: HeaderProvider, validator: ContractValidator, timeout: float = 15,
        allow_http: bool = False, max_response_bytes: int = 1_048_576,
    ) -> None:
        parts = urlsplit(base_url)
        if (parts.scheme not in ({"https", "http"} if allow_http else {"https"})
                or not parts.hostname or parts.username or parts.password
                or parts.query or parts.fragment or parts.path not in ("", "/")):
            raise ValueError("base_url must be an origin without credentials")
        if not math.isfinite(timeout) or timeout <= 0 or max_response_bytes <= 0:
            raise ValueError("invalid timeout/response limit")
        for path in routes.values():
            parsed = urlsplit(path)
            if (not path.startswith("/") or path.startswith("//") or parsed.scheme
                    or parsed.netloc or parsed.query or parsed.fragment
                    or "\\" in path or any(ord(c) < 33 for c in path)
                    or any(segment in (".", "..") for segment in path.split("/"))):
                raise ValueError("routes must be absolute paths on the configured origin")
        self._origin = base_url.rstrip("/")
        self._routes = dict(routes)
        self._transport = transport
        self._headers = headers
        self._validator = validator
        self._timeout = timeout
        self._max_response = max_response_bytes

    async def call(self, operation: str, request: Mapping[str, Any]) -> BackendResult:
        if operation not in self._routes:
            raise AdapterError("operation_not_configured")
        wire = snapshot(request)
        validate_request(wire)
        validate_with(self._validator, "request", wire)
        try:
            headers = dict(await self._headers.headers())
        except Exception:
            raise AdapterError("credentials_unavailable") from None
        if not headers:
            raise AdapterError("credentials_unavailable")
        reserved = {"content-type", "accept", "idempotency-key", "x-request-id", "x-trace-id"}
        for name, value in headers.items():
            if (not isinstance(name, str) or not isinstance(value, str)
                    or not name or not value or name.lower() in reserved
                    or any(c in name + value for c in "\r\n")):
                raise AdapterError("invalid_credentials_headers")
        headers.update({
            "Content-Type": "application/json", "Accept": "application/json",
            "Idempotency-Key": wire["idempotency_key"],
            "X-Request-Id": wire["request_id"], "X-Trace-Id": wire["trace_id"],
        })
        if any("\r" in v or "\n" in v for v in headers.values()):
            raise ValidationError()
        body = json.dumps(wire, ensure_ascii=False, allow_nan=False).encode("utf-8")
        try:
            response = await asyncio.wait_for(self._transport.post(
                self._origin + self._routes[operation], headers=headers,
                body=body, timeout=self._timeout,
            ), timeout=self._timeout)
        except TimeoutError:
            raise AdapterError("timeout", retryable=True, outcome_unknown=True) from None
        except OSError:
            raise AdapterError("unavailable", retryable=True, outcome_unknown=True) from None
        if len(response.body) > self._max_response:
            raise AdapterError("invalid_backend_response", outcome_unknown=True)
        if not 200 <= response.status < 300:
            code = HTTP_ERRORS.get(response.status, "unavailable" if response.status >= 500
                                   else "unexpected_http_status")
            raise AdapterError(code, retryable=response.status == 429 or response.status >= 500,
                               outcome_unknown=response.status >= 500)
        try:
            data = json.loads(response.body)
            data = snapshot(data)
            validate_with(self._validator, "response", data)
            if data.get("request_id") != wire["request_id"]:
                raise ValidationError()
            if data.get("status") == "error":
                error = data.get("error")
                if not isinstance(error, dict) or error.get("code") not in ERROR_CODES:
                    raise ValidationError()
                raise AdapterError(error["code"], retryable=error.get("retryable") is True,
                                   outcome_unknown=error["code"] == "unavailable")
            if (data.get("status") not in ("accepted", "completed")
                    or not isinstance(data.get("data"), dict) or "error" in data):
                raise ValidationError()
        except (ValueError, TypeError, ValidationError):
            raise AdapterError("invalid_backend_response", outcome_unknown=True) from None
        return BackendResult(data["request_id"], data["status"], data["data"])
