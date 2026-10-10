"""Allowlisted public projection and cursor semantics; no raw runtime leakage."""

from copy import deepcopy
import json

from .._models import require


PUBLIC_TYPES = {"assistant.message", "conversation.message", "workflow.status_changed",
                "workflow.awaiting_user", "workflow.awaiting_confirmation", "workflow.blocked",
                "workflow.closed", "operation.status_changed", "ticket.status_changed"}


def project_event(event, binding, *, authorized_audience):
    require(authorized_audience == binding["audience"], "AUDIENCE_FORBIDDEN")
    require(event["conversation_id"] == binding["conversation_id"] and
            event["workflow_id"] == binding["workflow_id"], "WORKFLOW_BINDING_MISMATCH")
    require(event["event_type"] in PUBLIC_TYPES, "EVENT_NOT_PUBLIC")
    result = {key: event[key] for key in (
        "event_id", "sequence", "conversation_id", "workflow_id", "event_type",
    )}
    result.update(schema_version="1", occurred_at=event.get("occurred_at", event.get("created_at")),
                  recorded_at=event.get("recorded_at", event.get("created_at")))
    result["external_ticket_id"] = binding["audience"].get("external_ticket_id")
    result["external_conversation_id"] = binding["audience"]["external_conversation_id"]
    result["external_user_id"] = binding["audience"]["external_user_id"]
    # Payload must already be the public schema projection produced by the owner,
    # not arbitrary tool/LLM output. Explicit per-type allowlist prevents secrets.
    allowed = ({"message_id", "speaker", "text"} if event["event_type"].endswith("message") else
               {"workflow_state", "next_action", "workflow_revision", "operation_id",
                "status", "protocol_version", "schema_version", "public_error_code"})
    result["payload"] = {k: deepcopy(v) for k, v in event.get("payload", {}).items() if k in allowed}
    if event["event_type"].endswith("message") and "text" not in result["payload"]:
        require(isinstance(event.get("payload", {}).get("content"), str), "MESSAGE_INVALID")
        result["payload"]["text"] = event["payload"]["content"]
    return result


def encode_sse(public_event):
    require(not any(c in public_event["event_id"] for c in "\r\n\x00"), "EVENT_ID_INVALID")
    require(public_event["event_type"] in PUBLIC_TYPES, "EVENT_NOT_PUBLIC")
    return (f"id: {public_event['event_id']}\nevent: {public_event['event_type']}\n"
            f"data: {json.dumps(public_event, ensure_ascii=False, separators=(',', ':'))}\n\n")


def validate_cursor(cursor_record, *, conversation_id, audience, retention_floor):
    require(cursor_record is not None and cursor_record["conversation_id"] == conversation_id and
            cursor_record["audience"] == audience, "EVENT_CURSOR_INVALID")
    require(cursor_record["sequence"] >= retention_floor, "EVENT_CURSOR_EXPIRED")
    return cursor_record["sequence"]
