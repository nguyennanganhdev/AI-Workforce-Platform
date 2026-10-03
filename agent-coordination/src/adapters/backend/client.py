"""Core API client. Routes and credentials are injected; no guessed endpoints."""

from __future__ import annotations

import asyncio
import json
import math
import time
from dataclasses import dataclass
from typing import Any, Callable, Literal, Mapping, Protocol
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


@dataclass(frozen=True)
class ReceptionReceipt:
    message_id: str
    status: str
    data: JSON


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
        observer: Callable[[JSON], None] | None = None,
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
        self._observer = observer

    @property
    def validator(self) -> ContractValidator:
        return self._validator

    async def call_contract(
        self, operation: str, request: Mapping[str, Any], *,
        request_schema: str, response_schema: str, identity: str = "request_id",
        authentication_headers: Mapping[str, str] | None = None,
    ) -> JSON:
        """Explicit internal contracts for lookup/authority/tools, never V1 conversion.

        The composition supplies pinned schemas and actual routes. The peer must
        echo the identity and return accepted/completed + data or a business error.
        This method never generates an ID, retries, or infers business authority.
        """
        if operation not in self._routes:
            raise AdapterError("operation_not_configured")
        if identity not in {"request_id", "message_id", "event_id"}:
            raise ValidationError()
        wire = snapshot(request)
        expected = wire.get(identity)
        if not isinstance(expected, str) or not expected.strip():
            raise ValidationError()
        validate_with(self._validator, request_schema, wire)
        headers = {"X-Request-Id": expected}
        if identity == "message_id":
            headers = {"X-Message-Id": expected}
        if "idempotency_key" in wire:
            key = wire["idempotency_key"]
            if not isinstance(key, str) or not key.strip():
                raise ValidationError()
            headers["Idempotency-Key"] = key
        if "correlation_id" in wire:
            correlation = wire["correlation_id"]
            if not isinstance(correlation, str) or not correlation.strip():
                raise ValidationError()
            headers["X-Correlation-Id"] = correlation
        data = await self._exchange(operation, wire, headers,
                                    authentication_headers=authentication_headers)
        return self._receipt(data, identity, expected, response_schema, operation=operation)["data"]

    async def call(self, operation: str, request: Mapping[str, Any]) -> BackendResult:
        if operation not in self._routes:
            raise AdapterError("operation_not_configured")
        wire = snapshot(request)
        validate_request(wire)
        validate_with(self._validator, "request", wire)
        data = await self._exchange(operation, wire, {
            "Idempotency-Key": wire["idempotency_key"],
            "X-Request-Id": wire["request_id"], "X-Trace-Id": wire["trace_id"],
        })
        data = self._receipt(data, "request_id", wire["request_id"], "response", operation=operation)
        return BackendResult(data["request_id"], data["status"], data["data"])

    async def call_reception(
        self, operation: str, request: Mapping[str, Any], *,
        direction: Literal["input", "output"],
        authentication_headers: Mapping[str, str] | None = None,
    ) -> ReceptionReceipt:
        """V2 only. Output uses an internal routing sidecar, never a V1 envelope.

        Input is the flat Reception message. Output is {message, context}; only
        message is delivered to Reception. Backend atomically enforces current
        rights, pending version, semantic decision dedup and delivery outbox.
        """
        from .reception_messages import validate_input, validate_output, validate_scope

        if operation not in self._routes:
            raise AdapterError("operation_not_configured")
        wire = snapshot(request)
        if direction == "input":
            validate_input(wire)
            validate_with(self._validator, "reception_input", wire)
            if not authentication_headers:
                raise AdapterError("reception_authentication_required")
            message = wire
        elif direction == "output":
            if set(wire) != {"message", "context"}:
                raise ValidationError()
            message = wire["message"]
            validate_output(message)
            validate_scope(message, wire["context"])
            validate_with(self._validator, "reception_output", message)
            validate_with(self._validator, "reception_delivery", wire)
        else:
            raise ValidationError()
        data = await self._exchange(operation, wire, {
            "Idempotency-Key": message["message_id"],
            "X-Message-Id": message["message_id"],
            "X-Correlation-Id": message["correlation_id"],
        }, authentication_headers=authentication_headers)
        data = self._receipt(data, "message_id", message["message_id"], "reception_response", operation=operation)
        return ReceptionReceipt(data["message_id"], data["status"], data["data"])

    async def _exchange(
        self, operation: str, wire: JSON, identity_headers: Mapping[str, str], *,
        authentication_headers: Mapping[str, str] | None = None,
    ) -> JSON:
        try:
            headers = dict(await asyncio.wait_for(self._headers.headers(), self._timeout))
        except Exception:
            raise AdapterError("credentials_unavailable") from None
        if not headers:
            raise AdapterError("credentials_unavailable")
        reserved = {"content-type", "accept", "idempotency-key", "x-request-id", "x-trace-id",
                    "x-message-id", "x-correlation-id"}
        self._check_headers(headers, reserved)
        if authentication_headers is not None:
            delegated = dict(authentication_headers)
            self._check_headers(delegated, reserved | {key.lower() for key in headers})
            headers.update(delegated)
        headers.update({
            "Content-Type": "application/json", "Accept": "application/json",
            **identity_headers,
        })
        if any("\r" in v or "\n" in v for v in headers.values()):
            raise ValidationError()
        body = json.dumps(wire, ensure_ascii=False, allow_nan=False).encode("utf-8")
        started = time.monotonic()
        try:
            response = await asyncio.wait_for(self._transport.post(
                self._origin + self._routes[operation], headers=headers,
                body=body, timeout=self._timeout,
            ), timeout=self._timeout)
        except TimeoutError:
            self._observe(operation, wire, started, None)
            raise AdapterError("timeout", retryable=True, outcome_unknown=True) from None
        except OSError:
            self._observe(operation, wire, started, None)
            raise AdapterError("unavailable", retryable=True, outcome_unknown=True) from None
        self._observe(operation, wire, started, response.status)
        if len(response.body) > self._max_response:
            raise AdapterError("invalid_backend_response", outcome_unknown=True)
        if not 200 <= response.status < 300:
            code = HTTP_ERRORS.get(response.status, "unavailable" if response.status >= 500
                                   else "unexpected_http_status")
            raise AdapterError(code, retryable=response.status == 429 or response.status >= 500,
                               outcome_unknown=response.status >= 500)
        try:
            data = json.loads(response.body)
            return snapshot(data)
        except (ValueError, TypeError, ValidationError):
            raise AdapterError("invalid_backend_response", outcome_unknown=True) from None

    def _observe(self, operation: str, wire: JSON, started: float, status: int | None) -> None:
        if self._observer is None:
            return
        message = wire.get("message") if isinstance(wire.get("message"), dict) else wire
        metadata = {key: message[key] for key in (
            "request_id", "message_id", "correlation_id", "task_id", "run_id"
        ) if key in message}
        metadata.update(operation=operation, phase="http", http_status=status,
                        elapsed_seconds=time.monotonic() - started)
        # HTTP status is transport evidence, never a successful business outcome.
        self._emit(metadata)

    def _emit(self, metadata: JSON) -> None:
        if self._observer is None:
            return
        try:
            self._observer(metadata)
        except Exception:
            pass  # a diagnostic sink cannot cause a successful mutation to retry

    @staticmethod
    def _check_headers(headers: Mapping[str, str], reserved: set[str]) -> None:
        seen: set[str] = set()
        for name, value in headers.items():
            if (not isinstance(name, str) or not isinstance(value, str)
                    or not name or not value or name.lower() in reserved
                    or name.lower() in seen or any(c in name + value for c in "\r\n")):
                raise AdapterError("invalid_credentials_headers")
            seen.add(name.lower())

    def _receipt(self, data: JSON, identity: str, expected: str, schema: str, *,
                 operation: str | None = None) -> JSON:
        try:
            validate_with(self._validator, schema, data)
            if data.get(identity) != expected:
                raise ValidationError()
            if data.get("status") == "error":
                error = data.get("error")
                if not isinstance(error, dict) or error.get("code") not in ERROR_CODES:
                    raise ValidationError()
                if operation is not None:
                    self._emit({"operation": operation, "phase": "receipt", identity: expected,
                                "status": "error", "code": error["code"]})
                raise AdapterError(error["code"], retryable=error.get("retryable") is True,
                                   outcome_unknown=error["code"] == "unavailable")
            if (data.get("status") not in ("accepted", "completed")
                    or not isinstance(data.get("data"), dict) or "error" in data):
                raise ValidationError()
        except (ValueError, TypeError, ValidationError):
            if operation is not None:
                self._emit({"operation": operation, "phase": "receipt", identity: expected,
                            "status": "error", "code": "invalid_backend_response", "outcome_unknown": True})
            raise AdapterError("invalid_backend_response", outcome_unknown=True) from None
        if operation is not None:
            self._emit({"operation": operation, "phase": "receipt", identity: expected, "status": data["status"]})
        return data
