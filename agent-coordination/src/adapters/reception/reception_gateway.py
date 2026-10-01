"""Reception ↔ Supervisor V2 only. No V1 conversion or completion-response path."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping

from adapters.backend.client import BackendClient
from adapters.backend.errors import AdapterError, ValidationError
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

    async def receive_ticket(self, message: Any, *, authentication: object):
        return await self._receive(message, authentication, {"ticket_submitted"})

    async def receive_message(self, message: Any, *, authentication: object):
        return await self._receive(message, authentication, {"information_provided"})

    async def receive_plan_response(self, message: Any, *, authentication: object):
        return await self._receive(message, authentication,
                                   {"plan_approved", "plan_rejected", "plan_change_requested"})

    async def receive_cancel(self, message: Any, *, authentication: object):
        return await self._receive(message, authentication, {"cancel_requested"})

    async def ask_question(self, message: Any, *, context: Any):
        return await self._send(message, context, {"information_requested"})

    async def send_update(self, message: Any, *, context: Any):
        return await self._send(message, context, {"accepted", "in_progress", "failed", "cancelled"})

    async def send_plan(self, message: Any, *, context: Any):
        return await self._send(message, context, {"plan_approval_requested"})

    async def send_completion(self, message: Any, *, context: Any):
        # completed is work completion, never a request for resident confirmation.
        return await self._send(message, context, {"completed"})
