"""Validated HTTP tool port for the OpenBot backend.

The endpoint paths are configurable. Inputs/results follow the PH16 consumer
proposal; the legacy V1 graph needs an explicit owner-reviewed migration.
Every mutation carries the caller's stable key; retries reuse the same body.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import httpx

from .validation import ToolContractError, prepare_call, validate_result


@dataclass(frozen=True)
class BackendToolConfig:
    base_url: str
    service_token: str = field(repr=False)
    operation_path: str = "/internal/reception/operations/execute"
    reconcile_path: str = "/internal/reception/operations/reconcile"
    timeout_seconds: float = 10.0
    max_attempts: int = 2

    def __post_init__(self):
        if not self.base_url.startswith(("http://", "https://")):
            raise ToolContractError("BACKEND_BASE_URL_INVALID")
        if not self.service_token.strip():
            raise ToolContractError("BACKEND_SERVICE_TOKEN_REQUIRED")
        if self.timeout_seconds <= 0 or self.max_attempts < 1:
            raise ToolContractError("BACKEND_RETRY_CONFIG_INVALID")


class BackendToolPort:
    """Internal transport. Graph consumers should use ReceptionTools methods."""

    def __init__(
        self,
        config: BackendToolConfig,
        client: httpx.AsyncClient | None = None,
    ):
        self.config = config
        self._owned_client = client is None
        self.client = client or httpx.AsyncClient(
            base_url=config.base_url,
            timeout=config.timeout_seconds,
            follow_redirects=False,
        )

    async def aclose(self):
        if self._owned_client:
            await self.client.aclose()

    async def invoke(self, request: dict[str, Any]) -> dict[str, Any]:
        return await self._validated_post(self.config.operation_path, request)

    async def reconcile(self, request: dict[str, Any]) -> dict[str, Any]:
        return await self._validated_post(self.config.reconcile_path, request)

    async def _validated_post(
        self, path: str, request: dict[str, Any]
    ) -> dict[str, Any]:
        call, value, body = prepare_call(request)
        raw = await self._post(path, body, call.idempotencyKey)
        result = validate_result(call.operation, value, call.context, raw)
        return result.model_dump(mode="json", exclude_unset=True)

    async def _post(self, path: str, body: dict, key: str) -> dict:
        headers = {
            "Authorization": "Bearer " + self.config.service_token,
            "Idempotency-Key": key,
            "Content-Type": "application/json",
        }
        last_response: httpx.Response | None = None
        for attempt in range(self.config.max_attempts):
            try:
                response = await self.client.post(path, json=body, headers=headers)
                last_response = response
                if response.status_code not in (502, 503, 504):
                    return self._decode(response)
            except (httpx.TimeoutException, httpx.TransportError):
                if attempt + 1 == self.config.max_attempts:
                    break
            if attempt + 1 < self.config.max_attempts:
                await asyncio.sleep(0)
        if last_response is not None:
            return self._decode(last_response)
        return {
            "kind": "failure",
            "code": "BACKEND_RESPONSE_UNKNOWN",
            "retryable": False,
            "outcome": "unknown",
        }

    @staticmethod
    def _decode(response: httpx.Response) -> dict:
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if 200 <= response.status_code < 300:
            if not isinstance(payload, dict):
                raise ToolContractError("BACKEND_RESPONSE_INVALID")
            return payload
        if isinstance(payload, dict) and payload.get("kind") == "failure":
            return payload
        outcome = (
            "not_applied"
            if response.status_code in (400, 401, 403, 404, 409, 410, 422)
            else "unknown"
        )
        return {
            "kind": "failure",
            "code": "BACKEND_HTTP_" + str(response.status_code),
            "retryable": False,
            "outcome": outcome,
        }
