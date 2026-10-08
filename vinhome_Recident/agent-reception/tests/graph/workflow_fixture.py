"""Synthetic ports confined to tests; exercises the real Python LangGraph."""

import asyncio
import inspect
import json
import sys
from copy import deepcopy
from functools import wraps
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from src.graph import (
    GraphDependencies,
    WorkflowOptions,
    create_reception_workflow_factory,
)
from src.graph.decision import compact_json

REQUEST = {
    "operationId": "resident-operation-1",
    "message": {
        "id": "message-1",
        "text": "Vòi nước tại bếp bị rò.",
        "fileIds": ["file-synthetic-1"],
    },
    "context": {
        "principalId": "principal-synthetic",
        "tenantId": "tenant-synthetic",
        "initiatedBy": "resident-synthetic",
        "bindingId": "binding-synthetic",
        "checkpoint": {"namespace": "workflow-test", "threadId": "thread-synthetic"},
        "runId": "run-synthetic",
        "requestId": "request-synthetic",
        "permissions": ["test:only"],
    },
}
PROFILE = {
    "resident_id": "resident-record-synthetic",
    "resident_name": "Cư dân mẫu",
    "phone_number": "synthetic-phone",
    "unit_id": "unit-synthetic",
    "unit_number": "Căn hộ mẫu",
    "building_id": "building-synthetic",
    "building_code": "TEST",
    "building_name": "Tòa mẫu",
    "domain_id": "domain-synthetic",
    "domain_name": "Domain mẫu",
    "location_scope_id": "scope-synthetic",
}
INFORMATION = json.dumps(
    {
        "intent": "information",
        "title": "Rò nước",
        "description": "Vòi nước tại bếp bị rò.",
        "facts": [
            {
                "key": "location",
                "value": "bếp",
                "source": "customer_report",
                "source_message_id": "message-1",
            }
        ],
        "answers": {},
    }
)


