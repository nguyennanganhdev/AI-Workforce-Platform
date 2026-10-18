"""Operation-specific validation, with no HTTP or graph dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Literal, get_args

from pydantic import TypeAdapter, ValidationError

from . import contracts as c

Operation = Literal[
    "create_ticket_draft",
    "get_verified_resident_context",
    "update_ticket_incident",
    "submit_ticket_assessment",
    "resolve_management_destination",
    "handoff_ticket",
    "register_supervisor_wait",
    "get_supervisor_event",
    "append_ticket_information",
    "respond_supervisor_interaction",
    "request_ticket_cancellation",
    "get_ticket_status",
    "process_self_help",
    "escalate_emergency",
]
OPERATIONS = get_args(Operation)


class ToolContractError(ValueError):
    """A stable error code only; never include input values or backend text."""


@dataclass(frozen=True)
class OperationContract:
    input_model: type[c.ContractModel]
    output_type: Any
    side_effect: Literal["read", "mutation"] = "mutation"
    visibility: Literal["system/internal"] = "system/internal"
    version: str = c.CONTRACT_VERSION


OPERATION_CONTRACTS = MappingProxyType(
    {
        "create_ticket_draft": OperationContract(c.DraftInput, c.Ticket),
        "get_verified_resident_context": OperationContract(
            c.ProfileInput, c.ProfileOutput
        ),
        "update_ticket_incident": OperationContract(c.IncidentInput, c.IncidentOutput),
        "submit_ticket_assessment": OperationContract(
            c.AssessmentInput, c.AssessmentOutput
        ),
        "resolve_management_destination": OperationContract(c.TicketRef, c.RouteOutput),
        "handoff_ticket": OperationContract(c.HandoffInput, c.HandoffOutput),
        "register_supervisor_wait": OperationContract(c.WaitInput, c.WaitOutput),
        "get_supervisor_event": OperationContract(
            c.EventInput, c.SupervisorEvent, "read"
        ),
        "append_ticket_information": OperationContract(c.AppendInput, c.AppendOutput),
        "respond_supervisor_interaction": OperationContract(
            c.InteractionInput, c.InteractionOutput
        ),
        "request_ticket_cancellation": OperationContract(
            c.CancellationInput, c.CancellationOutput
        ),
        "get_ticket_status": OperationContract(c.TicketRef, c.StatusOutput, "read"),
        "process_self_help": OperationContract(c.SelfHelpInput, c.SelfHelpOutput),
        "escalate_emergency": OperationContract(c.EmergencyInput, c.EmergencyOutput),
    }
)
_RESULTS = {
    name: TypeAdapter(c.Success[spec.output_type] | c.Accepted | c.Failure)
    for name, spec in OPERATION_CONTRACTS.items()
}

# Deliberately empty: this catalogue describes internal RPCs, not model tools.
LLM_TOOLS: tuple = ()


class CallEnvelope(c.ContractModel):
    operation: Operation
    input: dict[str, Any]
    context: c.VerifiedContext
    idempotencyKey: c.Id


def operation_contract(operation: str) -> OperationContract:
    if not isinstance(operation, str) or operation not in OPERATION_CONTRACTS:
        raise ToolContractError("TOOL_OPERATION_NOT_ALLOWED")
    return OPERATION_CONTRACTS[operation]


def validate_input(operation: str, value: object) -> c.ContractModel:
    spec = operation_contract(operation)
    if isinstance(value, c.ContractModel) and type(value) is not spec.input_model:
        raise ToolContractError("TOOL_INPUT_TYPE_MISMATCH")
    try:
        # Revalidate even model_construct(), copied models and mutable nested
        # lists; serialization warnings must not echo rejected values to logs.
        return spec.input_model.model_validate(value)
    except (ValidationError, TypeError, ValueError):
        raise ToolContractError("TOOL_INPUT_INVALID") from None


def prepare_call(request: object) -> tuple[CallEnvelope, c.ContractModel, dict]:
    try:
        call = CallEnvelope.model_validate(request)
    except (ValidationError, TypeError, ValueError):
        raise ToolContractError("TOOL_REQUEST_INVALID") from None
    value = validate_input(call.operation, call.input)
    body = {
        "operation": call.operation,
        "input": value.model_dump(mode="json", exclude_unset=True),
        "context": call.context.model_dump(mode="json"),
        "idempotency_key": call.idempotencyKey,
    }
    return call, value, body


def _same_ticket(expected, actual, *, exact_version=False):
    if (
        actual.ticket_id != expected.ticket_id
        or actual.ticket_generation != expected.ticket_generation
    ):
        raise ToolContractError("BACKEND_TICKET_MISMATCH")
    if exact_version and actual.ticket_version != expected.ticket_version:
        raise ToolContractError("BACKEND_TICKET_VERSION_MISMATCH")


def _same_correlation(expected, actual):
    if actual.correlation_id != expected.correlation_id:
        raise ToolContractError("BACKEND_CORRELATION_MISMATCH")


def _event(expected, context, event):
    _same_ticket(
        expected, event.payload, exact_version=isinstance(expected, c.EventInput)
    )
    _same_correlation(expected, event.payload)
    if (
        event.binding_id != context.bindingId
        or event.payload.tenant_id != context.tenantId
    ):
        raise ToolContractError("BACKEND_EVENT_SCOPE_MISMATCH")


def validate_result(
    operation: str,
    expected: c.ContractModel,
    context: c.VerifiedContext,
    raw: object,
    *,
    now: datetime | None = None,
) -> c.ToolResult:
    operation_contract(operation)
    try:
        result = _RESULTS[operation].validate_python(raw)
    except (ValidationError, TypeError, ValueError):
        raise ToolContractError("BACKEND_TOOL_RESULT_INVALID") from None
    if not isinstance(result, c.Success):
        # An accepted mutation has no value yet; unknown never becomes success.
        return result
    value = result.value
    ticket = getattr(value, "ticket", None)
    if ticket is not None and getattr(expected, "ticket_id", None) is not None:
        _same_ticket(expected, ticket)
    if operation == "update_ticket_incident":
        requested, confirmed = expected.incident.file_ids, value.incident.file_ids
        _confirm_files(requested, confirmed)
    elif operation == "append_ticket_information" or (
        operation == "respond_supervisor_interaction" and value.status == "accepted"
    ):
        _confirm_files(expected.file_ids, value.linked_file_ids)
    elif operation == "resolve_management_destination" and isinstance(
        value, c.ResolvedRoute
    ):
        if value.route.ticket_version != expected.ticket_version:
            raise ToolContractError("BACKEND_TICKET_VERSION_MISMATCH")
    elif operation in ("handoff_ticket", "register_supervisor_wait"):
        _same_ticket(expected, value, exact_version=True)
        _same_correlation(expected, value)
        if isinstance(value, c.WaitOutput) and value.buffered_event is not None:
            _event(expected, context, value.buffered_event)
    elif operation == "get_supervisor_event":
        _event(expected, context, value)
        if (
            value.event_id != expected.event_id
            or value.aggregate_version != expected.aggregate_version
        ):
            raise ToolContractError("BACKEND_EVENT_MISMATCH")
    elif operation == "process_self_help":
        _self_help(expected, value, now or datetime.now(timezone.utc))
    elif operation == "escalate_emergency":
        if value.policy_version != expected.policy_version:
            raise ToolContractError("BACKEND_POLICY_VERSION_MISMATCH")
        if (expected.ticket_id is None) != (value.ticket is None):
            raise ToolContractError("BACKEND_TICKET_MISMATCH")
    return result


def _confirm_files(requested, confirmed):
    if not set(requested).issubset(confirmed):
        raise ToolContractError("FILE_LINK_CONFIRMATION_MISSING")


def _self_help(expected: c.SelfHelpInput, value, now: datetime):
    if value.policy_version != expected.policy_version:
        raise ToolContractError("BACKEND_POLICY_VERSION_MISMATCH")
    if isinstance(value, c.SelfHelpUnavailable):
        return
    if expected.attempt is not None and value.attempt_id != expected.attempt.attempt_id:
        raise ToolContractError("BACKEND_SELF_HELP_ATTEMPT_MISMATCH")
    if isinstance(value, c.SelfHelpRecorded):
        if (
            expected.attempt is None
            or value.source_message_id != expected.source_message.id
        ):
            raise ToolContractError("BACKEND_SELF_HELP_OUTCOME_MISMATCH")
        return
    procedure = value.procedure
    if procedure.policy_version != expected.policy_version or (
        expected.attempt is not None
        and expected.attempt.procedure_version != procedure.version
    ):
        raise ToolContractError("BACKEND_PROCEDURE_VERSION_MISMATCH")
    if datetime.fromisoformat(procedure.expires_at.replace("Z", "+00:00")) <= now:
        raise ToolContractError("BACKEND_PROCEDURE_EXPIRED")
    if isinstance(value, c.SelfHelpAccepted) and (
        expected.attempt is None
        or value.consent_source_message_id != expected.source_message.id
    ):
        raise ToolContractError("BACKEND_SELF_HELP_CONSENT_MISMATCH")
