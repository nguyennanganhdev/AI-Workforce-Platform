"""Coordination side of Reception. Backend owns authorization and delivery."""

from typing import Any, Mapping

from adapters.backend.approval_client import ApprovalClient
from adapters.backend.client import BackendClient, BackendResult
from adapters.backend.errors import ValidationError
from adapters.backend.messages import snapshot
from adapters.backend.operations import send


class ReceptionGateway:
    def __init__(self, backend: BackendClient) -> None:
        self._backend = backend
        self._approvals = ApprovalClient(backend)

    async def receive_ticket(self, request: Mapping[str, Any]) -> BackendResult:
        return await send(self._backend, "reception.ticket", "ticket.submitted", request)

    async def receive_message(self, request: Mapping[str, Any]) -> BackendResult:
        # Keep reply_to_request_id and mentioned_agent_id unchanged. A display
        # name cannot be used as an authorization decision by this adapter.
        return await send(self._backend, "reception.message", "resident.message", request)

    async def ask_question(self, request: Mapping[str, Any]) -> BackendResult:
        return await send(self._backend, "reception.question", "resident.question", request)

    async def send_update(self, request: Mapping[str, Any]) -> BackendResult:
        # The endpoint must resolve recipient and filter content before delivery;
        # this method does not send model output directly to a browser/channel.
        return await send(self._backend, "reception.update", "resident.update", request)

    async def send_plan(self, request: Mapping[str, Any]) -> BackendResult:
        wire = snapshot(request)
        if (not isinstance(wire.get("payload"), dict)
                or wire["payload"].get("stage") != "resident_plan"):
            raise ValidationError()
        return await self._approvals.request_plan(wire)

    async def receive_plan_response(self, request: Mapping[str, Any]) -> BackendResult:
        wire = snapshot(request)
        if (not isinstance(wire.get("payload"), dict)
                or wire["payload"].get("stage") != "resident_plan"):
            raise ValidationError()
        return await self._approvals.respond_plan(wire)

    async def send_completion(self, request: Mapping[str, Any]) -> BackendResult:
        return await self._approvals.request_completion(request)

    async def receive_completion_response(self, request: Mapping[str, Any]) -> BackendResult:
        return await self._approvals.respond_completion(request)
