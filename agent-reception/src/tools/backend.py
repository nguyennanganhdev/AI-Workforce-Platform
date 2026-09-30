"""Validated HTTP tool port for the OpenBot backend.

The endpoint paths are configurable contracts. Team Chiến can bind them without
changing the Reception graph. Every mutation carries the graph-generated
idempotency key; retries always reuse the same request body and key.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx

from ..graph.workflow_contracts import OPERATIONS


class ToolContractError(ValueError):
    pass


@dataclass(frozen=True)
class BackendToolConfig:
    base_url: str
    service_token: str
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


def _required_text(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 16384:
        raise ToolContractError(code)
    return value


def _file_ids(value: Any) -> list[str]:
    if not isinstance(value, list) or len(value) > 256:
        raise ToolContractError("FILE_IDS_INVALID")
    result: list[str] = []
    for item in value:
        item = _required_text(item, "FILE_ID_INVALID")
        if item not in result:
            result.append(item)
    return result


def _validate_file_contract(operation: str, value: dict[str, Any]) -> list[str]:
    if operation == "update_ticket_incident":
        incident = value.get("incident")
        if not isinstance(incident, dict):
            raise ToolContractError("INCIDENT_INPUT_INVALID")
        return _file_ids(incident.get("file_ids"))
    if operation in ("append_ticket_information", "respond_supervisor_interaction"):
        return _file_ids(value.get("file_ids", []))
    return []


def _validate_result(operation: str, expected_files: list[str], result: Any) -> dict:
    if not isinstance(result, dict) or result.get("kind") not in (
        "success",
        "accepted",
        "failure",
    ):
        raise ToolContractError("BACKEND_TOOL_RESULT_INVALID")
    kind = result["kind"]
    if kind == "success":
        value = result.get("value")
        if not isinstance(value, dict):
            raise ToolContractError("BACKEND_TOOL_VALUE_INVALID")
        if expected_files:
            if operation == "update_ticket_incident":
                incident = value.get("incident")
                confirmed = (
                    incident.get("file_ids") if isinstance(incident, dict) else None
                )
            else:
                confirmed = value.get("linked_file_ids")
            if not set(expected_files).issubset(_file_ids(confirmed)):
                raise ToolContractError("FILE_LINK_CONFIRMATION_MISSING")
    elif kind == "accepted":
        _required_text(result.get("operationId"), "BACKEND_OPERATION_ID_REQUIRED")
    else:
        _required_text(result.get("code"), "BACKEND_ERROR_CODE_REQUIRED")
        if not isinstance(result.get("retryable"), bool) or result.get("outcome") not in (
            "unknown",
            "not_applied",
        ):
            raise ToolContractError("BACKEND_FAILURE_INVALID")
    return result


class BackendToolPort:
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
        operation = request.get("operation")
        if operation not in OPERATIONS:
            raise ToolContractError("TOOL_OPERATION_NOT_ALLOWED")
        value = request.get("input")
        context = request.get("context")
        if not isinstance(value, dict) or not isinstance(context, dict):
            raise ToolContractError("TOOL_REQUEST_INVALID")
        key = _required_text(request.get("idempotencyKey"), "IDEMPOTENCY_KEY_REQUIRED")
        expected_files = _validate_file_contract(operation, value)
        value = dict(value)
        if operation == "update_ticket_incident":
            value["incident"] = {**value["incident"], "file_ids": expected_files}
        elif operation in ("append_ticket_information", "respond_supervisor_interaction"):
            value["file_ids"] = expected_files
        body = {
            "operation": operation,
            "input": value,
            "context": context,
            "idempotency_key": key,
        }
        result = await self._post(self.config.operation_path, body, key)
        return _validate_result(operation, expected_files, result)

    async def reconcile(self, request: dict[str, Any]) -> dict[str, Any]:
        operation = request.get("operation")
        value = request.get("input")
        if operation not in OPERATIONS or not isinstance(value, dict):
            raise ToolContractError("RECONCILE_REQUEST_INVALID")
        key = _required_text(request.get("idempotencyKey"), "IDEMPOTENCY_KEY_REQUIRED")
        expected_files = _validate_file_contract(operation, value)
        body = {
            "operation": operation,
            "input": value,
            "context": request.get("context"),
            "idempotency_key": key,
        }
        result = await self._post(self.config.reconcile_path, body, key)
        return _validate_result(operation, expected_files, result)

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
