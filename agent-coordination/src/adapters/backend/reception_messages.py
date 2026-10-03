"""V2 guards using boundary models already shared by DEV-1/DEV-2.

An injected boundary validator remains required. Imports are lazy so backend
approval, tool and event clients keep their standard-library-only boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Mapping

from .errors import AdapterError, ValidationError
from .messages import JSON, fingerprint, snapshot, text, validate_context

if TYPE_CHECKING:
    from groupchat.models import Command
    from supervisor.models import VerifiedReception


@dataclass(frozen=True)
class ReceptionResolution:
    verified: VerifiedReception
    # Trusted routing sidecar, never a field in the Reception V2 message.
    room_command: Command | None = None


def message_wire(value: Any, *, output: bool = False) -> JSON:
    from groupchat.reception import ReceptionMessage, SupervisorMessage

    expected = SupervisorMessage if output else ReceptionMessage
    if isinstance(value, expected):
        # exclude_none would drop a required facts[].value=null on input.
        try:
            value = value.model_dump(mode="json", exclude_unset=True, warnings="error")
        except Exception:
            raise ValidationError() from None
    if not isinstance(value, Mapping):
        raise ValidationError()
    wire = snapshot(value)
    (validate_output if output else validate_input)(wire)
    return wire


def _validate(value: Any, *, output: bool) -> None:
    from groupchat.reception import ReceptionMessage, SupervisorMessage

    try:
        model = SupervisorMessage if output else ReceptionMessage
        model.model_validate(value, strict=True)
        snapshot(value)  # rejects NaN/infinity and non-JSON data in facts
    except Exception:
        raise ValidationError() from None


def validate_input(value: Any) -> None:
    _validate(value, output=False)


def validate_output(value: Any) -> None:
    _validate(value, output=True)


def validate_scope(message: JSON, context: Any) -> None:
    from groupchat.models import Context

    validate_context(context)
    try:
        Context.model_validate(context, strict=True)
    except Exception:
        raise ValidationError() from None
    for key in ("tenant_id", "workspace_id", "ticket_id", "ticket_generation"):
        if message[key] != context[key]:
            raise AdapterError("scope_mismatch")
    if "domain_id" in message and message["domain_id"] != context["domain_id"]:
        raise AdapterError("scope_mismatch")


def verified_resolution(request: JSON, data: JSON) -> ReceptionResolution:
    from groupchat.models import Command, Context
    from groupchat.reception import ReceptionMessage
    from supervisor.models import VerifiedReception

    try:
        if (not {"message", "context", "supervisor_run_id"} <= set(data)
                or set(data) - {"message", "context", "supervisor_run_id", "room_command"}
                or not text(data["supervisor_run_id"])):
            raise ValidationError()
        verified_wire = message_wire(data["message"])
        # Backend verifies the supplied snapshot; it must not rebase an old reply.
        if fingerprint(verified_wire) != fingerprint(request):
            raise ValidationError()
        validate_scope(verified_wire, data["context"])
        context = Context.model_validate(data["context"], strict=True)
        verified = VerifiedReception(context=context,
            message=ReceptionMessage.model_validate(verified_wire, strict=True),
            supervisor_run_id=data["supervisor_run_id"])
        command = None
        if data.get("room_command") is not None:
            command = Command.model_validate(data["room_command"], strict=True)
            if (request["message_type"] != "information_provided"
                    or command.payload.operation != "mention_agent"
                    or command.context != context
                    or command.payload.instruction != request["message"]):
                raise ValidationError()
        return ReceptionResolution(verified, command)
    except Exception:
        raise AdapterError("invalid_backend_response", outcome_unknown=True) from None
