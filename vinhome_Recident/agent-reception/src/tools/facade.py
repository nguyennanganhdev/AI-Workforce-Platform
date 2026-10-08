"""Named, typed operations for deterministic graph nodes; never bind to an LLM."""

from __future__ import annotations

from typing import Protocol, cast

from . import contracts as c
from .validation import Operation, prepare_call, validate_input, validate_result


class InternalToolPort(Protocol):
    async def invoke(self, request: dict) -> dict: ...


class ReceptionTools:
    """Inject a BackendToolPort. Context must come from the trusted runtime."""

    def __init__(self, port: InternalToolPort):
        self._port = port

    async def _call(
        self,
        operation: Operation,
        value: c.ContractModel,
        context: c.VerifiedContext,
        idempotency_key: str,
    ) -> c.ToolResult:
        value = validate_input(operation, value)
        call, value, body = prepare_call(
            {
                "operation": operation,
                "input": value.model_dump(mode="json", exclude_unset=True),
                "context": context,
                "idempotencyKey": idempotency_key,
            }
        )
        result = await self._port.invoke(
            {
                "operation": operation,
                "input": body["input"],
                "context": body["context"],
                "idempotencyKey": call.idempotencyKey,
            }
        )
        # Injected ports cannot skip the same boundary checks as HTTP.
        return validate_result(operation, value, call.context, result)

    async def create_ticket_draft(
        self,
        value: c.DraftInput,
        *,
        context: c.VerifiedContext,
        idempotency_key: str,
    ) -> c.Success[c.Ticket] | c.Accepted | c.Failure:
        return cast(
            c.Success[c.Ticket] | c.Accepted | c.Failure,
            await self._call(
                "create_ticket_draft",
                value,
                context,
                idempotency_key,
            ),
        )

    async def get_verified_resident_context(
        self,
        value: c.ProfileInput,
        *,
        context: c.VerifiedContext,
        idempotency_key: str,
    ) -> c.Success[c.ProfileOutput] | c.Accepted | c.Failure:
        return cast(
            c.Success[c.ProfileOutput] | c.Accepted | c.Failure,
            await self._call(
                "get_verified_resident_context",
                value,
                context,
                idempotency_key,
            ),
        )

    async def update_ticket_incident(
        self,
        value: c.IncidentInput,
        *,
        context: c.VerifiedContext,
        idempotency_key: str,
    ) -> c.Success[c.IncidentOutput] | c.Accepted | c.Failure:
        return cast(
            c.Success[c.IncidentOutput] | c.Accepted | c.Failure,
            await self._call(
                "update_ticket_incident",
                value,
                context,
                idempotency_key,
            ),
        )

    async def submit_ticket_assessment(
        self,
        value: c.AssessmentInput,
        *,
        context: c.VerifiedContext,
        idempotency_key: str,
    ) -> c.Success[c.AssessmentOutput] | c.Accepted | c.Failure:
        return cast(
            c.Success[c.AssessmentOutput] | c.Accepted | c.Failure,
            await self._call(
                "submit_ticket_assessment",
                value,
                context,
                idempotency_key,
            ),
        )

    async def resolve_management_destination(
        self,
        value: c.TicketRef,
        *,
        context: c.VerifiedContext,
        idempotency_key: str,
    ) -> c.Success[c.RouteOutput] | c.Accepted | c.Failure:
        return cast(
            c.Success[c.RouteOutput] | c.Accepted | c.Failure,
            await self._call(
                "resolve_management_destination",
                value,
                context,
                idempotency_key,
            ),
        )

    async def handoff_ticket(
        self,
        value: c.HandoffInput,
        *,
        context: c.VerifiedContext,
        idempotency_key: str,
    ) -> c.Success[c.HandoffOutput] | c.Accepted | c.Failure:
        return cast(
            c.Success[c.HandoffOutput] | c.Accepted | c.Failure,
            await self._call(
                "handoff_ticket",
                value,
                context,
                idempotency_key,
            ),
        )

    async def register_supervisor_wait(
        self,
        value: c.WaitInput,
        *,
        context: c.VerifiedContext,
        idempotency_key: str,
    ) -> c.Success[c.WaitOutput] | c.Accepted | c.Failure:
        return cast(
            c.Success[c.WaitOutput] | c.Accepted | c.Failure,
            await self._call(
                "register_supervisor_wait",
                value,
                context,
                idempotency_key,
            ),
        )

    async def get_supervisor_event(
        self,
        value: c.EventInput,
        *,
        context: c.VerifiedContext,
        idempotency_key: str,
    ) -> c.Success[c.SupervisorEvent] | c.Accepted | c.Failure:
        return cast(
            c.Success[c.SupervisorEvent] | c.Accepted | c.Failure,
            await self._call(
                "get_supervisor_event",
                value,
                context,
                idempotency_key,
            ),
        )

    async def append_ticket_information(
        self,
        value: c.AppendInput,
        *,
        context: c.VerifiedContext,
        idempotency_key: str,
    ) -> c.Success[c.AppendOutput] | c.Accepted | c.Failure:
        return cast(
            c.Success[c.AppendOutput] | c.Accepted | c.Failure,
            await self._call(
                "append_ticket_information",
                value,
                context,
                idempotency_key,
            ),
        )

    async def respond_supervisor_interaction(
        self,
        value: c.InteractionInput,
        *,
        context: c.VerifiedContext,
        idempotency_key: str,
    ) -> c.Success[c.InteractionOutput] | c.Accepted | c.Failure:
        return cast(
            c.Success[c.InteractionOutput] | c.Accepted | c.Failure,
            await self._call(
                "respond_supervisor_interaction",
                value,
                context,
                idempotency_key,
            ),
        )

    async def request_ticket_cancellation(
        self,
        value: c.CancellationInput,
        *,
        context: c.VerifiedContext,
        idempotency_key: str,
    ) -> c.Success[c.CancellationOutput] | c.Accepted | c.Failure:
        return cast(
            c.Success[c.CancellationOutput] | c.Accepted | c.Failure,
            await self._call(
                "request_ticket_cancellation",
                value,
                context,
                idempotency_key,
            ),
        )

    async def get_ticket_status(
        self,
        value: c.TicketRef,
        *,
        context: c.VerifiedContext,
        idempotency_key: str,
    ) -> c.Success[c.StatusOutput] | c.Accepted | c.Failure:
        return cast(
            c.Success[c.StatusOutput] | c.Accepted | c.Failure,
            await self._call(
                "get_ticket_status",
                value,
                context,
                idempotency_key,
            ),
        )

    async def process_self_help(
        self,
        value: c.SelfHelpInput,
        *,
        context: c.VerifiedContext,
        idempotency_key: str,
    ) -> c.Success[c.SelfHelpOutput] | c.Accepted | c.Failure:
        return cast(
            c.Success[c.SelfHelpOutput] | c.Accepted | c.Failure,
            await self._call(
                "process_self_help",
                value,
                context,
                idempotency_key,
            ),
        )

    async def escalate_emergency(
        self,
        value: c.EmergencyInput,
        *,
        context: c.VerifiedContext,
        idempotency_key: str,
    ) -> c.Success[c.EmergencyOutput] | c.Accepted | c.Failure:
        return cast(
            c.Success[c.EmergencyOutput] | c.Accepted | c.Failure,
            await self._call(
                "escalate_emergency",
                value,
                context,
                idempotency_key,
            ),
        )
