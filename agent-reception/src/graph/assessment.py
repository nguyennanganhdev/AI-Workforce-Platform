"""Strict LLM proposals and authoritative request policy, never a tool catalog."""

import json
from datetime import datetime

from .decision import GraphFault
from .intake import valid_knowledge
from .workflow_validation import boolean, choice, record, strings, text, timestamp

INTENTS = ("information", "incident", "service_request", "ticket_follow_up")
ACTIONS = (
    "retrieve_knowledge",
    "ask_clarification",
    "retrieve_self_help",
    "start_ticket",
    "continue_existing_ticket",
    "emergency_handoff",
)
ASSESSMENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "intent": {"type": "string", "enum": list(INTENTS)},
        "proposed_action": {"type": "string", "enum": list(ACTIONS)},
        "explicit_staff_request": {"type": "boolean"},
        "self_help_declined": {"type": "boolean"},
        "self_help_failed": {"type": "boolean"},
        "emergency_signals": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 16,
        },
        "missing_information": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 16,
        },
        "reason": {"type": "string", "minLength": 1, "maxLength": 1024},
    },
}
ASSESSMENT_SCHEMA["required"] = list(ASSESSMENT_SCHEMA["properties"])


def parse_assessment(content):
    try:
        if not isinstance(content, str) or len(content) > 16384:
            raise ValueError
        value = record(json.loads(content))
        if set(value) != set(ASSESSMENT_SCHEMA["required"]):
            raise ValueError
        return {
            "intent": choice(value["intent"], INTENTS),
            "proposed_action": choice(value["proposed_action"], ACTIONS),
            **{
                key: boolean(value[key])
                for key in (
                    "explicit_staff_request",
                    "self_help_declined",
                    "self_help_failed",
                )
            },
            "emergency_signals": strings(value["emergency_signals"], 16),
            "missing_information": strings(value["missing_information"], 16),
            "reason": text(value["reason"], 1024),
        }
    except (ValueError, GraphFault, TypeError, KeyError):
        raise GraphFault("INVALID_REQUEST_ASSESSMENT") from None


def parse_request_policy(raw):
    value = record(raw)
    result = {
        "policy_version": text(value.get("policy_version")),
        **{
            key: boolean(value.get(key))
            for key in ("emergency", "staff_required", "self_help_allowed")
        },
        "missing_information": strings(value.get("missing_information"), 16),
        "handoff_reason": choice(
            value.get("handoff_reason"),
            ("needs_staff", "self_help_declined", "self_help_failed", "emergency"),
        ),
    }
    if "safety_guidance" in value:
        guide = value["safety_guidance"]
        if (
            isinstance(guide, dict)
            and guide.get("approved") is True
            and valid_knowledge({**guide, "kind": "sufficient"})
        ):
            result["safety_guidance"] = {
                key: guide[key]
                for key in ("approved", "answer", "retrievalRunId", "citations")
            }
        else:
            # Bad guidance cannot delay a confirmed emergency alert or become advice.
            result["safety_guidance_error"] = "UNAPPROVED_SAFETY_GUIDANCE"
    return result


def decide_request(proposal, policy, active_ticket_id):
    action = proposal["proposed_action"]
    if policy["emergency"]:
        action = "emergency_handoff"
    elif active_ticket_id:
        action = (
            "retrieve_knowledge"
            if proposal["intent"] == "information"
            and not policy["staff_required"]
            and not proposal["explicit_staff_request"]
            and not proposal["emergency_signals"]
            and not policy["missing_information"]
            and not proposal["missing_information"]
            else "continue_existing_ticket"
        )
    elif policy["staff_required"]:
        action = "start_ticket"
    elif (
        policy["missing_information"]
        or proposal["missing_information"]
        or proposal["emergency_signals"]
    ):
        action = "ask_clarification"
    elif proposal["intent"] == "information" and not any(
        proposal[key]
        for key in ("explicit_staff_request", "self_help_declined", "self_help_failed")
    ):
        action = "retrieve_knowledge"
    elif (
        action == "retrieve_self_help"
        and policy["self_help_allowed"]
        and not any(
            proposal[key]
            for key in (
                "explicit_staff_request",
                "self_help_declined",
                "self_help_failed",
            )
        )
    ):
        action = "retrieve_self_help"
    else:
        action = "ask_clarification"
    return {
        **proposal,
        "next_action": action,
        "policy_version": policy["policy_version"],
        "missing_information": list(
            dict.fromkeys(
                policy["missing_information"] + proposal["missing_information"]
            )
        ),
    }


def parse_procedure(value, now):
    expires = timestamp(value.get("expires_at"))
    if datetime.fromisoformat(expires.replace("Z", "+00:00")) <= datetime.fromisoformat(
        timestamp(now).replace("Z", "+00:00")
    ):
        raise GraphFault("SELF_HELP_EXPIRED")
    steps, stops = (
        strings(value.get("steps"), 32),
        strings(value.get("stop_conditions"), 16),
    )
    if (
        not steps
        or not stops
        or not valid_knowledge(
            {
                "kind": "sufficient",
                "answer": "\n".join(steps),
                "retrievalRunId": value.get("retrievalRunId"),
                "citations": value.get("citations"),
            }
        )
    ):
        raise GraphFault("SELF_HELP_SOURCES_REQUIRED")
    return {
        "version": text(value.get("version")),
        "steps": steps,
        "stop_conditions": stops,
        "expires_at": expires,
        "citations": value["citations"],
        "retrievalRunId": value["retrievalRunId"],
    }
