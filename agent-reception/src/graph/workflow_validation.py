"""Runtime validation and schema-v1 projection from verified port results."""

from __future__ import annotations

import json
import math
from datetime import datetime

from .decision import GraphFault, compact_json


def record(value) -> dict:
    if type(value) is not dict:
        raise GraphFault("INVALID_WORKFLOW_OUTPUT")
    return value


def text(value, limit=16384) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise GraphFault("INVALID_WORKFLOW_OUTPUT")
    return value


def integer(value) -> int:
    if type(value) is not int or value < 0 or value > 2**53 - 1:
        raise GraphFault("INVALID_WORKFLOW_OUTPUT")
    return value


def boolean(value) -> bool:
    if type(value) is not bool:
        raise GraphFault("INVALID_WORKFLOW_OUTPUT")
    return value


def strings(value, limit=256) -> list[str]:
    if not isinstance(value, list) or len(value) > limit:
        raise GraphFault("INVALID_WORKFLOW_OUTPUT")
    return [text(item) for item in value]


def parse_file_refs(value, limit=256) -> list[dict]:
    if not isinstance(value, list) or len(value) > limit:
        raise GraphFault("INVALID_FILE_REFERENCES")
    result = []
    seen = set()
    for item in value:
        v = record(item)
        ref = {
            "file_id": text(v.get("file_id")),
            "source_message_id": text(v.get("source_message_id")),
        }
        identity = (ref["file_id"], ref["source_message_id"])
        if identity not in seen:
            seen.add(identity)
            result.append(ref)
    return result


def choice(value, choices):
    if not isinstance(value, str) or value not in choices:
        raise GraphFault("INVALID_WORKFLOW_OUTPUT")
    return value


def timestamp(value) -> str:
    value = text(value)
    try:
        if (
            "T" not in value
            or datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is None
        ):
            raise ValueError
    except ValueError:
        raise GraphFault("INVALID_WORKFLOW_OUTPUT") from None
    return value


def parse_ticket(value, previous=None) -> dict:
    v = record(value)
    ticket = {
        key: text(v.get(key)) for key in ("ticket_id", "ticket_code", "ticket_version")
    }
    ticket.update(
        {key: integer(v.get(key)) for key in ("ticket_generation", "aggregate_version")}
    )
    ticket["created_at"] = timestamp(v.get("created_at"))
    if previous and (
        ticket["ticket_id"] != previous["ticket_id"]
        or ticket["ticket_generation"] != previous["ticket_generation"]
        or ticket["aggregate_version"] < previous["aggregate_version"]
    ):
        raise GraphFault("TICKET_MISMATCH_OR_STALE")
    return ticket


def parse_profile(value) -> dict:
    v = record(value)
    return {
        key: text(v.get(key))
        for key in (
            "resident_id",
            "resident_name",
            "phone_number",
            "unit_id",
            "unit_number",
            "building_id",
            "building_code",
            "building_name",
            "domain_id",
            "domain_name",
            "location_scope_id",
        )
    }


def parse_facts(value) -> list[dict]:
    if not isinstance(value, list) or len(value) > 64:
        raise GraphFault("INVALID_WORKFLOW_OUTPUT")
    result = []
    for item in value:
        v = record(item)
        val = v.get("value")
        if val is not None and not (
            type(val) in (str, bool) or type(val) in (int, float) and math.isfinite(val)
        ):
            raise GraphFault("INVALID_WORKFLOW_OUTPUT")
        result.append(
            {
                "key": text(v.get("key")),
                "value": val,
                "source": choice(
                    v.get("source"),
                    ("customer_report", "staff_verified", "agent_inference"),
                ),
                "source_message_id": text(v.get("source_message_id")),
            }
        )
    return result


def parse_incident(value) -> dict:
    v = record(value)
    if (
        not isinstance(v.get("title"), str)
        or not isinstance(v.get("description"), str)
        or len(v["title"]) > 1024
        or len(v["description"]) > 16384
    ):
        raise GraphFault("INVALID_WORKFLOW_OUTPUT")
    return {
        "title": v["title"],
        "description": v["description"],
        "facts": parse_facts(v.get("facts")),
        "file_ids": strings(v.get("file_ids")),
    }


