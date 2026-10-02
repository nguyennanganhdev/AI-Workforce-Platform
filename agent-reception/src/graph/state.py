"""Python-only state envelope. No implicit migration from TypeScript checkpoints."""

from __future__ import annotations

from typing import Any, TypedDict

PYTHON_CONTRACT_VERSION = "0.1.0-python.draft.1"
STATE_SCHEMA_VERSION = 1
PD01_RUNTIME_VERSION = "pd01-python-1"


class GraphState(TypedDict):
    data: dict[str, Any]


def belongs_to(state: dict, context: dict) -> bool:
    return state.get("owner") == {
        key: context[key]
        for key in ("tenantId", "principalId", "initiatedBy", "bindingId")
    }


def initial_state(request: dict) -> dict:
    context = request["context"]
    return {
        "schemaVersion": 1,
        "runtime_version": PD01_RUNTIME_VERSION,
        "owner": {
            key: context[key]
            for key in ("tenantId", "principalId", "initiatedBy", "bindingId")
        },
        "phase": "intake",
        "operationId": request["operationId"],
        "message": request["message"],
        "reported": [request["message"]],
        "confirmed": [],
        "inferences": [],
        "decision": None,
        "pendingTool": None,
        "lastToolResult": None,
        "ticket": None,
        "reply": "",
        "clarifications": 0,
        "steps": 0,
        "toolSequence": 0,
    }
