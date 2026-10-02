"""Adapter-local guards for backend commands/events, not Reception schema V2.

The composition injects a validator for the documented contracts; published
JSON Schemas owned by DEV-5/Team Chien can augment these guards. Identity,
membership, approval validity and business state are checked by the backend.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime
from typing import Any, Mapping, Protocol

from .errors import ValidationError

JSON = dict[str, Any]


class ContractValidator(Protocol):
    def validate(self, kind: str, value: Mapping[str, Any]) -> None:
        """Validate documented boundaries/configured schemas; raise on failure.

        Backend: request/response/event. Reception: reception_input/output,
        reception_delivery/response/verified. Each wire direction has one schema;
        the latter three describe backend routing/receipts, not Reception fields.
        """
        ...


def snapshot(value: Mapping[str, Any]) -> JSON:
    """Isolate mutable caller state and reject non-JSON/NaN before an await."""
    try:
        result = json.loads(json.dumps(value, allow_nan=False, ensure_ascii=False))
    except (ValueError, TypeError, RecursionError):
        raise ValidationError() from None
    if not isinstance(result, dict):
        raise ValidationError()
    return result


def require(condition: bool) -> None:
    if not condition:
        raise ValidationError()


def text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def integer(value: Any, minimum: int = 0) -> bool:
    return type(value) is int and value >= minimum


def strings(value: Any) -> bool:
    return isinstance(value, list) and all(text(item) for item in value)


def timestamp(value: Any) -> bool:
    if not text(value):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.tzinfo is not None and parsed.utcoffset() is not None
    except ValueError:
        return False


CONTEXT_IDS = (
    "tenant_id", "principal_id", "domain_id", "workspace_id",
    "ticket_id", "binding_id", "run_id",
)
MESSAGE_TYPES = frozenset({
    "ticket.submitted", "resident.message", "resident.question", "resident.update",
    "approval.requested", "approval.responded", "assignment.offered",
    "assignment.responded", "work.completed", "completion.requested",
    "completion.responded",
})


def validate_context(context: Any) -> None:
    require(isinstance(context, dict))
    for key in CONTEXT_IDS:
        require(text(context.get(key)))
    require(integer(context.get("ticket_generation")))
    if "initiated_by_user_id" in context:
        require(text(context["initiated_by_user_id"]))


def money(value: Any, *, estimate: bool = False) -> None:
    # Unknown cost is explicit null, never silently converted to zero.
    if value is None:
        return
    require(isinstance(value, dict))
    require(type(value.get("amount")) in (int, float) and value["amount"] >= 0)
    require(text(value.get("currency")))
    if estimate:
        require(text(value.get("kind")))


def validate_payload(message_type: str, payload: Any) -> None:
    require(message_type in MESSAGE_TYPES and isinstance(payload, dict))
    p = payload

    def ids(*keys: str) -> None:
        for key in keys:
            require(text(p.get(key)))

    def versioned(name: str) -> None:
        ids(f"{name}_id")
        require(integer(p.get(f"{name}_version"), 1))

    def files(key: str) -> None:
        require(strings(p.get(key)))

    if message_type == "ticket.submitted":
        ids("report")
        require(isinstance(p.get("facts"), dict))
        files("attachment_ids")
    elif message_type == "resident.message":
        ids("text")
        for key in ("reply_to_request_id", "mentioned_agent_id"):
            if key in p:
                ids(key)
    elif message_type == "resident.question":
        ids("question_id", "question")
    elif message_type == "resident.update":
        ids("summary", "status")
        files("attachment_ids")
    elif message_type.startswith("approval."):
        ids("approval_id")
        versioned("plan")
        require(p.get("stage") in ("management_plan", "resident_plan"))
        if message_type == "approval.responded":
            require(p.get("decision") in ("approve", "reject", "request_changes"))
        else:
            ids("recipient_user_id", "summary")
            require(strings(p.get("steps")) and bool(p["steps"]))
            files("attachment_ids")
            require("cost" in p)
            money(p["cost"], estimate=True)
            require(timestamp(p.get("expires_at")))
            if p["stage"] == "resident_plan":
                ids("depends_on_approval_id")
                require(p.get("delivery_channel") == "reception")
            else:
                require(p.get("delivery_channel") == "management_ui")
    elif message_type.startswith("assignment."):
        versioned("assignment")
        versioned("plan")
        if message_type == "assignment.responded":
            require(p.get("decision") in ("accept", "decline"))
            if p["decision"] == "decline":
                ids("reason")
    elif message_type == "work.completed":
        versioned("assignment")
        versioned("result")
        ids("summary")
        files("before_file_ids")
        files("after_file_ids")
        if "actual_cost" in p:
            money(p["actual_cost"])
    elif message_type.startswith("completion."):
        ids("confirmation_id")
        versioned("result")
        if message_type == "completion.responded":
            require(p.get("decision") in ("confirmed", "not_satisfied"))
        else:
            versioned("plan")
            ids("recipient_user_id", "summary")
            files("evidence_file_ids")
            require("final_cost" in p)
            money(p["final_cost"])
    if "comment" in p:
        require(isinstance(p["comment"], str))


def validate_request(request: JSON) -> None:
    require(set(request) == {
        "contract_version", "type", "request_id", "trace_id",
        "idempotency_key", "context", "payload",
    })
    require(request.get("contract_version") == "1")
    for key in ("type", "request_id", "trace_id", "idempotency_key"):
        require(text(request.get(key)))
    validate_context(request.get("context"))
    validate_payload(request["type"], request.get("payload"))


def validate_event(event: JSON) -> None:
    # Event payload is canonical message data; routing context comes from a
    # trusted resolver, not an arbitrary context inserted into the event.
    require(set(event) == {
        "event_id", "event_type", "schema_version", "tenant_id", "aggregate_id",
        "aggregate_version", "occurred_at", "correlation_id", "causation_id", "payload",
    })
    for key in ("event_id", "event_type", "tenant_id", "aggregate_id",
                "correlation_id", "causation_id"):
        require(text(event.get(key)))
    require(event.get("schema_version") == "1")
    require(integer(event.get("aggregate_version")))
    require(timestamp(event.get("occurred_at")))
    require(isinstance(event.get("payload"), dict))


def fingerprint(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")).hexdigest()


def validate_with(validator: ContractValidator, kind: str, value: JSON) -> None:
    # A validator may neither mutate the wire value nor leak it in an exception.
    try:
        validator.validate(kind, deepcopy(value))
    except Exception:
        raise ValidationError() from None
