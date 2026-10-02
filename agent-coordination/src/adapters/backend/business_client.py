"""Configured business contracts, including procedure/contribution/report hooks.

No workflow or canonical schema is invented here. The owner supplies each alias,
endpoint operation and pinned request/response schema; unknown aliases fail.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .client import BackendClient
from .errors import AdapterError
from .messages import snapshot, validate_context


@dataclass(frozen=True)
class BusinessOperation:
    operation: str
    request_schema: str
    response_schema: str


class BusinessClient:
    def __init__(self, backend: BackendClient, *, operations: Mapping[str, BusinessOperation]):
        if any(not all((name, spec.operation, spec.request_schema, spec.response_schema))
               for name, spec in operations.items()):
            raise ValueError("invalid business operation")
        self._backend, self._operations = backend, dict(operations)

    async def call(self, alias: str, request: Mapping) -> dict:
        if alias not in self._operations:
            raise AdapterError("operation_not_configured")
        wire = snapshot(request)
        validate_context(wire.get("context"))
        operation = self._operations[alias]
        return await self._backend.call_contract(operation.operation, wire,
            request_schema=operation.request_schema, response_schema=operation.response_schema)
