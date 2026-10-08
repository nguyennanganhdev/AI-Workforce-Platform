"""Validation for the authoritative session snapshot returned by OpenBot backend."""

from __future__ import annotations

from datetime import datetime


class RecoveryContractError(ValueError):
    pass


def record(value):
    if type(value) is not dict:
        raise RecoveryContractError("RECOVERY_RECORD_INVALID")
    return value


def text(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 16384:
        raise RecoveryContractError("RECOVERY_TEXT_INVALID")
    return value


def integer(value):
    if type(value) is not int or value < 0 or value > 2**53 - 1:
        raise RecoveryContractError("RECOVERY_INTEGER_INVALID")
    return value


def timestamp(value):
    value = text(value)
    try:
        if datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is None:
            raise ValueError
    except ValueError:
        raise RecoveryContractError("RECOVERY_TIMESTAMP_INVALID") from None
    return value


def parse_ticket(value):
    value = record(value)
    return {
        **{
            key: text(value.get(key))
            for key in ("ticket_id", "ticket_code", "ticket_version")
        },
        **{
            key: integer(value.get(key))
            for key in ("ticket_generation", "aggregate_version")
        },
        "created_at": timestamp(value.get("created_at")),
    }


def parse_file_ref(value):
    value = record(value)
    return {
        "file_id": text(value.get("file_id")),
        "source_message_id": text(value.get("source_message_id")),
    }


def parse_recovered_session(value) -> dict:
    session = record(value)
    result = {
        "channel_id": text(session.get("channel_id")),
        "reception_session_id": text(session.get("reception_session_id")),
        "ticket": None,
        "active_ticket_id": None,
        "pending_file_refs": [],
        "linked_file_ids": [],
        "route": None,
        "ack": None,
    }
    if session.get("ticket") is not None:
        ticket = parse_ticket(session["ticket"])
        result.update(ticket=ticket, active_ticket_id=ticket["ticket_id"])
    raw_refs = session.get("file_references", [])
    if not isinstance(raw_refs, list):
        raise RecoveryContractError("INVALID_FILE_REFERENCES")
    statuses = {}
    for raw in raw_refs:
        parsed = parse_file_ref(raw)
        linked = record(raw).get("linked_to_ticket")
        if not isinstance(linked, bool):
            raise RecoveryContractError("RECOVERY_FILE_STATUS_INVALID")
        identity = (parsed["file_id"], parsed["source_message_id"])
        if identity in statuses and statuses[identity] != linked:
            raise RecoveryContractError("RECOVERY_FILE_STATUS_CONFLICT")
        if identity in statuses:
            continue
        statuses[identity] = linked
        if linked:
            if parsed["file_id"] not in result["linked_file_ids"]:
                result["linked_file_ids"].append(parsed["file_id"])
        else:
            result["pending_file_refs"].append(parsed)
    handoff = session.get("handoff")
    if handoff is not None:
        if result["ticket"] is None:
            raise RecoveryContractError("RECOVERY_TICKET_REQUIRED")
        handoff = record(handoff)
        route_value, ack_value = record(handoff.get("route")), record(handoff.get("ack"))
        route = {
            key: text(route_value.get(key))
            for key in (
                "destination_id",
                "workspace_id",
                "team_id",
                "coordination_binding_id",
                "building_id",
                "domain_id",
                "ticket_version",
            )
        }
        route["route_revision"] = integer(route_value.get("route_revision"))
        if route["ticket_version"] != result["ticket"]["ticket_version"]:
            raise RecoveryContractError("RECOVERY_ROUTE_VERSION_MISMATCH")
        ack = {
            "persisted": ack_value.get("persisted"),
            "enqueued": ack_value.get("enqueued"),
            "correlation_id": text(ack_value.get("correlation_id")),
            "operation_id": text(ack_value.get("operation_id")),
        }
        if ack["persisted"] is not True or ack["enqueued"] is not True:
            raise RecoveryContractError("RECOVERY_HANDOFF_ACK_INVALID")
        result.update(route=route, ack=ack)
    return result