def parse_triage(value) -> dict:
    v = record(value)
    return {
        "status": choice(v.get("status"), ("applied",)),
        "policy_version": text(v.get("policy_version")),
        "triage_decision_id": text(v.get("triage_decision_id")),
        "request_kind": choice(v.get("request_kind"), ("incident", "service_request")),
        "priority": choice(v.get("priority"), ("low", "normal", "high", "critical")),
        "severity": choice(
            v.get("severity"),
            ("unknown", "minor", "moderate", "major", "critical", "not_applicable"),
        ),
        "is_emergency": boolean(v.get("is_emergency")),
    }


def parse_route(value, state) -> dict:
    v = record(value)
    route = {
        key: text(v.get(key))
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
    route["route_revision"] = integer(v.get("route_revision"))
    p = state.get("verified_profile", {})
    if (
        route["building_id"] != p.get("building_id")
        or route["domain_id"] != p.get("domain_id")
        or route["ticket_version"] != state.get("ticket", {}).get("ticket_version")
    ):
        raise GraphFault("ROUTE_SCOPE_OR_VERSION_MISMATCH")
    return route


def parse_ack(value, correlation) -> dict:
    v = record(value)
    if (
        v.get("persisted") is not True
        or v.get("enqueued") is not True
        or v.get("correlation_id") != correlation
    ):
        raise GraphFault("HANDOFF_ACK_REQUIRED")
    return {
        "persisted": True,
        "enqueued": True,
        "correlation_id": correlation,
        "operation_id": text(v.get("operation_id")),
    }


def build_handoff(state, sent_at) -> dict:
    if any(
        not state.get(key)
        for key in ("ticket", "verified_profile", "incident", "triage", "route")
    ):
        raise GraphFault("HANDOFF_INCOMPLETE")
    ticket, p, i, t, r = (
        state[key]
        for key in ("ticket", "verified_profile", "incident", "triage", "route")
    )
    text(i["title"])
    text(i["description"])
    parse_profile(p)
    parse_triage(t)
    parse_route(r, state)
    if state.get("intake", {}).get("emergency") and not t["is_emergency"]:
        raise GraphFault("EMERGENCY_DOWNGRADE_REVIEW")
    identity = compact_json(
        [
            state["reception_session_id"],
            ticket["ticket_id"],
            ticket["ticket_generation"],
            ticket["ticket_version"],
            r["route_revision"],
        ]
    )
    return {
        "schema_version": "1.0",
        "message_id": "handoff:" + identity,
        "correlation_id": "correlation:" + identity,
        "sent_at": timestamp(sent_at),
        "tenant_id": state["owner"]["tenantId"],
        "domain_id": p["domain_id"],
        "domain_name": p["domain_name"],
        "workspace_id": r["workspace_id"],
        "team_id": r["team_id"],
        **{
            key: ticket[key]
            for key in (
                "ticket_id",
                "ticket_code",
                "ticket_generation",
                "ticket_version",
            )
        },
        "resident": {
            key: p[key] for key in ("resident_id", "resident_name", "phone_number")
        },
        "location": {
            key: p[key]
            for key in (
                "location_scope_id",
                "unit_id",
                "unit_number",
                "building_id",
                "building_code",
                "building_name",
            )
        },
        "request": {
            "title": i["title"],
            "description": i["description"],
            "handoff_reason": state["handoff_reason"],
            **{
                key: t[key]
                for key in (
                    "request_kind",
                    "priority",
                    "severity",
                    "is_emergency",
                    "triage_decision_id",
                )
            },
        },
        "facts": parse_facts(i["facts"]),
        "file_ids": strings(i["file_ids"]),
        "created_at": ticket["created_at"],
    }


def parse_turn(content, message_ids, earlier_message_ids=()) -> dict:
    if not isinstance(content, str) or len(content) > 32768:
        raise GraphFault("INVALID_RESIDENT_TURN")
    try:
        v = record(json.loads(content))
    except (ValueError, GraphFault):
        raise GraphFault("INVALID_RESIDENT_TURN") from None
    if set(v) - {"intent", "title", "description", "facts", "answers"}:
        raise GraphFault("INVALID_RESIDENT_TURN")
    parsed_facts = parse_facts(v.get("facts", []))
    allowed_message_ids = (
        {message_ids} if isinstance(message_ids, str) else set(strings(message_ids, 32))
    )
    # Models repeat facts from earlier turns of the same conversation. Those were handled
    # in their own turn, so they are dropped here; a source that never existed still faults.
    parsed_facts = [
        fact
        for fact in parsed_facts
        if fact["source_message_id"] in allowed_message_ids
        or fact["source_message_id"] not in earlier_message_ids
    ]
    if any(
        fact["source"] == "staff_verified"
        or fact["source_message_id"] not in allowed_message_ids
        for fact in parsed_facts
    ):
        raise GraphFault("MODEL_CANNOT_VERIFY_FACTS")
    answers = record(v.get("answers", {}))
    if len(answers) > 32:
        raise GraphFault("INVALID_RESIDENT_TURN")
    return {
        "intent": choice(
            v.get("intent"),
            ("information", "status", "cancel", "new_incident", "interaction_answer"),
        ),
        **{key: text(v[key]) for key in ("title", "description") if key in v},
        "facts": parsed_facts,
        "answers": {text(key): text(value) for key, value in answers.items()},
    }


def parse_supervisor_event(value, state) -> dict:
    v = record(value)
    p = record(v.get("payload"))
    ticket, route, ack, envelope = (
        state.get(key) for key in ("ticket", "route", "ack", "event")
    )
    if not all((ticket, route, ack, envelope)):
        raise GraphFault("EVENT_CONTEXT_MISSING")
    version, event_id = integer(v.get("aggregate_version")), text(v.get("event_id"))
    expected = {
        "tenant_id": state["owner"]["tenantId"],
        "ticket_id": ticket["ticket_id"],
        "ticket_code": ticket["ticket_code"],
        "ticket_generation": ticket["ticket_generation"],
        "workspace_id": route["workspace_id"],
        "team_id": route["team_id"],
        "correlation_id": ack["correlation_id"],
    }
    if (
        event_id != envelope["eventId"]
        or v.get("binding_id") != state["reception_binding_id"]
        or version != envelope["aggregateVersion"]
        or version <= state["last_event_version"]
        or version < ticket["aggregate_version"]
        or event_id in state["processed_event_ids"]
        or any(p.get(key) != val for key, val in expected.items())
    ):
        raise GraphFault("EVENT_STALE_OR_MISMATCH")
    payload = {
        "schema_version": choice(p.get("schema_version"), ("1.0",)),
        **{
            key: text(p.get(key))
            for key in (
                "message_id",
                "correlation_id",
                "tenant_id",
                "workspace_id",
                "team_id",
                "ticket_id",
                "ticket_code",
                "ticket_version",
                "supervisor_run_id",
                "customer_message",
            )
        },
        "sent_at": timestamp(p.get("sent_at")),
        "ticket_generation": integer(p.get("ticket_generation")),
        "status": choice(
            p.get("status"),
            ("accepted", "in_progress", "waiting_for_customer", "completed", "failed"),
        ),
    }
    if "requested_information" in p:
        info = record(p["requested_information"])
        if (
            not isinstance(info.get("questions"), list)
            or not 0 < len(info["questions"]) <= 32
        ):
            raise GraphFault("INVALID_WORKFLOW_OUTPUT")
        questions = [
            {
                "field_id": text(record(q).get("field_id")),
                "question": text(q.get("question")),
                "required": boolean(q.get("required")),
            }
            for q in info["questions"]
        ]
        if len({q["field_id"] for q in questions}) != len(questions):
            raise GraphFault("INVALID_WORKFLOW_OUTPUT")
        payload["requested_information"] = {
            "interaction_id": text(info.get("interaction_id")),
            "questions": questions,
        }
    if payload["status"] == "waiting_for_customer" and (
        "requested_information" not in payload or "interaction_revision" not in v
    ):
        raise GraphFault("INTERACTION_REVISION_REQUIRED")
    if "result" in p:
        r = record(p["result"])
        payload["result"] = {
            "outcome": choice(
                r.get("outcome"),
                ("work_completed", "needs_human_review", "unable_to_resolve"),
            ),
            "summary": text(r.get("summary")),
            "work_order_ids": strings(r.get("work_order_ids")),
            "evidence_ids": strings(r.get("evidence_ids")),
        }
    if "error" in p:
        e = record(p["error"])
        payload["error"] = {
            "code": text(e.get("code")),
            "retryable": boolean(e.get("retryable")),
            "message": text(e.get("message")),
        }
    return {
        "event_id": event_id,
        "aggregate_version": version,
        "binding_id": text(v.get("binding_id")),
        "payload": payload,
        **(
            {"interaction_revision": integer(v["interaction_revision"])}
            if "interaction_revision" in v
            else {}
        ),
    }