def async_test(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        return asyncio.run(fn(*args, **kwargs))

    return wrapped


class ScriptedModel:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    async def ainvoke(self, messages):
        self.calls.append(messages)
        value = self.responses[min(len(self.calls) - 1, len(self.responses) - 1)]
        if isinstance(value, Exception):
            raise value
        return AIMessage(content=value)


def turn(intent, **extra):
    return json.dumps({"intent": intent, "facts": [], "answers": {}, **extra})


class Intake:
    def __init__(self, policy=None, knowledge=None):
        self.policy = (
            policy
            if policy is not None
            else {
                "kind": "needs_staff",
                "reason": "test-policy-rule",
                "policyVersion": "policy-test-1",
            }
        )
        self.knowledge = (
            knowledge if knowledge is not None else {"kind": "insufficient"}
        )
        self.calls = []

    async def evaluate_policy(self, request):
        self.calls.append("policy")
        if isinstance(self.policy, Exception):
            raise self.policy
        return deepcopy(self.policy)

    async def search_knowledge(self, request):
        self.calls.append("knowledge")
        if isinstance(self.knowledge, Exception):
            raise self.knowledge
        return deepcopy(self.knowledge)


def harness(model=None, override=None, assess_model=None, **options):
    saver = options.pop("checkpointer", None) or InMemorySaver()
    calls, saved_plans, reconciliations = [], [], []
    mutable = {
        "ticket": {
            "ticket_id": "ticket-synthetic",
            "ticket_code": "TK-TEST",
            "ticket_generation": 0,
            "ticket_version": "1",
            "aggregate_version": 1,
            "created_at": "2026-09-30T00:00:00.000Z",
        },
        "event": None,
        "status": "in_progress",
        "confirmed": False,
    }

    def bump():
        ticket = mutable["ticket"]
        ticket = {
            **ticket,
            "aggregate_version": ticket["aggregate_version"] + 1,
            "ticket_version": str(ticket["aggregate_version"] + 1),
        }
        mutable["ticket"] = ticket
        return deepcopy(ticket)

    def output(call):
        op, ticket = call["operation"], deepcopy(mutable["ticket"])
        if op == "create_ticket_draft":
            return ticket
        if op == "get_verified_resident_context":
            return {"kind": "verified", "profile": deepcopy(PROFILE)}
        if op == "update_ticket_incident":
            return {
                "ticket": bump(),
                "incident": call["input"]["incident"],
                "missing_fields": [],
            }
        if op == "submit_ticket_assessment":
            return {
                "ticket": bump(),
                "triage": {
                    "status": "applied",
                    "policy_version": "policy-test-1",
                    "triage_decision_id": "triage-synthetic",
                    "request_kind": "incident",
                    "priority": "normal",
                    "severity": "minor",
                    "is_emergency": False,
                },
            }
        if op == "resolve_management_destination":
            return {
                "kind": "resolved",
                "route": {
                    "destination_id": "destination-synthetic",
                    "workspace_id": "workspace-synthetic",
                    "team_id": "team-synthetic",
                    "route_revision": 1,
                    "coordination_binding_id": "coordination-synthetic",
                    "building_id": PROFILE["building_id"],
                    "domain_id": PROFILE["domain_id"],
                    "ticket_version": ticket["ticket_version"],
                },
            }
        if op == "handoff_ticket":
            return {
                "persisted": True,
                "enqueued": True,
                "correlation_id": call["input"]["message"]["correlation_id"],
                "operation_id": "handoff-operation-synthetic",
            }
        if op == "register_supervisor_wait":
            return {"registered": True}
        if op == "get_supervisor_event":
            return deepcopy(mutable["event"])
        if op == "append_ticket_information":
            return {
                "ticket": bump(),
                "delivered": True,
                "scope_changed": False,
                "linked_file_ids": call["input"].get("file_ids", []),
            }
        if op == "respond_supervisor_interaction":
            return {
                "ticket": bump(),
                "status": "accepted",
                "linked_file_ids": call["input"].get("file_ids", []),
            }
        if op == "request_ticket_cancellation":
            return {"ticket": bump(), "status": "accepted"}
        if op == "get_ticket_status":
            return {
                "ticket": ticket,
                "status": mutable["status"],
                "completion_confirmed": mutable["confirmed"],
                "scope_changed": False,
            }
        if op == "escalate_emergency":
            return {
                "persisted": True,
                "enqueued": True,
                "operation_id": "emergency-synthetic",
                "policy_version": call["input"]["policy_version"],
                **({"ticket": bump()} if "ticket_id" in call["input"] else {}),
            }
        if op == "process_self_help":
            return {
                "status": "offered",
                "attempt_id": "attempt-synthetic",
                "policy_version": call["input"]["policy_version"],
                "procedure": {
                    "approved": True,
                    "eligible": True,
                    "policy_version": call["input"]["policy_version"],
                    "version": "procedure-synthetic-1",
                    "expires_at": "2026-10-01T00:00:00Z",
                    "steps": ["Bước thử nghiệm đã duyệt."],
                    "stop_conditions": ["Dừng nếu có dấu hiệu nguy hiểm."],
                    "retrievalRunId": "self-help-retrieval-synthetic",
                    "citations": [
                        {
                            "documentId": "procedure-synthetic",
                            "version": "1",
                            "chunkId": "step-synthetic",
                        }
                    ],
                },
            }
        raise AssertionError(op)

    class Tools:
        async def invoke(self, call):
            calls.append(call)
            if call["operation"] != "get_supervisor_event":
                context = call["context"]["checkpoint"]
                saved = await saver.aget_tuple(
                    {
                        "configurable": {
                            "thread_id": compact_json(
                                [context["namespace"], context["threadId"]]
                            ),
                            "checkpoint_ns": "",
                        }
                    }
                )
                assert (
                    saved.checkpoint["channel_values"]["data"]["pending"][
                        "idempotencyKey"
                    ]
                    == call["idempotencyKey"]
                )
                saved_plans.append(call["idempotencyKey"])
            result = output(call)
            changed = override(call, result) if override else None
            if inspect.isawaitable(changed):
                changed = await changed
            return (
                changed if changed is not None else {"kind": "success", "value": result}
            )

    async def resolve_session(context, signal):
        return {
            "channel_id": "channel-synthetic",
            "reception_session_id": "session-synthetic",
        }

    async def reconcile(call):
        reconciliations.append(call)
        return {"kind": "success", "value": output(call)}

    intake = options.get("intake", Intake())

    class Policy:
        async def evaluate_request(self, request):
            policy = await intake.evaluate_policy(request)
            return {
                "policy_version": policy["policyVersion"],
                "emergency": policy["kind"] == "emergency",
                "staff_required": policy["kind"] == "needs_staff",
                "self_help_allowed": False,
                "missing_information": [policy["question"]]
                if policy["kind"] == "clarify"
                else [],
                "handoff_reason": "emergency"
                if policy["kind"] == "emergency"
                else policy.get("handoffReason", "needs_staff"),
            }

    assessment_model = ScriptedModel(
        assess_model
        or [
            json.dumps(
                {
                    "intent": "information"
                    if intake.policy.get("kind") == "knowledge_chat"
                    else "incident",
                    "proposed_action": "retrieve_knowledge"
                    if intake.policy.get("kind") == "knowledge_chat"
                    else "start_ticket",
                    "explicit_staff_request": False,
                    "self_help_declined": False,
                    "self_help_failed": False,
                    "emergency_signals": [],
                    "missing_information": [],
                    "reason": "synthetic classification",
                }
            )
        ]
    )
    extraction_model = ScriptedModel(model or [INFORMATION])

    class WorkflowModel:
        async def ainvoke(self, messages):
            if "NODE assess_request" in messages[0].content:
                return await assessment_model.ainvoke(messages)
            return await extraction_model.ainvoke(messages)

    opts = WorkflowOptions(
        **{
            "intake": intake,
            "request_policy": Policy(),
            "resolve_session": resolve_session,
            "now": lambda: "2026-09-30T00:00:00.000Z",
            "reconcile": reconcile,
            **options,
        }
    )
    dependencies = GraphDependencies(
        model=WorkflowModel(), tools=Tools(), checkpointer=saver
    )
    factory = create_reception_workflow_factory(opts)
    return SimpleNamespace(
        graph=factory.create(dependencies),
        factory=factory,
        options=opts,
        dependencies=dependencies,
        saver=saver,
        calls=calls,
        saved_plans=saved_plans,
        reconciliations=reconciliations,
        mutable=mutable,
        assessment_model=assessment_model,
        extraction_model=extraction_model,
    )


def waiting(result):
    assert result["status"] == "interrupted", result
    return result


def resident_resume(result, message=None):
    result = waiting(result)
    message = message or {"id": "message-2", "text": "Tôi bổ sung thông tin."}
    return {
        "context": deepcopy(REQUEST["context"]),
        "operationId": "operation:" + message["id"],
        "interruptId": result["interrupts"][0]["id"],
        "source": {"kind": "resident", "message": message},
    }


def event_fixture(result, status="in_progress", event_id="event-synthetic-1"):
    state = waiting(result)["state"]
    ticket = state["ticket"]
    version = max(ticket["aggregate_version"], state["last_event_version"]) + 1
    event = {
        "event_id": event_id,
        "binding_id": state["reception_binding_id"],
        "aggregate_version": version,
        "payload": {
            "schema_version": "1.0",
            "message_id": "message:" + event_id,
            "correlation_id": state.get("ack", {}).get(
                "correlation_id", "pending-correlation"
            ),
            "sent_at": "2026-09-30T01:00:00.000Z",
            "tenant_id": state["owner"]["tenantId"],
            "workspace_id": state.get("route", {}).get(
                "workspace_id", "pending-workspace"
            ),
            "team_id": state.get("route", {}).get("team_id", "pending-team"),
            "ticket_id": ticket["ticket_id"],
            "ticket_code": ticket["ticket_code"],
            "ticket_generation": ticket["ticket_generation"],
            "ticket_version": str(version),
            "supervisor_run_id": "supervisor-run-synthetic",
            "status": status,
            "customer_message": "Bộ phận xử lý đang xem xét ticket.",
        },
    }
    resume = {
        "context": deepcopy(REQUEST["context"]),
        "operationId": "event-operation:" + event_id,
        "interruptId": result["interrupts"][0]["id"],
        "source": {
            "kind": "backend",
            "event": {
                "eventId": event_id,
                "aggregateVersion": version,
                "ticketId": ticket["ticket_id"],
                "generation": ticket["ticket_generation"],
                "bindingId": state["reception_binding_id"],
                "interruptId": result["interrupts"][0]["id"],
            },
        },
    }
    return event, resume


def set_event(h, event):
    h.mutable["event"] = event
    h.mutable["ticket"].update(
        ticket_version=event["payload"]["ticket_version"],
        aggregate_version=event["aggregate_version"],
    )
