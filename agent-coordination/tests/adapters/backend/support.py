"""Test-only collaborators. No production auth, schema or durability claims."""

import asyncio
import copy
import json

from adapters.backend.client import BackendClient, HttpResponse
from adapters.backend.errors import AdapterError
from adapters.backend.events import ResolvedEvent


CONTEXT = {
    "tenant_id": "tenant-a", "principal_id": "service-1",
    "initiated_by_user_id": "resident-1", "domain_id": "domain-1",
    "workspace_id": "workspace-1", "ticket_id": "ticket-1",
    "ticket_generation": 1, "binding_id": "binding-1", "run_id": "run-1",
}


def payload(kind):
    examples = {
        "ticket.submitted": {"report": "Trần bị rò nước gần ổ điện", "facts": {"vi_tri": "bếp"},
                             "attachment_ids": ["file-1"]},
        "resident.message": {"text": "Nước chảy liên tục", "reply_to_request_id": "question-1"},
        "resident.question": {"question_id": "question-1", "question": "Nước chảy khi nào?"},
        "resident.update": {"summary": "Đã nhận phản ánh", "status": "in_progress",
                            "attachment_ids": []},
        "approval.requested": {
            "approval_id": "approval-2", "stage": "resident_plan", "plan_id": "plan-1",
            "plan_version": 2, "depends_on_approval_id": "approval-1",
            "recipient_user_id": "resident-1", "delivery_channel": "reception",
            "summary": "Thay đoạn ống", "steps": ["Kiểm tra", "Thay ống"],
            "cost": {"amount": 300000, "currency": "VND", "kind": "estimate"},
            "attachment_ids": [], "expires_at": "2026-10-01T10:00:00+07:00",
        },
        "approval.responded": {
            "approval_id": "approval-2", "stage": "resident_plan",
            "plan_id": "plan-1", "plan_version": 2, "decision": "approve", "comment": "",
        },
        "assignment.offered": {"assignment_id": "assignment-1", "assignment_version": 1,
                               "plan_id": "plan-1", "plan_version": 2},
        "assignment.responded": {"assignment_id": "assignment-1", "assignment_version": 1,
                                 "plan_id": "plan-1", "plan_version": 2, "decision": "accept"},
        "work.completed": {"assignment_id": "assignment-1", "assignment_version": 1,
                           "result_id": "result-1", "result_version": 1,
                           "before_file_ids": ["before"], "after_file_ids": ["after"],
                           "summary": "Đã sửa, chờ nghiệm thu"},
        "completion.requested": {
            "confirmation_id": "confirmation-1", "result_id": "result-1", "result_version": 1,
            "plan_id": "plan-1", "plan_version": 2, "recipient_user_id": "resident-1",
            "summary": "Đã nghiệm thu", "evidence_file_ids": ["before", "after"],
            "final_cost": {"amount": 300000, "currency": "VND"},
        },
        "completion.responded": {"confirmation_id": "confirmation-1", "result_id": "result-1",
                                 "result_version": 1, "decision": "not_satisfied",
                                 "comment": "Vẫn rỉ nước"},
    }
    return copy.deepcopy(examples[kind])


def request(kind="ticket.submitted", **context_changes):
    return {
        "contract_version": "1", "type": kind, "request_id": "request-1",
        "trace_id": "trace-1", "idempotency_key": "command-1",
        "context": {**CONTEXT, **context_changes}, "payload": payload(kind),
    }


def event(kind="ticket.submitted", *, event_id="event-1", ticket_id="ticket-1", tenant="tenant-a"):
    return {
        "event_id": event_id, "event_type": f"backend.{kind}", "schema_version": "1",
        "tenant_id": tenant, "aggregate_id": ticket_id, "aggregate_version": 3,
        "occurred_at": "2026-09-30T10:00:00Z", "correlation_id": "trace-1",
        "causation_id": "request-1", "payload": payload(kind),
    }


class Validator:
    """Spy standing in for DEV-5 canonical validation. Local guards run for real."""
    def __init__(self):
        self.seen = []
        self.reject = None

    def validate(self, kind, value):
        self.seen.append((kind, copy.deepcopy(value)))
        if kind == self.reject:
            raise ValueError("sensitive validator diagnostic")


class Headers:
    async def headers(self):
        return {"Authorization": "Bearer test-credential"}


class Transport:
    def __init__(self):
        self.calls = []
        self.response = None
        self.failure = None

    async def post(self, url, *, headers, body, timeout):
        self.calls.append((url, dict(headers), json.loads(body), timeout))
        if self.failure:
            raise self.failure
        if self.response is not None:
            return self.response
        return HttpResponse(202, json.dumps({
            "request_id": json.loads(body)["request_id"], "status": "accepted",
            "data": {"operation_id": "operation-1"},
        }).encode())


OPERATIONS = (
    "reception.ticket", "reception.message", "reception.question", "reception.update",
    "approval.request", "approval.respond", "completion.request", "completion.respond",
    "assignment.offer", "assignment.respond", "work.complete",
)


def client(transport=None, validator=None, **kwargs):
    return BackendClient(
        base_url="https://backend.test", routes={op: f"/test/{op}" for op in OPERATIONS},
        transport=transport or Transport(), headers=kwargs.pop("headers", Headers()),
        validator=validator or Validator(), **kwargs,
    )


class Verifier:
    def __init__(self):
        self.failure = None
        self.calls = []
        self.contexts = {"ticket-1": dict(CONTEXT)}

    async def resolve(self, value, authentication):
        self.calls.append(copy.deepcopy(value))
        if authentication != "test-backend-signature":
            raise AdapterError("event_not_authorized")
        if self.failure:
            raise AdapterError(self.failure)
        return ResolvedEvent(self.contexts[value["aggregate_id"]])


class Inbox:
    """Only a test double for atomic inbox contract, NOT restart-safe storage."""
    def __init__(self):
        self.items = {}
        self.lock = asyncio.Lock()

    async def enqueue_once(self, delivery):
        async with self.lock:
            key = (delivery.tenant_id, delivery.event_id)
            old = self.items.get(key)
            if old is not None:
                if old.fingerprint != delivery.fingerprint:
                    raise AdapterError("conflict")
                return False
            self.items[key] = copy.deepcopy(delivery)
            return True
