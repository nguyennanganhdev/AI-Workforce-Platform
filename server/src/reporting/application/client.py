"""Fixed HTTP routes, bounded total deadline, no model-selected URL or SQL."""

from __future__ import annotations

import asyncio
import math
from decimal import Decimal
from urllib.parse import urlsplit

import httpx

from ..tools.contracts import ReportToolError, RuntimeContext


def valid_budget(value, maximum):
    return type(value) in (int, float) and 0 < value <= maximum and math.isfinite(value)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def invalid_constant(value):
    raise ValueError("Non-finite JSON constant")


def exact_decimal(value):
    result = Decimal(value)
    if len(value) > 128 or result.adjusted() > 38 or result.as_tuple().exponent < -38:
        raise ValueError("JSON decimal outside supported range")
    return result


def json_safe_numbers(value):
    # Keep all decoded fractional numbers exact and safe for runtime JSON serialization.
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, dict):
        return {key: json_safe_numbers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe_numbers(item) for item in value]
    return value


class ReportBackend:
    def __init__(
        self,
        base_url: str,
        *,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 15.0,
        read_retries: int = 2,
        operation_timeout_seconds: float = 60.0,
    ):
        url = urlsplit(base_url)
        if (
            url.scheme not in ("http", "https")
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
            or (
                url.scheme == "http"
                and url.hostname not in ("localhost", "127.0.0.1", "::1")
            )
        ):
            raise ValueError("Use HTTPS, or HTTP on loopback, without URL credentials")
        if (
            not valid_budget(timeout_seconds, 300)
            or not valid_budget(operation_timeout_seconds, 60)
            or type(read_retries) is not int
            or not 0 <= read_retries <= 3
        ):
            raise ValueError("Invalid request budget")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout_seconds
        self.operation_timeout_seconds = operation_timeout_seconds
        self.read_retries = read_retries
        self._owned = client is None
        self.client = client or httpx.AsyncClient(follow_redirects=False)

    async def aclose(self):
        if self._owned:
            await self.client.aclose()

    async def request(
        self,
        method: str,
        path: str,
        context: RuntimeContext,
        *,
        params: dict | None = None,
        body: dict | None = None,
    ) -> dict:
        if (
            method not in ("GET", "POST")
            or not path.startswith("/reports/")
            or ".." in path
        ):
            raise ValueError("Invalid report route")
        try:
            async with asyncio.timeout(self.operation_timeout_seconds):
                return await self._request(
                    method, path, context, params=params, body=body
                )
        except TimeoutError:
            raise ReportToolError(
                "BACKEND_UNAVAILABLE",
                retryable=True,
                execution_unknown=method == "POST",
            ) from None

    async def _request(self, method, path, context, *, params, body):
        write = method == "POST"
        attempts = 1 if write else 1 + self.read_retries
        for attempt in range(attempts):
            try:
                response = await self.client.request(
                    method,
                    self.base_url + path,
                    params=params,
                    json=body,
                    headers={
                        "Cookie": context.session_cookie,
                        "Accept": "application/json",
                    },
                    timeout=self.timeout,
                    follow_redirects=False,
                )
            except httpx.TransportError:
                if not write and attempt + 1 < attempts:
                    await asyncio.sleep(0.1 * (2**attempt))
                    continue
                raise ReportToolError(
                    "BACKEND_UNAVAILABLE", retryable=True, execution_unknown=write
                ) from None
            code = response.status_code
            if not write and code in (502, 503, 504) and attempt + 1 < attempts:
                await asyncio.sleep(0.1 * (2**attempt))
                continue
            if not 200 <= code < 300:
                error = {
                    401: "AUTHENTICATION_REQUIRED",
                    403: "REPORT_SCOPE_FORBIDDEN",
                    404: "REPORT_NOT_FOUND",
                    409: "REPORT_CONFLICT",
                    422: "BACKEND_INPUT_REJECTED",
                    429: "RATE_LIMITED",
                }.get(
                    code, "BACKEND_UNAVAILABLE" if code >= 500 else "BACKEND_HTTP_ERROR"
                )
                raise ReportToolError(
                    error,
                    retryable=code in (429, 502, 503, 504),
                    execution_unknown=write and (code >= 500 or 300 <= code < 400),
                )
            try:
                value = response.json(
                    object_pairs_hook=unique_object,
                    parse_constant=invalid_constant,
                    parse_float=exact_decimal,
                )
                if type(value) is not dict:
                    raise ValueError
                return json_safe_numbers(value)
            except (ValueError, RecursionError):
                raise ReportToolError(
                    "BACKEND_CONTRACT_INVALID", execution_unknown=write
                ) from None
        raise AssertionError("Unreachable")
