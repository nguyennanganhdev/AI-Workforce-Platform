"""Read-only fixed endpoints; no fallback to invented business data."""

import asyncio
import math
from decimal import Decimal
from urllib.parse import urlsplit

import httpx

from ..tools.contracts import ReportToolError, uuid_string

EXISTING_ROUTES = frozenset(
    (
        "/catalogs",
        "/reports/filter-options",
        "/reports/supporting-records",
        "/reports/incident-frequency-summary",
        "/reports/employee-feedback",
    )
)


def valid_path(path):
    if type(path) is not str:
        return False
    if path in EXISTING_ROUTES:
        return True
    if not path.startswith("/invoices/"):
        return False
    identifier = path[len("/invoices/") :]
    try:
        return uuid_string(identifier) == identifier
    except (ValueError, AttributeError):
        return False


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
        raise ValueError("Decimal out of range")
    return result


def json_safe_numbers(value):
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
        base_url,
        *,
        client=None,
        timeout_seconds=15.0,
        read_retries=2,
        operation_timeout_seconds=60.0,
        max_pages=100,
        max_records=10000,
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
            raise ValueError("Use HTTPS or loopback HTTP without credentials")
        if (
            not valid_budget(timeout_seconds, 300)
            or not valid_budget(operation_timeout_seconds, 60)
            or type(read_retries) is not int
            or not 0 <= read_retries <= 3
        ):
            raise ValueError("Invalid request budget")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout_seconds
        self.read_retries = read_retries
        self.operation_timeout_seconds = operation_timeout_seconds
        if (
            type(max_pages) is not int
            or not 1 <= max_pages <= 1000
            or type(max_records) is not int
            or not 1 <= max_records <= 100000
        ):
            raise ValueError("Invalid scan limits")
        self.max_pages, self.max_records = max_pages, max_records
        self._owned = client is None
        self.client = client or httpx.AsyncClient(follow_redirects=False)

    async def aclose(self):
        if self._owned:
            await self.client.aclose()

    async def request(self, path, context, *, params=None):
        if not valid_path(path):
            raise ValueError("Invalid read-only report route")
        try:
            async with asyncio.timeout(self.operation_timeout_seconds):
                return await self._request(path, context, params)
        except TimeoutError:
            raise ReportToolError("BACKEND_UNAVAILABLE", retryable=True) from None

    async def _request(self, path, context, params):
        for attempt in range(1 + self.read_retries):
            try:
                response = await self.client.get(
                    self.base_url + path,
                    params=params,
                    headers={
                        "Cookie": context.session_cookie,
                        "Accept": "application/json",
                    },
                    timeout=self.timeout,
                    follow_redirects=False,
                )
            except httpx.TransportError:
                if attempt < self.read_retries:
                    await asyncio.sleep(0.1 * 2**attempt)
                    continue
                raise ReportToolError("BACKEND_UNAVAILABLE", retryable=True) from None
            code = response.status_code
            if code in (502, 503, 504) and attempt < self.read_retries:
                await asyncio.sleep(0.1 * 2**attempt)
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
                raise ReportToolError(error, retryable=code in (429, 502, 503, 504))
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
                raise ReportToolError("BACKEND_CONTRACT_INVALID") from None
        raise AssertionError("Unreachable")
