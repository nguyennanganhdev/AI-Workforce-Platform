"""Allowlisted tool/assignment operations through backend, never direct WRITE."""

from typing import Any, Mapping, Optional

from adapters.backend.client import BackendClient, BackendResult
from adapters.backend.errors import AdapterError
from adapters.backend.messages import MESSAGE_TYPES
from adapters.backend.operations import send


class ToolClient:
    def __init__(
        self,
        backend: BackendClient,
        *,
        operations: Optional[Mapping[str, tuple[str, str]]] = None,
    ) -> None:
        """operations maps a trusted tool alias to (backend operation, payload type).

        Only documented message schemas are supported here. New tool wire formats
        require the shared contract owner; a model cannot supply an endpoint.
        """
        self._backend = backend
        self._operations = dict(operations or {})
        for operation, message_type in self._operations.values():
            if not operation or message_type not in MESSAGE_TYPES:
                raise ValueError("unsupported tool operation")

    async def offer_assignment(self, request: Mapping[str, Any]) -> BackendResult:
        # Backend must verify approvals and choose an authorized assignee.
        return await send(self._backend, "assignment.offer", "assignment.offered", request)

    async def respond_assignment(self, request: Mapping[str, Any]) -> BackendResult:
        return await send(self._backend, "assignment.respond", "assignment.responded", request)

    async def report_work(self, request: Mapping[str, Any]) -> BackendResult:
        # Before/after file IDs are evidence references, not proof of QC success.
        return await send(self._backend, "work.complete", "work.completed", request)

    async def invoke(self, name: str, request: Mapping[str, Any]) -> BackendResult:
        if name not in self._operations:
            raise AdapterError("tool_not_allowed")
        operation, message_type = self._operations[name]
        return await send(self._backend, operation, message_type, request)
