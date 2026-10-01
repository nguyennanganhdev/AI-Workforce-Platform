"""Separate DEV-1 legacy bridge and Reception V2 ports; no wire conversion."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping

from adapters.backend.approval_client import ApprovalClient
from adapters.backend.client import BackendClient, BackendResult
from adapters.backend.errors import AdapterError, ValidationError
from adapters.backend.messages import snapshot
from adapters.backend.operations import send as send_backend
from adapters.backend.reception_client import ReceptionAuthentication, ReceptionClient
from adapters.backend.reception_messages import ReceptionResolution, message_wire

if TYPE_CHECKING:
    from groupchat.models import Context
    from groupchat.reception import ReceptionMessage, SupervisorMessage
    from supervisor.models import VerifiedReception


class ReceptionGateway:
    def __init__(
        self, backend: BackendClient, *, authentication: ReceptionAuthentication | None = None,
        timeout: float = 15,
    ) -> None:
        self._backend = backend
        self._approvals = ApprovalClient(backend)
        self._client = ReceptionClient(backend, authentication=authentication, timeout=timeout)

    async def resolve(self, message: Any, authentication: object) -> ReceptionResolution:
        """Return verified input and optional backend-resolved DEV-2 mention command.

        Composition must enqueue/consume the command through DEV-4/DEV-2 with its
        original IDs and reauthorization. Never derive an ID from @text.
        """
        return await self._client.resolve(message, authentication)

    async def verify(
        self, message: ReceptionMessage | Mapping[str, Any], authentication: object,
    ) -> VerifiedReception:
        """Implements DEV-1 ReceptionPort.verify, accepting only schema 2.0."""
        resolved = await self.resolve(message, authentication)
        if resolved.room_command is not None:
            raise AdapterError("mention_requires_groupchat")
        return resolved.verified

    async def send(
        self, message: SupervisorMessage | Mapping[str, Any], context: Context | Mapping[str, Any],
    ) -> dict[str, Any]:
        """Implements ReceptionPort.send; backend validates/stores before delivery."""
        receipt = await self._client.send(message, context)
        return {"message_id": receipt.message_id, "status": receipt.status}

    async def _receive(self, message: Any, authentication: object, kinds: set[str]):
        wire = message_wire(message)
        if wire["message_type"] not in kinds:
            raise ValidationError()
        return await self.verify(wire, authentication)

    async def _send(self, message: Any, context: Any, kinds: set[str]):
        wire = message_wire(message, output=True)
        if wire["message_type"] not in kinds:
            raise ValidationError()
        return await self.send(wire, context)

    async def receive_ticket_v2(self, message: Any, *, authentication: object):
        return await self._receive(message, authentication, {"ticket_submitted"})

    async def receive_message_v2(self, message: Any, *, authentication: object):
        return await self._receive(message, authentication, {"information_provided"})

    async def receive_plan_response_v2(self, message: Any, *, authentication: object):
        return await self._receive(message, authentication,
                                   {"plan_approved", "plan_rejected", "plan_change_requested"})

    async def receive_cancel_v2(self, message: Any, *, authentication: object):
        return await self._receive(message, authentication, {"cancel_requested"})

    async def ask_question_v2(self, message: Any, *, context: Any):
        return await self._send(message, context, {"information_requested"})

    async def send_update_v2(self, message: Any, *, context: Any):
        return await self._send(message, context, {"accepted", "in_progress", "failed", "cancelled"})

    async def send_plan_v2(self, message: Any, *, context: Any):
        return await self._send(message, context, {"plan_approval_requested"})

    async def send_completion_v2(self, message: Any, *, context: Any):
        # completed is work completion, never a request for resident confirmation.
        return await self._send(message, context, {"completed"})

    # Legacy bridge methods accept only contract_version=1 backend envelopes.
    async def receive_ticket(self, request: Mapping[str, Any]) -> BackendResult:
        return await send_backend(self._backend, "reception.ticket", "ticket.submitted", request)

    async def receive_message(self, request: Mapping[str, Any]) -> BackendResult:
        # Keep reply_to_request_id and mentioned_agent_id unchanged. A display
        # name cannot be used as an authorization decision by this adapter.
        return await send_backend(self._backend, "reception.message", "resident.message", request)

    async def ask_question(self, request: Mapping[str, Any]) -> BackendResult:
        return await send_backend(self._backend, "reception.question", "resident.question", request)

    async def send_update(self, request: Mapping[str, Any]) -> BackendResult:
        # The endpoint must resolve recipient and filter content before delivery;
        # this method does not send model output directly to a browser/channel.
        return await send_backend(self._backend, "reception.update", "resident.update", request)

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
