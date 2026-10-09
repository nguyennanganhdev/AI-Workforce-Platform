"""Async client for the Vinhomes integration API (`/integration/v1/*`).

Contract: vinhome_Recident/docs/domain/HOP_DONG_TICH_HOP.md. The client signs in with the
platform's own secret (X-Client-Id + Bearer ics_...); it never acts on behalf of a resident.

It does not retry by itself. Each error says whether trying again can help, and the caller
(the inbox loop, or the core's result outbox) decides when.
"""
from __future__ import annotations

import os
from typing import Any
from uuid import UUID

import httpx


class VinhomesError(Exception):
    """The domain refused or could not answer."""

    def __init__(self, status: int, code: str, message: str, *, retryable: bool = False,
                 retry_after: float | None = None) -> None:
        super().__init__(f"{status} {code}: {message}")
        self.status, self.code, self.message = status, code, message
        self.retryable, self.retry_after = retryable, retry_after


class Conflict(VinhomesError):
    """409. The snapshot is stale or the domain is in another state. Read again before deciding;
    sending the same thing again will fail the same way."""


class Rejected(VinhomesError):
    """400, 401, 403, 404, 422. The request itself is wrong; do not send it again unchanged."""


class Unavailable(VinhomesError):
    """Network error, 429 or 5xx. The same request may succeed later."""


def _detail(data: Any) -> str:
    """FastAPI's {"detail": ...} is a string or a list of {loc, msg}."""
    if isinstance(data, list):
        return "; ".join(
            f"{'.'.join(str(p) for p in d.get('loc', []))}: {d.get('msg', '')}" if isinstance(d, dict) else str(d)
            for d in data)[:500]
    return str(data)[:500]


def _error_from(r: httpx.Response) -> VinhomesError:
    """Both error shapes: {"error": {code, message, retryable}} and {"detail": ...}."""
    try:
        data = r.json()
    except ValueError:
        data = {}
    err = data.get("error") if isinstance(data, dict) else None
    if isinstance(err, dict):
        code, message = str(err.get("code", r.status_code)), str(err.get("message", ""))[:500]
    else:
        code = {409: "CONFLICT", 422: "VALIDATION_FAILED", 429: "RATE_LIMITED"}.get(r.status_code, str(r.status_code))
        message = _detail(data.get("detail", "")) if isinstance(data, dict) else r.text[:200]
    retry_after = None
    try:
        retry_after = float(r.headers["Retry-After"])
    except (KeyError, ValueError):
        pass
    if r.status_code == 409:
        return Conflict(409, code, message)
    if r.status_code == 429 or r.status_code >= 500:
        return Unavailable(r.status_code, code, message, retryable=True, retry_after=retry_after)
    return Rejected(r.status_code, code, message)


class VinhomesClient:
    def __init__(self, base_url: str, secret: str, client_id: str = "platform", *,
                 timeout: float = 15.0, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.client_id = client_id
        self._http = httpx.AsyncClient(
            base_url=base_url.rstrip("/"), timeout=timeout, transport=transport,
            headers={"X-Client-Id": client_id, "Authorization": f"Bearer {secret}"})

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "VinhomesClient":
        e = os.environ if env is None else env
        url, secret = e.get("VINHOMES_API_URL", ""), e.get("VINHOMES_CLIENT_SECRET", "")
        if not url or not secret:
            raise ValueError("set VINHOMES_API_URL and VINHOMES_CLIENT_SECRET")
        return cls(url, secret, e.get("VINHOMES_CLIENT_ID", "platform"),
                   timeout=float(e.get("VINHOMES_TIMEOUT", 15) or 15))

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _call(self, method: str, path: str, *, params: dict | None = None,
                    json: Any = None, key: str | None = None) -> Any:
        headers = {}
        if key is not None:
            if not 1 <= len(key) <= 160:
                raise ValueError("Idempotency-Key must be 1 to 160 characters")
            headers["Idempotency-Key"] = key
        try:
            r = await self._http.request(method, "/integration/v1" + path, params=params,
                                         json=json, headers=headers)
        except httpx.HTTPError as e:  # connection, timeout, protocol
            raise Unavailable(0, "NETWORK", f"{type(e).__name__}: {e}"[:300], retryable=True) from e
        if r.status_code >= 300:
            raise _error_from(r)
        return r.json()

    # ---- cases ---------------------------------------------------------------
    async def inbox(self, cursor: str | None = None, limit: int = 50) -> dict:
        """{"items": [message...], "next_cursor": str | None}, oldest first."""
        params: dict[str, Any] = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        return await self._call("GET", "/cases/inbox", params=params)

    async def get_case(self, ticket_id: str | UUID) -> dict:
        return await self._call("GET", f"/cases/{ticket_id}")

    async def post_result(self, ticket_id: str | UUID, body: dict, idempotency_key: str) -> dict:
        return await self._call("POST", f"/cases/{ticket_id}/results", json=body, key=idempotency_key)

    async def post_plan(self, ticket_id: str | UUID, body: dict, idempotency_key: str) -> dict:
        return await self._call("POST", f"/cases/{ticket_id}/plans", json=body, key=idempotency_key)

    # ---- knowledge -----------------------------------------------------------
    async def knowledge_pack(self, audience: str = "resident", since: str | None = None) -> dict:
        params = {"audience": audience}
        if since:
            params["since"] = since
        return await self._call("GET", "/knowledge/pack", params=params)
