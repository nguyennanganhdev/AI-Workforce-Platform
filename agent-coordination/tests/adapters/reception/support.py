"""Backend/auth test doubles, not production policy or durable storage."""
import asyncio
import copy
import json

from adapters.backend.client import HttpResponse
from adapters.backend.errors import AdapterError
from adapters.backend.messages import fingerprint
from backend.support import CONTEXT, Validator, client


def input_message(kind="ticket_submitted", *, identity="input-1", version="1", **changes):
    wire = dict(schema_version="2.0", message_id=identity, correlation_id="conversation-1",
        sent_at="2026-10-01T00:00:00Z", message_type=kind, message="Rò nước tại bếp",
        tenant_id=CONTEXT["tenant_id"], domain_id=CONTEXT["domain_id"], domain_name="Dịch vụ",
        workspace_id=CONTEXT["workspace_id"], team_id="team-1", ticket_id=CONTEXT["ticket_id"],
        ticket_code="T-1", ticket_generation=CONTEXT["ticket_generation"], ticket_version=version,
        resident=dict(resident_id="resident-1", resident_name="Cư dân", phone_number="0123456789"),
        location=dict(location_scope_id="scope-1", unit_id="unit-1", unit_number="101",
                      building_id="building-1", building_code="B1", building_name="Tòa B1"),
        request=dict(title="Rò nước", description="Ống nước bếp bị rò", request_kind="incident",
            priority="normal", severity="minor", is_emergency=False, handoff_reason="needs_staff"),
        facts=[dict(key="nguyên_nhân", value=None, source="customer_report", source_message_id="source-1")],
        file_ids=["photo-1"], created_at="2026-09-30T18:00:00+07:00")
    if kind != "ticket_submitted":
        wire["source_message_id"] = "source-reply-1"
    wire.update(changes)
    return wire


def output_message(kind="accepted", *, identity="output-1", version="1", **changes):
    source = input_message()
    wire = {key: source[key] for key in ("schema_version", "correlation_id", "sent_at",
        "tenant_id", "workspace_id", "team_id", "ticket_id", "ticket_code", "ticket_generation")}
    wire.update(message_id=identity, message_type=kind, message="Thông báo đã được backend cho phép",
                ticket_version=version, supervisor_run_id="supervisor-run-1")
    if kind == "completed":
        wire["result"] = dict(outcome="work_completed", summary="Đã nghiệm thu",
                              work_order_ids=["work-1"], evidence_ids=["after-1"])
    wire.update(changes)
    return wire


class Authentication:
    async def headers(self, authentication):
        if authentication != "verified-source":
            raise AdapterError("reception_not_authorized")
        return {"X-Reception-Source-Proof": "test-source-proof"}


class V2Transport:
    def __init__(self):
        self.calls, self.receipts, self.decisions, self.delivered = [], {}, {}, []
        self.context = dict(CONTEXT)
        self.response = None
        self.failure = None
        self.current_version = None
        self.pending = None
        self.management_approved = True
        self.qc_approved = True
        self.cancelled = False
        self.room_command = None
        self.lock = asyncio.Lock()

    @staticmethod
    def response_json(value):
        return HttpResponse(202, json.dumps(value, ensure_ascii=False).encode())

    async def post(self, url, *, headers, body, timeout):
        wire = json.loads(body)
        self.calls.append((url, dict(headers), copy.deepcopy(wire), timeout))
        if self.failure:
            raise self.failure
        if self.response is not None:
            return self.response
        async with self.lock:
            incoming = url.endswith("reception.verify")
            message = wire if incoming else wire["message"]
            if incoming and headers.get("X-Reception-Source-Proof") != "test-source-proof":
                return HttpResponse(403, b"private backend diagnostic")
            if any(message[k] != self.context[k] for k in
                   ("tenant_id", "workspace_id", "ticket_id", "ticket_generation")):
                return HttpResponse(403, b"wrong scope")
            key = (message["tenant_id"], message["message_id"])
            digest = fingerprint(wire)
            previous = self.receipts.get(key)
            if previous:
                return (self.response_json(previous[1]) if previous[0] == digest
                        else HttpResponse(409, b"changed body"))
            if self.current_version is not None and message["ticket_version"] != self.current_version:
                return self.response_json(dict(message_id=message["message_id"], status="error",
                    error=dict(code="stale_version", retryable=False)))
            kind = message["message_type"]
            if incoming:
                if kind in ("plan_approved", "plan_rejected", "plan_change_requested"):
                    step = (message["tenant_id"], message["ticket_id"], message["ticket_generation"],
                            message["ticket_version"])
                    old = self.decisions.get(step)
                    if old is not None and old != kind:
                        return HttpResponse(409, b"decision conflict")
                    if old is None:
                        if self.pending != "plan_approval_requested":
                            return HttpResponse(409, b"wrong waiting step")
                        self.decisions[step] = kind
                        self.pending = None
                data = dict(message=copy.deepcopy(message), context=copy.deepcopy(self.context),
                            supervisor_run_id="supervisor-run-1")
                if self.room_command is not None:
                    data["room_command"] = copy.deepcopy(self.room_command)
            else:
                if ((kind == "plan_approval_requested" and not self.management_approved)
                        or (kind == "completed" and not self.qc_approved)
                        or (kind == "cancelled" and not self.cancelled)):
                    return HttpResponse(403, b"not authorized")
                if kind in ("information_requested", "plan_approval_requested"):
                    if self.pending is not None:
                        return HttpResponse(409, b"request already pending")
                    self.pending = kind
                self.delivered.append(copy.deepcopy(message))
                data = {}
            receipt = dict(message_id=message["message_id"], status="accepted", data=data)
            self.receipts[key] = (digest, copy.deepcopy(receipt))
            return self.response_json(receipt)


def gateway_parts(**kwargs):
    from adapters.reception.reception_gateway import ReceptionGateway

    transport, validator = V2Transport(), Validator()
    backend = client(transport, validator, **kwargs)
    gateway = ReceptionGateway(backend, authentication=Authentication())
    return gateway, transport, validator
