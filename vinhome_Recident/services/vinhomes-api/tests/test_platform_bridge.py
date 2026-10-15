"""The bridge to the AI platform (docs/domain/NOI_WORKFORCE_V1.md), against migrated, seeded PostgreSQL.

No network: FakePlatform answers the way /workforce/v1 does (strict bodies, idempotency by external_request_id, the
error envelope, 200 or 202, the event log with cursors, the signed provider endpoint).
"""

import asyncio
import hashlib
import hmac
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import asyncpg
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from test_domain_database import operation
from test_resident_contract import CATEGORY, TENANT, client, image, key, sql
from test_resident_contract import database as database  # noqa: PLC0414 -- pytest fixture export
from test_staff_dispatch import accept, advance, offer

from vinhomes_api import platform as bridge
from vinhomes_api import platform_sync
from vinhomes_api.main import create_app
from vinhomes_api.platform import FAILED_TEXT, SILENT_TEXT, Bridge, Platform, event_body, provider_events, sign
from vinhomes_api.platform_sync import CLOSE_TRIES, run_once
from vinhomes_api.v3_reception_runtime import emergency_kind
from vinhomes_api.v3_config import V3Settings

CUSTOMER_KEY, PROVIDER_KEY = "dp_customer01.customer-secret-0001", "dp_provider01.provider-secret-0001"
KEY_ID, SECRET = "sig_test_01", "signing-secret-of-the-test"
BRIDGE = Bridge("http://platform.test", CUSTOMER_KEY, PROVIDER_KEY, KEY_ID, SECRET, "")
NOW = "2026-10-11T02:00:00Z"
REQUEST_FIELDS = {"schema_version", "command_type", "external_request_id", "external_management_ref", "external_user_id",
                  "external_ticket_id", "external_conversation_id", "workflow_id", "residence_id", "timezone", "message"}
DECISION_FIELDS = {"schema_version", "external_request_id", "external_user_id", "external_ticket_id",
                   "external_conversation_id", "workflow_id", "decision", "expected_revision", "arguments_hash", "quote_ref"}
CLOSE_FIELDS = {"schema_version", "external_request_id", "external_user_id", "external_ticket_id",
                "external_conversation_id", "expected_revision", "reason", "stop_tracking_only"}
EVENT_FIELDS = {"schema_version", "external_event_id", "external_job_id", "client_reference", "event_type",
                "provider_version", "occurred_at", "data"}
STATE_EVENT = {"closed": "workflow.closed", "awaiting_user": "workflow.awaiting_user", "needs_attention": "workflow.needs_attention"}


def refusal(status, code, **details):
    return httpx.Response(status, json={"error": {"code": code, "message": code.lower(), "details": details,
                                                  "request_id": "req_test", "retryable": status >= 500}})


class FakePlatform:
    def __init__(self, wait=True, page=500):
        self.wait = wait        # False: the turn does not end in time: 202, result null, the messages only as events
        self.page = page        # the most events one history call returns
        self.down = False       # the platform cannot be reached
        self.refuse = None      # (status, code) for the next customer POST
        self.expired = False    # the next history call finds its cursor purged
        self.replies = []       # what the coordinator says to the next requests; default: one line
        self.meanwhile = None   # called once while the worker waits for the event log
        self.calls, self.done, self.flows, self.received = [], {}, {}, {}
        self.assets, self.uploaded = {}, {}

    def id(self, prefix):
        return f"{prefix}_{uuid4().hex}"  # as the platform makes them: never the same twice

    def posts(self, part):
        return [body for method, path, body in self.calls if method == "POST" and part in path]

    # -- what the engine does -----------------------------------------------------------------------------------------
    def emit(self, flow, kind, payload):
        flow["events"].append({"schema_version": "1", "event_id": self.id("evt"), "sequence": len(flow["events"]) + 1,
                               "event_type": kind, "occurred_at": NOW, "recorded_at": NOW, "conversation_id": flow["conversation_id"],
                               "external_ticket_id": flow["ticket"], "external_conversation_id": flow["conversation"],
                               "external_user_id": flow["user"], "workflow_id": flow["workflow_id"], "ticket_id": None,
                               "payload": payload})

    def move(self, flow, state, reason=None):
        flow["state"], flow["revision"] = state, flow["revision"] + 1
        self.emit(flow, STATE_EVENT.get(state, "workflow.status_changed"), {"state": state, "revision": flow["revision"], "reason": reason})

    def say(self, flow, text):
        message = {"message_id": self.id("msg"), "workflow_id": flow["workflow_id"], "sender": "assistant", "text": text, "created_at": NOW}
        flow["messages"].append(message)
        self.emit(flow, "assistant.message", {"message_id": message["message_id"], "text": text})
        return message

    def ask(self, flow, summary, quote_ref=None):
        """The coordinator needs the resident's agreement."""
        approval = {"approval_id": self.id("appr"), "summary": summary, "arguments_hash": "sha256:" + hashlib.sha256(
            json.dumps(summary, sort_keys=True).encode()).hexdigest(), "quote_ref": quote_ref,
            "expires_at": (datetime.now(UTC) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"), "status": "pending"}
        flow["approvals"].append(approval)
        self.move(flow, "awaiting_approval", "approval_required")
        self.emit(flow, "approval.required", {**{k: v for k, v in approval.items() if k != "status"}, "expected_revision": flow["revision"]})
        return approval

    # -- HTTP ---------------------------------------------------------------------------------------------------------
    def handle(self, request):
        if self.down:
            raise httpx.ConnectError("no route to the platform", request=request)
        path = request.url.path.removeprefix("/workforce/v1")
        body = json.loads(request.content) if request.method == "POST" and request.content else None
        self.calls.append((request.method, path, body))
        if request.method == "PUT" and path.startswith("/uploads/"):
            asset = path.rsplit("/", 1)[1]
            assert "authorization" not in request.headers and "cookie" not in request.headers
            assert request.headers["x-amz-meta-asset-id"] == asset
            assert request.headers["content-type"] == self.assets[asset]["content_type"]
            self.uploaded[asset] = request.content
            return httpx.Response(200)
        provider = path.startswith("/provider/")
        if request.headers.get("authorization") != "ApiKey " + (PROVIDER_KEY if provider else CUSTOMER_KEY):
            return refusal(401, "UNAUTHENTICATED")
        if path == "/partner/assets/upload-sessions":
            assert set(body) == {"schema_version", "external_management_ref", "external_user_id", "external_ticket_id",
                                 "external_conversation_id", "filename", "content_type", "byte_size"}
            asset = self.id("asset")
            self.assets[asset] = body
            return httpx.Response(201, json={"asset_id": asset, "upload_method": "PUT",
                "upload_url": f"https://storage.test/uploads/{asset}", "required_headers": {
                    "Content-Type": body["content_type"], "x-amz-meta-asset-id": asset},
                "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                "complete_url": f"/workforce/v1/partner/assets/{asset}/complete"})
        if path.startswith("/partner/assets/") and path.endswith("/complete"):
            asset = path.split("/")[-2]
            expected = self.assets[asset]
            assert all(request.url.params[key] == expected[key] for key in
                       ("external_user_id", "external_ticket_id", "external_conversation_id"))
            assert len(self.uploaded[asset]) == expected["byte_size"]
            return httpx.Response(200, json={"asset_id": asset, "status": "active"})
        if provider:
            if request.method == "POST":
                return self.job_event(request, body)
            receipt = next(r["receipt"] for r in self.received.values() if r["receipt"]["receipt_id"] == path.rsplit("/", 1)[1])
            return httpx.Response(200, json={
                "receipt_id": receipt["receipt_id"], "external_event_id": receipt["external_event_id"], "ingestion_status": "applied",
                "normalized_status": "x", "received_at": NOW, "applied_at": NOW, "error": None, "note": None})
        if request.method == "GET":
            if path.startswith("/partner/requests/"):
                known = next((value[2] for value in self.done.values() if value[2].get('request_id')==path.rsplit('/',1)[1]),None)
                if known is None:
                    return refusal(404,"RESOURCE_NOT_FOUND")
                flow = self.flows[known['workflow_id']]
                if request.url.params.get('external_user_id')!=flow['user']:
                    return refusal(404,"RESOURCE_NOT_FOUND")
                return httpx.Response(200,json={**known,'request_status':'completed','workflow_state':flow['state'],
                    'workflow_revision':flow['revision'],'result':{'messages':flow['messages']}})
            flow = next((f for f in self.flows.values() if f["conversation_id"] == path.split("/")[3]), None)
            if flow is None or request.url.params.get("external_user_id") != flow["user"]:
                return refusal(404, "NOT_FOUND")
            return self.history(flow, request.url.params) if path.endswith("/event-history") else self.snapshot(flow)
        if self.refuse:
            (status, code), self.refuse = self.refuse, None
            return refusal(status, code)
        known = self.done.get(body.get("external_request_id"))
        if known is not None:  # the same request again: the first answer; another request under its id: a conflict
            return httpx.Response(known[1], json=known[2]) if known[0] == body else refusal(409, "IDEMPOTENCY_CONFLICT")
        if path == "/partner/requests":
            answer = self.command(body)
        elif path.endswith("/decision"):
            answer = self.decision(path.split("/")[3], body)
        else:
            answer = self.close(path.split("/")[3], body)
        if answer.status_code < 300:
            self.done[body["external_request_id"]] = (body, answer.status_code, json.loads(answer.content))
        return answer

    def bound(self, flow, body):
        return flow is not None and (flow["user"], flow["ticket"], flow["conversation"]) == (
            body["external_user_id"], body.get("external_ticket_id"), body["external_conversation_id"])

    def command(self, body):
        if set(body) - REQUEST_FIELDS or body.get("schema_version") != "1" or not {"type", "text"} <= set(body.get("message") or {}) \
                or set(body.get("message") or {}) - {"type", "text", "attachments"} \
                or body["message"]["type"] != "text" or not body["message"]["text"].strip():
            return refusal(422, "VALIDATION_FAILED")
        attached = body["message"].get("attachments", [])
        if len(attached) > 10:
            return refusal(422, "VALIDATION_FAILED")
        for reference in attached:
            assert set(reference) == {"asset_id"}
            asset = self.assets[reference["asset_id"]]
            assert reference["asset_id"] in self.uploaded
            assert all(asset[key] == body[key] for key in
                       ("external_user_id", "external_ticket_id", "external_conversation_id", "external_management_ref"))
        if body["command_type"] == "start_workflow":
            if "workflow_id" in body:
                return refusal(400, "INVALID_REQUEST")
            flow = {"workflow_id": self.id("wf"), "conversation_id": self.id("conv"), "user": body["external_user_id"],
                    "ticket": body["external_ticket_id"], "conversation": body["external_conversation_id"],
                    "ref": body["external_management_ref"], "state": "accepted", "revision": 0, "events": [], "messages": [],
                    "approvals": [], "texts": []}
            self.flows[flow["workflow_id"]] = flow
        else:
            flow = self.flows.get(body.get("workflow_id"))
            if not self.bound(flow, body):
                return refusal(409, "WORKFLOW_BINDING_MISMATCH")
            if flow["state"] == "closed":
                return refusal(409, "WORKFLOW_CLOSED")
            waiting = [a for a in flow["approvals"] if a["status"] == "pending"]
            if waiting:
                return refusal(409, "APPROVAL_PENDING", approval_id=waiting[0]["approval_id"])
        flow["texts"].append(body["message"]["text"])
        request_id = self.id("req")
        self.emit(flow, "request.accepted", {"request_id": request_id})
        self.move(flow, "active", "resident_reply")
        seen = {"workflow_state": flow["state"], "workflow_revision": flow["revision"]}  # what a 202 can know
        said = [self.say(flow, line) for line in (self.replies.pop(0) if self.replies else ["Tôi đã nhận được tin của bạn."])]
        self.move(flow, "awaiting_user", "reply_expected")
        if self.wait:
            seen = {"workflow_state": flow["state"], "workflow_revision": flow["revision"]}
        return httpx.Response(200 if self.wait else 202, json={
            "request_id": request_id, "request_status": "completed" if self.wait else "running",
            "external_ticket_id": flow["ticket"], "conversation_id": flow["conversation_id"], "workflow_id": flow["workflow_id"],
            **seen, "next_action": "submit_reply" if self.wait else "watch_request", "ticket_id": None,
            "result": {"messages": said} if self.wait else None, "error": None, "accepted_at": NOW,
            "completed_at": NOW if self.wait else None, "status_url": f"/workforce/v1/partner/requests/{request_id}",
            "conversation_url": f"/workforce/v1/partner/conversations/{flow['conversation_id']}",
            "event_stream_url": f"/workforce/v1/partner/conversations/{flow['conversation_id']}/events"})

    def decision(self, approval_id, body):
        found = [(f, a) for f in self.flows.values() for a in f["approvals"] if a["approval_id"] == approval_id]
        if not found:
            return refusal(404, "NOT_FOUND")
        flow, approval = found[0]
        if set(body) - DECISION_FIELDS or body.get("decision") not in ("approve", "reject") or not isinstance(body.get("expected_revision"), int):
            return refusal(422, "VALIDATION_FAILED")
        if not self.bound(flow, body) or body["workflow_id"] != flow["workflow_id"]:
            return refusal(409, "WORKFLOW_BINDING_MISMATCH")
        if approval["status"] != "pending":
            return refusal(409, "APPROVAL_NOT_PENDING", status=approval["status"])
        if body["arguments_hash"] != approval["arguments_hash"]:
            return refusal(409, "ARGUMENTS_HASH_MISMATCH")
        if body.get("quote_ref") != approval["quote_ref"]:
            return refusal(409, "QUOTE_MISMATCH")
        if body["expected_revision"] != flow["revision"]:
            return refusal(409, "REVISION_CONFLICT", current_revision=flow["revision"])
        approval["status"] = "approved" if body["decision"] == "approve" else "rejected"
        self.emit(flow, "approval.resolved", {"approval_id": approval_id, "status": approval["status"]})
        self.move(flow, "active", "approval_decided")
        return httpx.Response(202, json={"approval_id": approval_id, "status": approval["status"],
                                         "external_ticket_id": flow["ticket"], "workflow_id": flow["workflow_id"], "accepted_at": NOW})

    def close(self, workflow_id, body):
        flow = self.flows.get(workflow_id)
        if flow is None:
            return refusal(404, "NOT_FOUND")
        if set(body) - CLOSE_FIELDS or not isinstance(body.get("expected_revision"), int) or not body.get("reason"):
            return refusal(422, "VALIDATION_FAILED")
        if not self.bound(flow, body):
            return refusal(409, "WORKFLOW_BINDING_MISMATCH")
        if flow["state"] == "closed":
            return refusal(409, "WORKFLOW_CLOSED")
        if body["expected_revision"] != flow["revision"]:
            return refusal(409, "REVISION_CONFLICT", current_revision=flow["revision"])
        # Work the platform still tracks (flow["tracking"]): only "stop tracking" closes.
        if flow.get("tracking") and not (body.get("stop_tracking_only") is True and body["reason"] == "resident_requested_stop_tracking"):
            return refusal(409, "WORKFLOW_NOT_READY_TO_CLOSE", open_operations=1)
        self.move(flow, "closed", body["reason"])
        return httpx.Response(200, json={
            "request_id": self.id("req"), "request_status": "completed", "external_ticket_id": flow["ticket"],
            "conversation_id": flow["conversation_id"], "workflow_id": workflow_id, "ticket_id": None, "state": "closed",
            "next_action": "none", "revision": flow["revision"], "reason": body["reason"], "closed_at": NOW})

    def history(self, flow, params):
        if self.meanwhile:
            call, self.meanwhile = self.meanwhile, None
            call()
        if self.expired:
            self.expired = False
            return refusal(410, "EVENT_CURSOR_EXPIRED", snapshot_url=f"/workforce/v1/partner/conversations/{flow['conversation_id']}")
        cursor, after = params.get("after_cursor"), 0
        if cursor:
            at = [i for i, event in enumerate(flow["events"]) if event["event_id"] == cursor]
            if not at:
                return refusal(422, "VALIDATION_FAILED")
            after = at[0] + 1
        page = flow["events"][after:after + min(int(params.get("limit", 100)), self.page)]
        return httpx.Response(200, json={"items": page, "next_cursor": page[-1]["event_id"] if page else cursor,
                                         "has_more": len(flow["events"]) > after + len(page)})

    def snapshot(self, flow):
        return httpx.Response(200, json={
            "conversation_id": flow["conversation_id"], "external_ticket_id": flow["ticket"],
            "external_conversation_id": flow["conversation"], "external_user_id": flow["user"],
            "workflows": [{"workflow_id": flow["workflow_id"], "external_ticket_id": flow["ticket"], "ticket_id": None,
                           "state": flow["state"], "next_action": "x", "revision": flow["revision"]}],
            "messages": [{"message_id": "msg_user", "workflow_id": flow["workflow_id"], "sender": "user", "text": "(cư dân)",
                          "created_at": NOW}, *flow["messages"]],
            "has_more_messages": False,
            # The contract's field: each pending approval is its approval.required payload with its workflow and status.
            "pending_approvals": [{**{k: v for k, v in a.items() if k != "status"}, "workflow_id": flow["workflow_id"], "status": "pending",
                                   "expected_revision": flow["revision"]} for a in flow["approvals"] if a["status"] == "pending"],
            "snapshot_cursor": flow["events"][-1]["event_id"] if flow["events"] else None})

    def job_event(self, request, body):
        raw, stamp = request.content, request.headers.get("x-partner-timestamp", "")
        # The signature of the contract, computed here on its own: HMAC-SHA256 over "<timestamp>.<raw body>".
        expected = "v1=" + hmac.new(SECRET.encode(), stamp.encode() + b"." + raw, hashlib.sha256).hexdigest()
        if request.headers.get("x-partner-key-id") != KEY_ID or request.headers.get("x-partner-signature") != expected \
                or not stamp.isdigit() or abs(time.time() - int(stamp)) > 300:
            return refusal(401, "UNAUTHENTICATED", reason="signature_invalid")
        if self.refuse:
            (status, code), self.refuse = self.refuse, None
            return refusal(status, code)
        if set(body) - EVENT_FIELDS or body.get("schema_version") != "1" or not isinstance(body.get("provider_version"), int) \
                or not isinstance(body.get("data"), dict):
            return refusal(422, "VALIDATION_FAILED")
        known = self.received.get(body["external_event_id"])
        if known is not None:
            if known["raw"] != raw:
                return refusal(409, "EVENT_ID_CONFLICT")
            return httpx.Response(202, json={**{k: v for k, v in known["receipt"].items() if k != "external_event_id"}, "duplicate": True})
        receipt = {"receipt_id": self.id("rcpt"), "ingestion_status": "accepted", "duplicate": False, "received_at": NOW,
                   "status_url": "/workforce/v1/provider/event-receipts/x"}
        self.received[body["external_event_id"]] = {"raw": raw, "body": body, "receipt": {**receipt, "external_event_id": body["external_event_id"]}}
        return httpx.Response(202, json=receipt)


# ---- helpers --------------------------------------------------------------------------------------------------------

def sync(database, fake):
    """One pass of the worker, as the API's restricted role."""
    async def run():
        engine, platform = create_async_engine(database["runtime"]), Platform(BRIDGE, transport=httpx.MockTransport(fake.handle))
        try:
            await run_once(engine, platform)
        finally:
            await platform.aclose()
            await engine.dispose()
    asyncio.run(run())


def retry_now(database):
    sql(database, "update platform_commands set next_attempt_at=now() where status='pending' returning id")
    sql(database, "update platform_outbox set next_attempt_at=now() where status='pending' returning event_id")


@pytest.fixture
def on(database, monkeypatch):
    """The bridge switched on, with nothing left over from another test for the worker to pick up."""
    sql(database, "update platform_commands set status='failed',last_error='another test' where status='pending' returning id")
    sql(database, "update platform_links set status='closed' where status in ('pending','open') returning ticket_id")
    sql(database, "update platform_outbox set status='rejected' where status='pending' returning event_id")
    monkeypatch.setenv("VINHOMES_API_PLATFORM_URL", BRIDGE.url)


@contextmanager
def resident(database):
    """The resident's session, with a Reception runtime configured so that a turn would be dispatched."""
    settings = V3Settings("127.0.0.1", 8000, database["runtime"], TENANT, "local-v3-resident",
                          resident_allowed_origins=("http://testserver",), reception_service_token="t" * 32,
                          reception_url="http://reception.invalid", resident_messages_per_minute=1000)
    with TestClient(create_app(settings), client=("127.0.0.1", 50000)) as c:
        yield c


@pytest.fixture(autouse=True)
def turns(monkeypatch):
    """Resident messages handed to Reception instead of the platform (no Reception runtime runs in these tests)."""
    seen = []

    async def dispatch_turn(app, actor_id, channel_id, message):
        seen.append(message["text"])

    monkeypatch.setattr("vinhomes_api.v3_reception_runtime.dispatch_turn", dispatch_turn)
    return seen


def say(c, channel, text):
    sent = c.post(f"/resident/chats/{channel}/messages", json={"text": text, "client_message_id": str(uuid4())})
    assert sent.status_code == 201, sent.text
    return sent.json()["id"]


def hand_over(c, text="Light is broken", emergency=False):
    """Reception files a request from the chat, the way its agent does (plan_required False)."""
    place = operation(c, "get_verified_resident_context")[0]["residences"][0]
    channel = c.post("/resident/chats", json={"title": "Platform bridge"}).json()["id"]
    message = say(c, channel, text)
    draft, _ = operation(c, "create_ticket_draft", {
        "channel_id": channel, "domain_id": place["domain_id"], "building_id": place["building_id"],
        "unit_id": place["unit_id"], "category_id": CATEGORY})
    target = {"channel_id": channel, "draft_id": draft["draftId"]}
    if emergency:
        operation(c, "update_ticket_incident", {**target, "fields": {"title": text, "description": text, "source_message_id": message}})
        operation(c, "submit_ticket_assessment", {**target, "assessment": {
            "priority": "critical", "severity": "critical", "is_emergency": True, "reason": "Policy xác nhận cần chuyển khẩn cấp."}})
    else:
        operation(c, "update_ticket_incident", {**target, "fields": {"source_message_id": message, "facts": [
            {"key": "symptom", "value": "is broken", "source": "customer_report", "source_message_id": message},
            {"key": "item", "value": "Light", "source": "customer_report", "source_message_id": message}]}})
        operation(c, "submit_ticket_assessment", {**target, "assessment": {
            "priority": "high", "severity": "minor", "reason": "Resident report"}})
    handoff, _ = operation(c, "handoff_ticket", {**target, "plan_required": False,
                                                 **({"handoff_reason": "emergency"} if emergency else {})})
    assert handoff["accepted"], handoff
    return channel, handoff["ticket"]["id"]


def link(database, ticket):
    return sql(database, "select * from platform_links where ticket_id=$1", UUID(ticket))[0]


def resident_reply_text(value):
    """V2 carries the original message id for authorization; keep checking the exact resident text."""
    words, separator, source = value.rpartition("\nsource_message_id: ")
    assert separator and str(UUID(source)) == source
    return words


def commands(database, ticket):
    rows = sql(database, "select * from platform_commands where ticket_id=$1 order by enqueue_seq", UUID(ticket))
    return [{**row, "body": json.loads(row["body"])} for row in rows]


def chat(database, channel):
    """What the platform's coordinator wrote into the resident's chat."""
    rows = sql(database, "select body from messages where channel_id=$1 and sender_kind='agent' and sender_client_id='platform' "
                         "and visibility='customer' order by seq", channel)
    return [json.loads(row["body"]) for row in rows]


def started(database, c, fake, **how):
    """A request handed over and accepted by the platform."""
    channel, ticket = hand_over(c, **how)
    sync(database, fake)
    assert link(database, ticket)["status"] == "open"
    return channel, ticket, fake.flows[link(database, ticket)["workflow_id"]]


# ---- 5.1 handing over -----------------------------------------------------------------------------------------------

def test_with_the_bridge_off_a_handoff_writes_nothing_for_the_platform(database, monkeypatch):
    monkeypatch.delenv("VINHOMES_API_PLATFORM_URL", raising=False)
    with resident(database) as c:
        channel, ticket = hand_over(c)
        say(c, channel, "Bao giờ có người đến?")
        assert not any(item["confirm_close"] for item in c.get("/resident/chats").json()["items"])
    assert sql(database, "select count(*) as n from platform_links where ticket_id=$1", UUID(ticket)) == [{"n": 0}]
    assert sql(database, "select count(*) as n from platform_commands where ticket_id=$1", UUID(ticket)) == [{"n": 0}]


def test_a_handoff_links_the_ticket_and_queues_the_start_in_its_own_transaction(database, on, monkeypatch):
    with resident(database) as c:
        channel, ticket = hand_over(c)
        row, [start] = link(database, ticket), commands(database, ticket)
        code = sql(database, "select t.code,mu.code as ref,u.code as unit from tickets t join management_units mu on mu.id=t.management_unit_id "
                             "join units u on u.id=t.unit_id where t.id=$1", UUID(ticket))[0]
        assert (row["status"], row["channel_id"], row["user_id"], row["management_ref"]) == ("pending", channel, "local-v3-resident", code["ref"])
        assert (start["kind"], start["status"], start["attempts"]) == ("start_workflow", "pending", 0)
        told = start["body"]["text"]
        # The agent copies the ticket id from this line into every tool call.
        assert told.splitlines()[0] == f"ticket_id: {ticket}"
        assert "Light is broken" in told and f"Căn: {code['unit']}" in told and "Mức ưu tiên: Cao" in told and "Số ảnh: 0" in told
        assert "Mức khẩn cấp do Lễ tân đánh giá: không khẩn cấp; mức độ nghiêm trọng: nhẹ" in told.splitlines()
        # Neither the internal code nor the phone number of the resident leaves the domain.
        assert code["code"] not in told and "VH-" not in told and "+84901234567" not in told and "0901234567" not in told

        # An emergency is handed over too, with the level Reception assessed; what happens to it here is unchanged.
        _, urgent = hand_over(c, "Bếp nhà tôi đang cháy", emergency=True)
        [alarm] = commands(database, urgent)
        assert link(database, urgent)["status"] == "pending" and alarm["kind"] == "start_workflow"
        assert "Mức khẩn cấp do Lễ tân đánh giá: KHẨN CẤP (cháy hoặc khói); mức độ nghiêm trọng: nghiêm trọng" in alarm["body"]["text"].splitlines()
        assert "Mức ưu tiên: Khẩn cấp" in alarm["body"]["text"] and "VH-" not in alarm["body"]["text"]
        assert sql(database, "select is_emergency,priority from tickets where id=$1", UUID(urgent)) == [{"is_emergency": True, "priority": "critical"}]

        # The link, the command and the ticket are one transaction: a start that cannot be queued leaves no ticket.
        async def broken(*_):
            raise RuntimeError("the command could not be written")

        before = sql(database, "select (select count(*) from tickets) as tickets,(select count(*) from platform_links) as links")[0]
        monkeypatch.setattr(bridge, "command", broken)
        with pytest.raises(RuntimeError):
            hand_over(c)
        assert sql(database, "select (select count(*) from tickets) as tickets,(select count(*) from platform_links) as links")[0] == before


# ---- 5.2 commands and events ----------------------------------------------------------------------------------------

def test_messages_of_an_answer_reach_the_chat_once_also_after_they_come_again_as_events(database, on):
    fake = FakePlatform()
    fake.replies = [["Chào bạn, tôi là trợ lý của Ban quản lý.", "Tôi đang tìm kỹ thuật viên cho bạn."]]
    with resident(database) as c:
        channel, ticket = hand_over(c)
        sync(database, fake)
        row, [start] = link(database, ticket), commands(database, ticket)
        [sent] = fake.posts("/partner/requests")
        flow = fake.flows[row["workflow_id"]]
        # The identifiers of spec section 3.
        assert sent["external_request_id"] == str(start["id"]) and sent["external_ticket_id"] == ticket
        assert sent["external_conversation_id"] == f"{channel}:{ticket}" and sent["external_user_id"] == "local-v3-resident"
        assert sent["external_management_ref"] == row["management_ref"] and sent["timezone"] == "Asia/Ho_Chi_Minh"
        assert (start["status"], start["attempts"], start["last_error"]) == ("done", 1, None)
        assert (row["status"], row["conversation_id"], row["state"], row["next_action"], row["revision"]) == (
            "open", flow["conversation_id"], "awaiting_user", "submit_reply", flow["revision"])
        # The pass that sent the command also read the events that carry the same two messages.
        assert row["cursor"] == flow["events"][-1]["event_id"]
        said = ["Chào bạn, tôi là trợ lý của Ban quản lý.", "Tôi đang tìm kỹ thuật viên cho bạn."]
        assert [m["text"] for m in chat(database, channel)] == said
        sync(database, fake)
        sql(database, "update platform_links set cursor=null where ticket_id=$1 returning ticket_id", UUID(ticket))
        sync(database, fake)  # the whole log again
        assert [m["text"] for m in chat(database, channel)] == said
        inbox = sql(database, "select platform_id,chat_message_id from platform_inbox where ticket_id=$1", UUID(ticket))
        assert {r["platform_id"] for r in inbox} == {m["message_id"] for m in flow["messages"]} and all(r["chat_message_id"] for r in inbox)
        # The resident's app reads them as ordinary messages with text.
        shown = c.get(f"/resident/chats/{channel}/messages").json()["items"]
        assert [m["body"]["text"] for m in shown if m["sender_client_id"] == "platform"] == said


@pytest.mark.parametrize('synchronous',[True,False])
def test_platform_reply_ends_the_resident_turn_indicator(database, on, synchronous):
    fake = FakePlatform(wait=synchronous)
    with resident(database) as c:
        channel, ticket, flow = started(database, c, fake)
        say(c, channel, "Công việc đang tới đâu rồi?")
        assert c.get(f"/resident/chats/{channel}/turn-state").json()["status"] == "waiting_platform"
        sync(database, fake)
        assert c.get(f"/resident/chats/{channel}/turn-state").json()["status"] == "completed"


def test_the_ticket_draft_card_is_not_the_residents_turn(database, on):
    # Reception writes the draft card under the resident's name; the turn the indicator follows is what they typed.
    with resident(database) as c:
        channel, _ = hand_over(c)
        [typed] = sql(database, "select id from messages where channel_id=$1 and sender_kind='user' and body->>'text'=$2",
                      channel, "Light is broken")
        assert c.get(f"/resident/chats/{channel}/turn-state").json()["messageId"] == str(typed["id"])


def test_a_202_is_followed_through_the_event_log_page_by_page(database, on):
    fake = FakePlatform(wait=False, page=2)
    fake.replies = [["Tôi đã nhận yêu cầu.", "Kỹ thuật viên sẽ liên hệ trong ít phút."]]
    with resident(database) as c:
        channel, ticket = hand_over(c)
        sync(database, fake)
        row = link(database, ticket)
        flow = fake.flows[row["workflow_id"]]
        final = json.loads(commands(database, ticket)[0]["result"])
        assert final["request_status"] == "completed" and final["result"]["messages"]
        assert len(flow["events"]) > 4 and len([call for call in fake.calls if call[1].endswith("/event-history")]) >= 3
        # The answer knew the workflow as "active"; the events moved it on and the older picture did not win.
        assert (row["status"], row["state"], row["next_action"], row["revision"]) == ("open", "awaiting_user", "submit_reply", flow["revision"])
        assert [m["text"] for m in chat(database, channel)] == ["Tôi đã nhận yêu cầu.", "Kỹ thuật viên sẽ liên hệ trong ít phút."]
        assert row["cursor"] == flow["events"][-1]["event_id"]


def test_a_purged_cursor_falls_back_to_the_snapshot(database, on):
    fake = FakePlatform()
    with resident(database) as c:
        channel, ticket, flow = started(database, c, fake)
        fake.say(flow, "Kỹ thuật viên đã nhận việc.")
        approval = fake.ask(flow, {"text": "Đồng ý thay vòi mới, 350000 đồng"})
        fake.expired = True
        sync(database, fake)
        row = link(database, ticket)
        assert (row["cursor"], row["state"], row["revision"]) == (flow["events"][-1]["event_id"], "awaiting_approval", flow["revision"])
        texts = [m["text"] for m in chat(database, channel)]
        # The resident's own words in the snapshot are not posted back at them.
        assert texts == ["Tôi đã nhận được tin của bạn.", "Kỹ thuật viên đã nhận việc.", "Đồng ý thay vòi mới, 350000 đồng"]
        assert sql(database, "select status from platform_approvals where approval_id=$1", approval["approval_id"]) == [{"status": "pending"}]


# ---- 5.3 the resident goes on talking -------------------------------------------------------------------------------

def test_a_later_message_goes_to_the_platform_and_an_emergency_goes_to_reception_and_is_told_to_it(database, on, turns):
    fake = FakePlatform()
    with resident(database) as c:
        channel, ticket, flow = started(database, c, fake)
        assert turns == ["Light is broken"]  # before the handoff the chat was Reception's
        fake.replies = [["Khoảng 15 giờ hôm nay bạn nhé."]]
        say(c, channel, "Khi nào thợ đến?")
        assert turns == ["Light is broken"]
        reply = commands(database, ticket)[-1]
        assert (reply["kind"], reply["status"], resident_reply_text(reply["body"]["text"])) == ("workflow_reply", "pending", "Khi nào thợ đến?")
        sync(database, fake)
        sent = fake.posts("/partner/requests")[-1]
        assert (sent["command_type"], sent["workflow_id"], resident_reply_text(sent["message"]["text"])) == ("workflow_reply", flow["workflow_id"], "Khi nào thợ đến?")
        assert chat(database, channel)[-1]["text"] == "Khoảng 15 giờ hôm nay bạn nhé."

        # Danger is handled here, at once, as before; the coordinator is told of it in one fixed sentence that claims
        # nothing about what Reception's turn (not run yet) will reach.
        say(c, channel, "Bếp nhà tôi đang cháy")
        assert turns == ["Light is broken", "Bếp nhà tôi đang cháy"]
        told = commands(database, ticket)[-1]
        assert (told["kind"], told["status"], len(commands(database, ticket))) == ("workflow_reply", "pending", 3)
        assert told["body"]["own"] is True and resident_reply_text(told["body"]["text"]) == "Cư dân vừa báo tình huống khẩn cấp (cháy hoặc khói). Lời cư dân:\nBếp nhà tôi đang cháy"
        # A burnt-out bulb is no emergency: it is the coordinator's alone.
        say(c, channel, "Bóng đèn phòng khách bị cháy rồi")
        assert len(turns) == 2 and resident_reply_text(commands(database, ticket)[-1]["body"]["text"]) == "Bóng đèn phòng khách bị cháy rồi"
        fake.replies = [[], ["Tôi sẽ báo nhân viên mang bóng mới."]]
        sync(database, fake)
        sync(database, fake)
        assert flow["texts"][-2].startswith("Cư dân vừa báo tình huống khẩn cấp") and resident_reply_text(flow["texts"][-1]) == "Bóng đèn phòng khách bị cháy rồi"
        # Reception answered the emergency in the chat: a coordinator that says nothing leaves no "no answer" line.
        assert SILENT_TEXT not in [m["text"] for m in chat(database, channel)]

        # Another chat of the same resident has no workflow.
        other = c.post("/resident/chats", json={"title": "Khác"}).json()["id"]
        say(c, other, "Cho tôi hỏi giờ mở cửa hồ bơi")
        assert turns[-1] == "Cho tôi hỏi giờ mở cửa hồ bơi"

        # The workflow ends: the chat is Reception's again.
        fake.move(flow, "closed", "operator_closed")
        sync(database, fake)
        assert (link(database, ticket)["status"], link(database, ticket)["next_action"]) == ("closed", "none")
        say(c, channel, "Cảm ơn nhé")
        assert turns[-1] == "Cảm ơn nhé" and len(commands(database, ticket)) == 4


def test_a_message_the_coordinator_leaves_unanswered_gets_one_honest_line(database, on):
    fake = FakePlatform()
    with resident(database) as c:
        channel, ticket, flow = started(database, c, fake)
        fake.replies = [[], ["Thợ đến lúc 15 giờ."]]
        say(c, channel, "Khi nào thợ đến?")
        sync(database, fake)
        sync(database, fake)
        assert [m["text"] for m in chat(database, channel)].count(SILENT_TEXT) == 1
        say(c, channel, "Khi nào thợ đến vậy?")
        sync(database, fake)
        assert [m["text"] for m in chat(database, channel)][-2:] == [SILENT_TEXT, "Thợ đến lúc 15 giờ."]


def test_photos_in_a_handed_over_chat_join_the_request_and_are_told_to_the_coordinator_as_a_count(database, on, turns):
    fake = FakePlatform()
    with resident(database) as c:
        channel, ticket, flow = started(database, c, fake)
        photo = c.post(f"/resident/chats/{channel}/photos?filename=a.png&mimeType=image/png", content=image(), headers=key())
        assert photo.status_code == 201, photo.text

        def send(text):
            sent = c.post(f"/resident/chats/{channel}/messages", json={
                "text": text, "client_message_id": str(uuid4()), "file_ids": [photo.json()["id"]]})
            assert sent.status_code == 201, sent.text
            return commands(database, ticket)[-1]

        # Photos without a word: still the coordinator's chat, and Reception is not asked.
        alone = send("")
        assert (alone["kind"], resident_reply_text(alone["body"]["text"])) == ("workflow_reply", "Cư dân gửi thêm 1 ảnh.")
        # The same photo again adds nothing: the coordinator is told only of photos the request did not hold yet.
        assert resident_reply_text(send("Vết nứt ở đây ạ")["body"]["text"]) == "Vết nứt ở đây ạ"
        assert send("") == commands(database, ticket)[-1] and len(commands(database, ticket)) == 3
        assert turns == ["Light is broken"]
        sync(database, fake)
        sync(database, fake)
        assert [resident_reply_text(v) for v in flow["texts"][-2:]] == ["Cư dân gửi thêm 1 ảnh.", "Vết nứt ở đây ạ"]
        # The photo is the request's own, once, with the ticket event staff read in the request.
        held = sql(database, "select file_id,purpose,uploaded_by from ticket_files where ticket_id=$1", UUID(ticket))
        assert held == [{"file_id": UUID(photo.json()["id"]), "purpose": "issue", "uploaded_by": "local-v3-resident"}]
        attached = sql(database, "select payload from ticket_events where ticket_id=$1 and event_type='ticket.conversation_images_attached'", UUID(ticket))
        assert [json.loads(row["payload"]) for row in attached] == [{"fileIds": [photo.json()["id"]]}]
        with client(database, "management") as manager:
            assert [f["id"] for f in manager.get(f"/tickets/{ticket}/files").json()["items"]] == [photo.json()["id"]]

        # Also while the result waits for the resident's answer: a photo of what is still wrong is the request's.
        sql(database, "update tickets set status='resolved',resolved_at=now() where id=$1 returning id", UUID(ticket))
        late = c.post(f"/resident/chats/{channel}/photos?filename=b.png&mimeType=image/png", content=image(), headers=key())
        sent = c.post(f"/resident/chats/{channel}/messages", json={"text": "", "client_message_id": str(uuid4()), "file_ids": [late.json()["id"]]})
        assert sent.status_code == 201 and resident_reply_text(commands(database, ticket)[-1]["body"]["text"]) == "Cư dân gửi thêm 1 ảnh."
        assert {row["file_id"] for row in sql(database, "select file_id from ticket_files where ticket_id=$1", UUID(ticket))} == {
            UUID(photo.json()["id"]), UUID(late.json()["id"])}
        assert len(sql(database, "select 1 as x from ticket_events where ticket_id=$1 and event_type='ticket.conversation_images_attached'", UUID(ticket))) == 2


def test_the_resident_can_write_while_the_worker_waits_for_the_platform(database, on):
    fake = FakePlatform()
    with resident(database) as c:
        channel, ticket, flow = started(database, c, fake)
        sent, pool = [], ThreadPoolExecutor(1)

        def meanwhile():  # the worker holds the link here; a message that waited for it would never come back
            sent.append(pool.submit(say, c, channel, "Còn ai ở đó không?").result(timeout=15))

        fake.meanwhile = meanwhile
        try:
            sync(database, fake)
        finally:
            pool.shutdown(wait=False)
        assert sent and resident_reply_text(commands(database, ticket)[-1]["body"]["text"]) == "Còn ai ở đó không?"


def test_the_loop_serves_other_chats_while_one_command_waits_for_the_coordinator(database, on):
    fake = FakePlatform()
    with resident(database) as c:
        channel, ticket, flow = started(database, c, fake)
        _, waiting = hand_over(c)  # the platform will take its time over this one
    fake.say(flow, "Kỹ thuật viên đang trên đường đến.")

    async def until(check, what):
        for _ in range(150):
            if await asyncio.to_thread(check):
                return
            await asyncio.sleep(0.1)
        raise AssertionError(what)

    async def scenario():
        held, release = asyncio.Event(), asyncio.Event()

        async def handle(request):
            if request.method == "POST" and request.url.path.endswith("/partner/requests"):
                held.set()
                await release.wait()  # a turn that has not ended yet
            return fake.handle(request)

        engine, platform = create_async_engine(database["runtime"]), Platform(BRIDGE, transport=httpx.MockTransport(handle))
        loop = asyncio.create_task(platform_sync.run(engine, platform))
        try:
            await asyncio.wait_for(held.wait(), 15)
            await until(lambda: chat(database, channel)[-1]["text"] == "Kỹ thuật viên đang trên đường đến.",
                        "events were not read while a command was waiting")
            assert (await asyncio.to_thread(link, database, waiting))["status"] == "pending"
            release.set()
            await until(lambda: link(database, waiting)["status"] == "open", "the held command was never finished")
        finally:
            release.set()
            loop.cancel()
            await asyncio.gather(loop, *platform_sync._sending.values(), return_exceptions=True)
            await platform.aclose()
            await engine.dispose()

    asyncio.run(scenario())


def test_a_reply_waits_while_an_approval_is_pending_and_the_decision_goes_first(database, on, turns):
    fake = FakePlatform()
    with resident(database) as c:
        channel, ticket, flow = started(database, c, fake)
        approval = fake.ask(flow, {"text": "Đồng ý chi phí 550000 đồng", "items": [{"label": "Vòi", "amount": "550000"}], "total": "550000",
                                   "tool": "vh_some_action", "arguments": {"ticket_id": ticket}}, quote_ref="Q-1")
        sync(database, fake)
        stored = sql(database, "select * from platform_approvals where approval_id=$1", approval["approval_id"])[0]
        assert (stored["status"], stored["arguments_hash"], stored["quote_ref"], stored["expected_revision"]) == (
            "pending", approval["arguments_hash"], "Q-1", flow["revision"])
        card = chat(database, channel)[-1]
        # A card with words and amounts; the tool and its arguments are not the resident's business.
        assert card["text"] == "Đồng ý chi phí 550000 đồng" and card["platform"] == {
            "kind": "approval", "approval_id": approval["approval_id"], "status": "pending", "expires_at": approval["expires_at"],
            "summary": {"text": "Đồng ý chi phí 550000 đồng", "arguments": {"items": [{"label": "Vòi", "amount": 550000}], "total": 550000}}}
        assert link(database, ticket)["next_action"] == "submit_approval"

        # Words instead of the button: the platform holds the reply back, and it is tried again later.
        say(c, channel, "Giá đó có gồm công không?")
        sync(database, fake)
        reply = commands(database, ticket)[-1]
        assert (reply["status"], reply["attempts"]) == ("pending", 1) and reply["last_error"].startswith("APPROVAL_PENDING")
        assert reply["next_attempt_at"] > datetime.now(UTC) and link(database, ticket)["status"] == "open"
        assert FAILED_TEXT not in [m["text"] for m in chat(database, channel)]

        decide = f"/resident/platform/approvals/{approval['approval_id']}/decision"
        assert c.post("/resident/platform/approvals/appr_unknown/decision", json={"approve": True}).status_code == 404
        with client(database, "management") as someone_else:
            assert someone_else.post(decide, json={"approve": True}).status_code == 404
        assert c.post(decide, json={"approve": "yes", "note": "x"}).status_code == 422
        # Meanwhile the workflow moved on (staff progress does that) without telling the bridge.
        flow["revision"] += 1
        agreed = c.post(decide, json={"approve": True})
        assert agreed.status_code == 200 and agreed.json() == {"approval_id": approval["approval_id"], "status": "approved"}
        assert c.post(decide, json={"approve": True}).json()["status"] == "approved"
        assert c.post(decide, json={"approve": False}).status_code == 409
        decision = commands(database, ticket)[-1]
        assert decision["kind"] == "approval_decision" and decision["body"] == {
            "approval_id": approval["approval_id"], "decision": "approve", "arguments_hash": approval["arguments_hash"],
            "expected_revision": stored["expected_revision"], "quote_ref": "Q-1"}
        assert len([x for x in commands(database, ticket) if x["kind"] == "approval_decision"]) == 1

        retry_now(database)
        sync(database, fake)  # the decision before the older reply; its revision was stale
        first = fake.posts("/decision")[-1]
        assert (first["arguments_hash"], first["quote_ref"], first["expected_revision"]) == (approval["arguments_hash"], "Q-1", stored["expected_revision"])
        assert commands(database, ticket)[-1]["last_error"].startswith("REVISION_CONFLICT")
        retry_now(database)
        sync(database, fake)
        again = fake.posts("/decision")[-1]
        assert again["external_request_id"] == first["external_request_id"] == str(decision["id"])
        assert again["expected_revision"] == stored["expected_revision"] + 1 and approval["status"] == "approved"
        retry_now(database)
        sync(database, fake)
        assert [x["status"] for x in commands(database, ticket)] == ["done", "done", "done"]
        assert resident_reply_text(flow["texts"][-1]) == "Giá đó có gồm công không?"
        resolved = [m for m in chat(database, channel) if m.get("platform", {}).get("status") == "approved"]
        # The outcome is the same card again, so the app can show the question with its answer.
        assert len(resolved) == 1 and resolved[0]["text"]
        assert resolved[0]["platform"] == {"kind": "approval", "approval_id": approval["approval_id"], "status": "approved",
                                           "summary": card["platform"]["summary"]}
        assert sql(database, "select status from platform_approvals where approval_id=$1", approval["approval_id"]) == [{"status": "approved"}]


# ---- 5.5 the resident confirms ---------------------------------------------------------------------------------------

def resolved_with_a_completion_request(database, ticket):
    """The state the onsite acceptance leaves (v3_completion.publish_completion): work done and checked, the ticket
    resolved, the resident asked to confirm. Written directly: how staff get there is not the bridge's."""
    work = sql(database, """insert into work_orders(tenant_id,ticket_id,category_id,required_specialty_id,description,status,completed_at)
        values($1,$2,$3,$3,'Thay bóng đèn','completed',now()) returning id""", TENANT, UUID(ticket), UUID(CATEGORY))[0]["id"]
    sql(database, """insert into vh_qc_results(tenant_id,work_order_id,outcome,criteria,checked_by)
        values($1,$2,'pass','{}','local-v3-management') returning id""", TENANT, work)
    approval = sql(database, """insert into work_approvals(tenant_id,work_order_id,kind,requested_to_user_id,request_detail,status,request_hash)
        values($1,$2,'customer_completion','local-v3-resident','{"note":"Vui lòng xác nhận"}','pending',$3) returning id""",
                   TENANT, work, f"completion:{ticket}")[0]["id"]
    return str(approval), sql(database, "update tickets set status='resolved',resolved_at=now() where id=$1 returning version", UUID(ticket))[0]["version"]


def test_confirming_completion_closes_the_ticket_and_the_workflow_at_its_current_revision(database, on, turns):
    fake = FakePlatform()
    with resident(database) as c:
        channel, ticket, flow = started(database, c, fake)
        # The app shows the completion card once the result waits for the resident (spec 5.5 step 4), whether or
        # not the coordinator has said anything yet.
        asked = lambda: next(x for x in c.get("/resident/chats").json()["items"] if x["id"] == channel)["confirm_close"]  # noqa: E731
        assert asked() is False
        approval, version = resolved_with_a_completion_request(database, ticket)
        assert asked() is False
        assert not any(str(a['id']) == approval for a in c.get('/resident/approvals').json()['items'])
        premature = c.post(f'/resident/approvals/{approval}/decision', headers=key(), json={
            'version': version, 'approved': True, 'note': 'Premature confirmation'})
        assert premature.status_code == 409
        fake.move(flow, "awaiting_confirmation", "operation_completed")
        fake.say(flow, "Việc đã xong, bạn xác nhận giúp nhé.")
        sync(database, fake)
        assert link(database, ticket)["next_action"] == "confirm_close" and asked() is True
        flow["revision"] += 1  # moved again since the bridge last read
        headers = key()
        body = {"version": version, "approved": True, "note": "Đã sửa xong, cảm ơn"}
        confirmed = c.post(f"/resident/approvals/{approval}/decision", headers=headers, json=body)
        assert confirmed.status_code == 200, confirmed.text
        assert sql(database, "select status from tickets where id=$1", UUID(ticket)) == [{"status": "closed"}]
        # The same answer sent again is the stored receipt: one close, not two.
        assert c.post(f"/resident/approvals/{approval}/decision", headers=headers, json=body).json() == confirmed.json()
        close = commands(database, ticket)[-1]
        assert (close["kind"], close["status"], close["body"]) == ("close", "pending", {"reason": "resident_confirmed"})
        assert len(commands(database, ticket)) == 2
        # The request is over, its workflow is still being told: what the resident writes now is Reception's.
        said = len(turns)
        say(c, channel, "Cảm ơn bạn nhiều nhé")
        assert turns[said:] == ["Cảm ơn bạn nhiều nhé"] and len(commands(database, ticket)) == 2
        # A reply that was already waiting when the workflow ends is dropped; that is not a failure to report.
        sql(database, """insert into platform_commands(tenant_id,ticket_id,kind,body) values($1,$2,'workflow_reply','{"text":"Còn gì nữa không?"}')
            returning id""", TENANT, UUID(ticket))
        sync(database, fake)
        retry_now(database)
        sync(database, fake)
        first, sent = fake.posts("/close")[-2:]
        assert first["external_request_id"] == sent["external_request_id"] == str(close["id"])
        assert sent["expected_revision"] == flow["revision"] - 1 and sent["reason"] == "resident_confirmed"
        row = link(database, ticket)
        assert (flow["state"], row["status"], row["state"], row["next_action"]) == ("closed", "closed", "closed", "none")
        sync(database, fake)
        assert [(x["kind"], x["status"], x["last_error"]) for x in commands(database, ticket)][1:] == [
            ("close", "done", None), ("workflow_reply", "failed", "the link is closed")]
        assert FAILED_TEXT not in [m["text"] for m in chat(database, channel)] and asked() is False


class LastWords(FakePlatform):
    """The coordinator says one more thing after the bridge last read the log, then the workflow is closed; the first
    read after that fails."""
    cut = True

    def close(self, workflow_id, body):
        flow = self.flows[workflow_id]
        if flow["state"] != "closed" and body.get("expected_revision") == flow["revision"]:
            self.say(flow, "Cảm ơn anh/chị đã xác nhận. Chúc anh/chị một ngày tốt lành.")
        return super().close(workflow_id, body)

    def history(self, flow, params):
        if flow["state"] == "closed" and self.cut:
            self.cut = False
            raise httpx.ReadTimeout("the log could not be read", request=None)
        return super().history(flow, params)


def test_what_the_platform_logged_up_to_the_close_reaches_the_chat_before_the_link_is_finished(database, on, turns):
    fake = LastWords()
    with resident(database) as c:
        channel, ticket, flow = started(database, c, fake)
        approval, version = resolved_with_a_completion_request(database, ticket)
        fake.move(flow, "awaiting_confirmation", "operation_completed")
        sync(database, fake)
        confirmed = c.post(f"/resident/approvals/{approval}/decision", headers=key(), json={"version": version, "approved": True, "note": "Đã xong, cảm ơn"})
        assert confirmed.status_code == 200, confirmed.text
        # The close is answered (the workflow is closed) before the last line was read, and the read fails.
        sync(database, fake)
        row = link(database, ticket)
        assert (flow["state"], commands(database, ticket)[-1]["status"], row["state"], row["next_action"]) == ("closed", "done", "closed", "none")
        assert row["status"] == "open" and row["cursor"] != flow["events"][-1]["event_id"]
        assert "Chúc anh/chị một ngày tốt lành." not in " ".join(m["text"] for m in chat(database, channel))
        # Not finished, but no longer the coordinator's chat: the next message is Reception's.
        said = len(turns)
        say(c, channel, "Cảm ơn nhé")
        assert turns[said:] == ["Cảm ơn nhé"] and commands(database, ticket)[-1]["kind"] == "close"
        # The next pass reads the log to its end: the last line is in the chat, once, and only then is the link closed.
        sync(database, fake)
        row = link(database, ticket)
        assert (row["status"], row["cursor"]) == ("closed", flow["events"][-1]["event_id"])
        assert [m["text"] for m in chat(database, channel)][-1] == "Cảm ơn anh/chị đã xác nhận. Chúc anh/chị một ngày tốt lành."
        calls = len(fake.calls)
        sync(database, fake)
        assert len(fake.calls) == calls and len(chat(database, channel)) == 2   # a closed link is not read again


def test_refusing_completion_reopens_the_ticket_and_tells_the_coordinator_why(database, on):
    fake = FakePlatform()
    with resident(database) as c:
        channel, ticket, flow = started(database, c, fake)
        approval, version = resolved_with_a_completion_request(database, ticket)
        fake.move(flow, "awaiting_confirmation", "operation_completed")
        sync(database, fake)
        refused = c.post(f"/resident/approvals/{approval}/decision", headers=key(), json={
            "version": version, "approved": False, "note": "Đèn vẫn nhấp nháy sau khi thay"})
        assert refused.status_code == 200, refused.text
        assert sql(database, "select status,reopen_count from tickets where id=$1", UUID(ticket)) == [{"status": "triaging", "reopen_count": 1}]
        reply = commands(database, ticket)[-1]
        assert (reply["kind"], reply["status"]) == ("workflow_reply", "pending") and "Đèn vẫn nhấp nháy sau khi thay" in reply["body"]["text"]
        fake.replies = [[]]  # the coordinator sends someone back and says nothing
        sync(database, fake)
        # The resident tapped a button and wrote no chat message: no line about an unanswered message.
        assert SILENT_TEXT not in [m["text"] for m in chat(database, channel)]
        assert "Đèn vẫn nhấp nháy sau khi thay" in flow["texts"][-1] and flow["state"] != "closed"
        assert link(database, ticket)["status"] == "open"


# ---- failures -------------------------------------------------------------------------------------------------------

def test_a_platform_that_is_away_is_asked_again_with_the_same_request_id(database, on):
    fake = FakePlatform()
    fake.down = True
    with resident(database) as c:
        channel, ticket = hand_over(c)  # the handoff itself is untouched: the ticket exists, Reception can answer
        sync(database, fake)
        [start] = commands(database, ticket)
        assert (start["status"], start["attempts"], start["last_error"]) == ("pending", 1, "ConnectError")
        assert start["next_attempt_at"] > datetime.now(UTC) and link(database, ticket)["status"] == "pending" and chat(database, channel) == []
        sync(database, fake)  # not due yet: not tried
        assert commands(database, ticket)[0]["attempts"] == 1
        fake.down, fake.refuse = False, (503, "INTERNAL_ERROR")
        retry_now(database)
        sync(database, fake)
        assert commands(database, ticket)[0]["attempts"] == 2 and commands(database, ticket)[0]["last_error"].startswith("INTERNAL_ERROR")
        fake.refuse = (429, "RATE_LIMITED")
        retry_now(database)
        sync(database, fake)
        retry_now(database)
        sync(database, fake)
        tries = fake.posts("/partner/requests")
        assert len(tries) == 3 and tries[0] == tries[1] == tries[2] and tries[0]["external_request_id"] == str(start["id"])
        [start] = commands(database, ticket)
        assert (start["status"], start["attempts"], start["last_error"]) == ("done", 4, None)
        assert link(database, ticket)["status"] == "open" and len(chat(database, channel)) == 1


def test_a_request_the_platform_refuses_for_good_fails_the_link_and_tells_the_resident_once(database, on, turns):
    fake = FakePlatform()
    fake.refuse = (403, "ROUTE_NOT_AUTHORIZED")
    with resident(database) as c:
        channel, ticket = hand_over(c)
        say(c, channel, "Có ai xem giúp chưa?")  # queued behind the start
        sync(database, fake)
        start, reply = commands(database, ticket)
        assert (start["status"], start["attempts"]) == ("failed", 1) and start["last_error"].startswith("ROUTE_NOT_AUTHORIZED")
        assert reply["status"] == "failed" and link(database, ticket)["status"] == "failed"
        # One line, in plain words: no code, no error text.
        assert chat(database, channel) == [{"text": FAILED_TEXT}]
        retry_now(database)
        sync(database, fake)
        sync(database, fake)
        assert chat(database, channel) == [{"text": FAILED_TEXT}] and len(fake.posts("/partner/requests")) == 1
        # The chat is Reception's again.
        said = len(turns)
        say(c, channel, "Vậy tôi phải làm gì?")
        assert len(turns) == said + 1 and len(commands(database, ticket)) == 2


class FailingTurn(FakePlatform):
    """The coordinator's turn fails for good: the request settles as failed, the workflow needs an operator."""

    def command(self, body):
        answer = super().command(body)
        if body["command_type"] == "start_workflow" or answer.status_code != 200:
            return answer
        data = json.loads(answer.content)
        flow = self.flows[data["workflow_id"]]
        self.move(flow, "needs_attention", "engine_error")
        return httpx.Response(200, json={
            **data, "request_status": "failed", "workflow_state": "needs_attention", "workflow_revision": flow["revision"],
            "next_action": "resolve_attention", "result": {"messages": []},
            "error": {"code": "engine_error", "message": "The assistant could not process this message. A person will follow up."}})


def test_a_turn_that_failed_for_good_gives_the_request_back_to_people_and_says_so_once(database, on, turns):
    fake = FailingTurn()
    fake.replies = [["Tôi đã nhận yêu cầu."], []]
    with resident(database) as c:
        channel, ticket, flow = started(database, c, fake)
        say(c, channel, "Khi nào thợ đến vậy?")
        sync(database, fake)
        sync(database, fake)
        reply, row = commands(database, ticket)[-1], link(database, ticket)
        assert (reply["status"], reply["last_error"], row["status"], row["state"]) == ("failed", "engine_error", "failed", "needs_attention")
        assert [m["text"] for m in chat(database, channel)] == ["Tôi đã nhận yêu cầu.", FAILED_TEXT]
        said = len(turns)
        say(c, channel, "Vậy tôi phải làm gì?")
        assert len(turns) == said + 1

        # The same failure seen only in the event log (the answer was a 202), and a route that was taken away.
        for state, reason in (("needs_attention", "engine_error"), ("blocked_authorization", "route_suspended")):
            other, later, running = started(database, c, fake)
            fake.move(running, state, reason)
            sync(database, fake)
            assert link(database, later)["status"] == "failed" and chat(database, other)[-1] == {"text": FAILED_TEXT}
        # A workflow that waits for a person on the platform's side but can still be written to stays linked.
        other, later, running = started(database, c, fake)
        fake.move(running, "needs_attention", "needs_human")
        sync(database, fake)
        row = link(database, later)
        assert (row["status"], row["next_action"]) == ("open", "resolve_attention") and FAILED_TEXT not in [m["text"] for m in chat(database, other)]


class LostAnswer(FakePlatform):
    """The platform takes the decision; its answer never arrives (a cut connection)."""
    lose = True

    def handle(self, request):
        answer = super().handle(request)
        if self.lose and request.method == "POST" and request.url.path.endswith("/decision") and answer.status_code < 300:
            self.lose = False
            raise httpx.ReadTimeout("the answer was lost", request=request)
        return answer


def test_a_decision_whose_answer_was_lost_is_sent_again_as_the_very_same_request(database, on):
    fake = LostAnswer()
    with resident(database) as c:
        channel, ticket, flow = started(database, c, fake)
        approval = fake.ask(flow, {"text": "Đồng ý chi phí 550000 đồng"}, quote_ref="Q-1")
        sync(database, fake)
        assert c.post(f"/resident/platform/approvals/{approval['approval_id']}/decision", json={"approve": True}).status_code == 200
        # Applied by the platform, answer lost; the same pass reads the events the decision caused (a newer revision).
        sync(database, fake)
        decision = commands(database, ticket)[-1]
        assert (approval["status"], decision["status"], decision["last_error"]) == ("approved", "pending", "ReadTimeout")
        assert link(database, ticket)["revision"] == flow["revision"] > decision["body"]["sent_revision"]
        retry_now(database)
        sync(database, fake)
        first, again = fake.posts("/decision")
        assert first == again and commands(database, ticket)[-1]["status"] == "done"
        assert link(database, ticket)["status"] == "open" and FAILED_TEXT not in [m["text"] for m in chat(database, channel)]


def test_a_ticket_people_end_in_their_own_screens_closes_its_workflow_and_frees_the_chat(database, on, turns):
    fake = FakePlatform()
    with resident(database) as c:
        channel, ticket, flow = started(database, c, fake)
        flow["tracking"] = True  # a job the coordinator dispatched is still out
        version = sql(database, "select version from tickets where id=$1", UUID(ticket))[0]["version"]
        with client(database, "management") as manager:
            ended = manager.patch(f"/tickets/{ticket}/status", json={"version": version, "status": "cancelled", "reason": "Trùng yêu cầu"})
            assert ended.status_code == 200, ended.text
        # At once, before the worker has told the platform: the chat is Reception's.
        said = len(turns)
        say(c, channel, "Yêu cầu của tôi sao rồi?")
        assert turns[said:] == ["Yêu cầu của tôi sao rồi?"] and len(commands(database, ticket)) == 1
        sync(database, fake)
        sync(database, fake)
        [start, close] = commands(database, ticket)
        assert (close["kind"], close["status"]) == ("close", "done")
        sent = fake.posts("/close")[-1]
        assert (sent["reason"], sent["stop_tracking_only"]) == ("resident_requested_stop_tracking", True)
        assert (flow["state"], link(database, ticket)["status"]) == ("closed", "closed")
        assert FAILED_TEXT not in [m["text"] for m in chat(database, channel)]


def test_completion_never_forces_platform_to_stop_tracking_unfinished_work(database, on):
    fake = FakePlatform()
    with resident(database) as c:
        channel, ticket, flow = started(database, c, fake)
        approval, version = resolved_with_a_completion_request(database, ticket)
        fake.move(flow, "awaiting_confirmation", "operation_completed")
        sync(database, fake)
        flow["tracking"] = True  # the platform never learnt that the job ended (its event was lost)
        confirmed = c.post(f"/resident/approvals/{approval}/decision", headers=key(), json={"version": version, "approved": True, "note": "Đã xong, cảm ơn"})
        assert confirmed.status_code == 200, confirmed.text
        for _ in range(CLOSE_TRIES):
            sync(database, fake)
            close = commands(database, ticket)[-1]
            assert close["status"] == "pending" and close["last_error"].startswith("WORKFLOW_NOT_READY_TO_CLOSE")
            retry_now(database)
        assert [x["reason"] for x in fake.posts("/close")] == ["resident_confirmed"] * CLOSE_TRIES and link(database, ticket)["status"] == "open"
        sync(database, fake)
        sent = fake.posts("/close")
        assert len(sent) == CLOSE_TRIES + 1 and sent[-1]["reason"] == "resident_confirmed" and not sent[-1].get("stop_tracking_only")
        assert sent[-1]["external_request_id"] == sent[0]["external_request_id"]
        assert (link(database, ticket)["status"], commands(database, ticket)[-1]["status"]) == ("open", "pending")
        flow["tracking"] = False
        retry_now(database)
        sync(database, fake)
        assert (flow["state"], link(database, ticket)["status"], commands(database, ticket)[-1]["status"]) == ("closed", "closed", "done")


# ---- section 7: staff progress ----------------------------------------------------------------------------------------

EVENT = {"id": UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"), "ticket_id": UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"), "seq": 7,
         "occurred_at": datetime(2026, 10, 11, 2, 30, tzinfo=UTC)}
WORK = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
CONTEXT = {"work_order_id": UUID(WORK), "operations": {WORK: "cr_" + "1" * 32}, "staff_name": "Nguyễn Văn Hòa",
           "eta_at": datetime(2026, 10, 11, 8, 5, tzinfo=UTC), "quote": None}


def mapped(event_type, payload, **context):
    one = provider_events({**EVENT, "event_type": event_type, "payload": payload}, {**CONTEXT, **context})
    if one is None:
        return None
    assert (one["client_reference"], one["external_job_id"]) == ("cr_" + "1" * 32, WORK)
    return one["event_type"], one["data"]


def test_each_domain_event_becomes_the_progress_event_of_the_table():
    changed = lambda status: mapped("work_order.status_changed", {"workOrderId": WORK, "status": status, "note": "ghi chú nội bộ 0901234567"})  # noqa: E731
    assert mapped("work_order.offered", {"assignmentId": "x"}) == ("job.offered", {})
    assert mapped("work_assignment.responded", {"assignmentId": "x", "status": "rejected"}) == ("job.declined", {})
    # Times are shown as the resident reads them: Vietnam time.
    assert mapped("work_assignment.responded", {"assignmentId": "x", "status": "accepted"}) == (
        "job.accepted", {"staff_name": "Nguyễn Văn Hòa", "eta": "15:05 11/10/2026"})
    assert changed("en_route") == ("job.en_route", {"staff_name": "Nguyễn Văn Hòa"})
    assert changed("arrived") == ("job.arrived", {"staff_name": "Nguyễn Văn Hòa"})
    assert changed("in_progress") == ("job.started", {}) and changed("completed") == ("job.completed", {})
    kind, data = changed("cancelled")
    # The staff member's note is not the reason the resident reads.
    assert kind == "job.cancelled" and data["reason"] and "0901234567" not in data["reason"]
    assert changed("awaiting_approval") is None
    quote = {"id": UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd"), "kind": "customer_repair", "detail": {
        "note": "Thay vòi", "lines": [{"name": "Vòi lavabo", "quantity": "1", "unit": "cái", "unit_price": 650000, "amount": 650000},
                                      {"name": "Băng tan", "quantity": "2", "unit": "cuộn", "unit_price": 8000, "amount": 16000}],
        "labor_cost": 150000, "warranty_months": 6, "total": 816000}}
    kind, data = mapped("work_order.repair_proposed", {"workOrderId": WORK}, quote=quote)
    # The quote's id stays in the domain: the resident answers on the card, the coordinator has nothing to record.
    assert kind == "job.quote_ready" and set(data) == {"items", "total", "warranty_months", "approval_id"} and data["warranty_months"] == 6
    # Labour is a line of its own and the total is the sum of the amounts, in whole dong.
    assert data["items"] == [{"label": "Vòi lavabo (1 cái)", "amount": 650000}, {"label": "Băng tan (2 cuộn)", "amount": 16000},
                             {"label": "Tiền công", "amount": 150000}]
    assert data["total"] == sum(item["amount"] for item in data["items"]) == quote["detail"]["total"]
    assert mapped("work_order.repair_proposed", {"workOrderId": WORK}) is None
    # One event type for each answer: each has its own fixed line for the resident, and only a refusal wakes the coordinator.
    assert mapped("work_approval.decided", {"approvalId": "x", "status": "approved"}, quote=quote) == ("job.quote_approved", {})
    assert mapped("work_approval.decided", {"approvalId": "x", "status": "rejected"}, quote=quote) == ("job.quote_rejected", {})
    assert mapped("work_approval.decided", {"approvalId": "x", "status": "approved"}, quote={**quote, "kind": "customer_completion"}) is None
    # Work the platform did not dispatch is not reported, and neither is anything outside the table.
    assert mapped("work_order.offered", {"assignmentId": "x"}, operations={}) is None
    assert mapped("work_order.offered", {"assignmentId": "x"}, work_order_id=None) is None
    assert mapped("work_order.created", {"workOrderId": WORK}) is None and mapped("ticket.created", {}) is None
    # Offers that ran out or found nobody, a new appointment, and the published result (tests/test_platform_tools.py emits them).
    assert mapped("work_assignment.expired", {"assignmentId": "x", "workOrderId": WORK}) == ("job.offer_expired", {})
    assert mapped("work_order.unassigned", {"workOrderId": WORK}) == ("job.unassigned", {})
    assert mapped("work_order.rescheduled", {"workOrderId": WORK, "appointmentAt": "2026-10-12T02:00:00+00:00", "reason": "ghi chú 0901234567"}) == (
        "job.rescheduled", {"appointment": "09:00 12/10/2026"})
    kind, data = mapped("work_order.status_changed", {"workOrderId": WORK, "status": "cancelled", "note": "0901234567", "cancelledBy": "resident"})
    assert kind == "job.cancelled" and "cư dân" in data["reason"] and "0901234567" not in data["reason"]
    # The technician's acceptance report: who sent it, what they wrote for the resident. Nothing says the resident checked.
    assert mapped("ticket.resolution_published", {"message": "x"}, result={"photo_count": 3, "reported_by": "Nguyễn Văn Hòa", "note": None}) == (
        "job.result_published", {"summary": "Nhân viên đã làm xong và gửi kết quả nghiệm thu.", "photo_count": 3, "reported_by": "Nguyễn Văn Hòa"})
    kind, data = mapped("ticket.resolution_published", {"message": "x"}, result={
        "photo_count": 2, "reported_by": "Nguyễn Văn Hòa", "note": "Đã thay gioăng,\n  thử nước 10 phút không rỉ. " + "x" * 300})
    assert data["summary"].startswith("Nhân viên đã làm xong và gửi kết quả nghiệm thu. Ghi chú của nhân viên: Đã thay gioăng, thử nước 10 phút không rỉ. x")
    assert len(data["summary"]) == 200 and "\n" not in data["summary"] and "cư dân" not in data["summary"]
    # Management's own inspection of platform-dispatched work.
    assert mapped("ticket.resolution_published", {"message": "x"}, result={"photo_count": 0, "reported_by": None, "note": None}) == (
        "job.result_published", {"summary": "Công việc đã làm xong và Ban quản lý đã nghiệm thu.", "photo_count": 0, "reported_by": "Ban quản lý"})
    # A result published for work the platform did not dispatch says nothing to it.
    assert mapped("ticket.resolution_published", {"message": "x"}) is None


def test_the_signature_is_hmac_sha256_over_the_timestamp_a_dot_and_the_exact_bytes():
    row = {"event_id": EVENT["id"], "external_job_id": WORK, "client_reference": "cr_" + "1" * 32, "event_type": "job.accepted",
           "provider_version": 7, "occurred_at": EVENT["occurred_at"], "data": {"staff_name": "Nguyễn Văn Hòa", "eta": "15:05 11/10/2026"}}
    raw = event_body(row)
    assert raw == event_body({**dict(reversed(list(row.items()))), "data": dict(reversed(list(row["data"].items())))})
    assert json.loads(raw) == {"schema_version": "1", "external_event_id": str(EVENT["id"]), "external_job_id": WORK,
                               "client_reference": "cr_" + "1" * 32, "event_type": "job.accepted", "provider_version": 7,
                               "occurred_at": "2026-10-11T02:30:00.000000Z", "data": row["data"]}
    assert "Nguyễn Văn Hòa".encode() in raw  # sent as UTF-8, and signed as sent
    assert sign("s3cret", "1760000000", raw) == "v1=" + hmac.new(b"s3cret", b"1760000000." + raw, hashlib.sha256).hexdigest()
    assert sign("s3cret", "1760000000", raw) != sign("s3cret", "1760000000", raw + b" ")


def test_staff_progress_is_queued_signed_sent_in_order_and_resent_with_the_same_bytes(database, on):
    fake = FakePlatform()
    reference = "cr_" + uuid4().hex
    with resident(database) as c:
        channel, ticket, flow = started(database, c, fake)
        with client(database, "management") as manager:
            version = manager.get("/tickets/" + ticket).json()["ticket"]["version"]
            order = manager.post(f"/tickets/{ticket}/work-orders", json={
                "category_id": CATEGORY, "required_specialty_id": CATEGORY, "description": "Thay bóng đèn", "ticket_version": version})
            assert order.status_code == 201, order.text
            order = order.json()
        # What the dispatch tool records: this work order was created for that platform operation.
        sql(database, """insert into platform_operations(client_reference,tenant_id,ticket_id,tool,work_order_id,answer)
            values($1,$2,$3,'vh_work_order_dispatch',$4,'{"status":"pending"}') returning client_reference""",
            reference, TENANT, UUID(ticket), UUID(order["id"]))
        staff = sql(database, "select sp.id,u.name from staff_profiles sp join users u on u.id=sp.user_id where sp.user_id='local-v3-technical'")[0]
        offered = offer(database, order, staff["id"])
        assert offered.status_code == 201, offered.text
        with client(database, "technical") as worker:
            work = accept(worker, offered.json())
            for status in ("en_route", "arrived"):
                moved = advance(worker, work, status)
                assert moved.status_code == 200, moved.text
                work = moved.json()
            proposed = worker.post(f"/work-orders/{work['id']}/repair-proposal", json={
                "version": work["version"], "note": "Thay bóng đèn LED mới", "labor_cost": 50000, "warranty_months": 3,
                "lines": [{"name": "Bóng LED", "quantity": "2", "unit": "cái", "unit_price": 75000}]})
            assert proposed.status_code == 201, proposed.text

        fake.refuse = (503, "INTERNAL_ERROR")  # the first event is refused once: nothing later may overtake it
        sync(database, fake)
        rows = sql(database, "select * from platform_outbox where ticket_id=$1 order by provider_version", UUID(ticket))
        assert [r["event_type"] for r in rows] == ["job.offered", "job.accepted", "job.en_route", "job.arrived", "job.quote_ready"]
        assert {r["status"] for r in rows} == {"pending"} and rows[0]["attempts"] == 1 and fake.received == {}
        assert not [m for m in chat(database, channel) if 'platform' in m]
        assert not any(a["ticket_id"] == ticket for a in c.get("/resident/approvals").json()["items"])
        approval_id = sql(database, "select id from work_approvals where work_order_id=$1 and kind='customer_repair'", UUID(order['id']))[0]['id']
        version_before = sql(database, 'select version from tickets where id=$1', UUID(ticket))[0]['version']
        assert c.post(f'/resident/approvals/{approval_id}/decision', headers=key(), json={
            'version': version_before, 'approved': True, 'note': 'Premature quote'}).status_code == 409
        events = {str(e["id"]): e for e in sql(database, "select id,seq,occurred_at from ticket_events where ticket_id=$1", UUID(ticket))}
        for r in rows:  # spec section 3: the event id, its number and its time are the ticket event's
            assert (events[str(r["event_id"])]["seq"], events[str(r["event_id"])]["occurred_at"]) == (r["provider_version"], r["occurred_at"])
            assert (r["client_reference"], r["external_job_id"]) == (reference, order["id"])
        retry_now(database)
        sync(database, fake)

        approval = sql(database, "select id from work_approvals where work_order_id=$1 and kind='customer_repair'", UUID(order["id"]))[0]["id"]
        # The quote is a card in the chat, written by the domain itself, once: the bill in words and as data.
        sync(database, fake)
        [card] = [m for m in chat(database, channel) if "platform" in m]
        assert card == {
            "text": "Báo giá sửa chữa của nhân viên:\n- Bóng LED (2 cái): 150.000 đồng\n- Tiền công: 50.000 đồng\n"
                    "Tổng cộng: 200.000 đồng. Bảo hành 3 tháng.\nBạn xem rồi bấm Đồng ý hoặc Không đồng ý trên thẻ báo giá này.",
            "platform": {"kind": "quote", "approval_id": str(approval), "labor_cost": 50000, "warranty_months": 3, "total": 200000,
                         "expires_at": None, "lines": [{"name": "Bóng LED", "quantity": 2, "unit": "cái", "unit_price": 75000, "amount": 150000}]}}
        # The technician's own note is not on it, and where the quote stands is not stored: the API reads it each time.
        assert "Thay bóng đèn LED mới" not in json.dumps(card, ensure_ascii=False)

        def shown():
            [message] = [m for m in c.get(f"/resident/chats/{channel}/messages").json()["items"] if m["body"].get("platform")]
            assert message["sender_client_id"] == "platform" and "VH-" not in json.dumps(message)
            return message["body"]["platform"]

        assert shown() == {**card["platform"], "status": "pending"}
        version = sql(database, "select version from tickets where id=$1", UUID(ticket))[0]["version"]
        agreed = c.post(f"/resident/approvals/{approval}/decision", headers=key(), json={"version": version, "approved": True, "note": "Đồng ý"})
        assert agreed.status_code == 200, agreed.text
        assert shown() == {**card["platform"], "status": "approved"}
        for status, reads in (("rejected", "rejected"), ("cancelled", "expired"), ("pending", "pending")):
            sql(database, "update work_approvals set status=$2 where id=$1 returning id", approval, status)
            assert shown()["status"] == reads
        sql(database, "update work_approvals set expires_at=now()-interval '1 minute' where id=$1 returning id", approval)
        assert shown()["status"] == "expired"
        sql(database, "update work_approvals set status='approved',expires_at=null where id=$1 returning id", approval)
        with client(database, "technical") as worker:
            work = worker.get(f"/work-orders/{order['id']}").json()["workOrder"]
            assert advance(worker, work, "in_progress").status_code == 200
        sync(database, fake)
        sync(database, fake)
        rows = sql(database, "select * from platform_outbox where ticket_id=$1 order by provider_version", UUID(ticket))
        kinds = ["job.offered", "job.accepted", "job.en_route", "job.arrived", "job.quote_ready", "job.quote_approved", "job.started"]
        assert [r["event_type"] for r in rows] == kinds and {r["status"] for r in rows} == {"sent"}
        # The fake checked every signature over the bytes it received; here is what those bytes said, in order.
        got = [r["body"] for r in fake.received.values()]
        assert [b["event_type"] for b in got] == kinds and [b["provider_version"] for b in got] == sorted(b["provider_version"] for b in got)
        assert all(b["client_reference"] == reference and b["external_job_id"] == order["id"] for b in got)
        assert got[1]["data"]["staff_name"] == staff["name"] and got[1]["data"]["eta"] and got[2]["data"] == {"staff_name": staff["name"]}
        assert got[4]["data"] == {"approval_id": str(approval), "warranty_months": 3, "total": 200000, "items": [
            {"label": "Bóng LED (2 cái)", "amount": 150000}, {"label": "Tiền công", "amount": 50000}]}
        assert got[5]["data"] == {}
        # Still one card: passes of the worker do not write it again.
        assert len([m for m in chat(database, channel) if "platform" in m]) == 1
        # The receipt was followed until the platform applied the event.
        assert all(json.loads(r["receipt"])["ingestion_status"] == "applied" for r in rows)

        # Sent again (the answer was lost): the same id and the very same bytes, which the platform takes as a duplicate.
        sql(database, "update platform_outbox set status='pending',next_attempt_at=now() where event_id=$1 returning event_id", rows[1]["event_id"])
        before = len(fake.posts("/provider/job-events"))
        sync(database, fake)
        again = sql(database, "select status,receipt from platform_outbox where event_id=$1", rows[1]["event_id"])[0]
        assert len(fake.posts("/provider/job-events")) == before + 1 and again["status"] == "sent"
        assert json.loads(again["receipt"])["duplicate"] is True and len(fake.received) == len(kinds)


def test_a_second_worker_does_not_send_a_tickets_later_events_past_the_first(database, on):
    fake = FakePlatform()
    with resident(database) as c:
        channel, ticket, flow = started(database, c, fake)
        for version, kind in ((101, "job.offered"), (102, "job.accepted")):
            sql(database, """insert into platform_outbox(event_id,tenant_id,ticket_id,client_reference,external_job_id,event_type,provider_version,occurred_at,data)
                values($1,$2,$3,'cr_two_workers','job-1',$4,$5,now(),'{}') returning event_id""", uuid4(), TENANT, UUID(ticket), kind, version)
        # Another worker is in the middle of this ticket's events (it waits for the platform's answer).
        holding, release = threading.Event(), threading.Event()

        def other_worker():
            async def hold():
                connection = await asyncpg.connect(database["admin"])
                try:
                    async with connection.transaction():
                        await connection.execute("select pg_advisory_xact_lock(hashtextextended($1,0))", "platform-progress:" + ticket)
                        holding.set()
                        while not release.is_set():
                            await asyncio.sleep(0.05)
                finally:
                    await connection.close()
            asyncio.run(hold())

        thread = threading.Thread(target=other_worker)
        thread.start()
        try:
            assert holding.wait(20)
            sync(database, fake)
            assert fake.received == {}
        finally:
            release.set()
            thread.join()
        sync(database, fake)
        assert [(r["body"]["event_type"], r["body"]["provider_version"]) for r in fake.received.values()] == [
            ("job.offered", 101), ("job.accepted", 102)]


def test_a_progress_event_the_platform_refuses_for_good_is_kept_as_rejected(database, on):
    fake = FakePlatform()
    with resident(database) as c:
        channel, ticket, flow = started(database, c, fake)
        event = sql(database, "select id,seq,occurred_at from ticket_events where ticket_id=$1 order by seq limit 1", UUID(ticket))[0]
        sql(database, """insert into platform_outbox(event_id,tenant_id,ticket_id,client_reference,external_job_id,event_type,provider_version,occurred_at,data)
            values($1,$2,$3,'cr_unknown','job-1','job.unheard_of',$4,$5,'{}') returning event_id""",
            event["id"], TENANT, UUID(ticket), event["seq"], event["occurred_at"])
        fake.refuse = (422, "UNKNOWN_EVENT_TYPE")
        sync(database, fake)
        row = sql(database, "select status,attempts,receipt from platform_outbox where event_id=$1", event["id"])[0]
        assert (row["status"], row["attempts"]) == ("rejected", 1) and json.loads(row["receipt"])["error"] == "UNKNOWN_EVENT_TYPE"
        sync(database, fake)
        assert len(fake.posts("/provider/job-events")) == 1


# ---- the tables -------------------------------------------------------------------------------------------------------

def test_the_api_role_sees_only_its_own_tenants_links(database, on):
    with resident(database) as c:
        hand_over(c)

    async def run():
        connection = await asyncpg.connect(database["runtime"].replace("postgresql+asyncpg:", "postgresql:"))
        try:
            async def visible(tenant, table):
                async with connection.transaction():
                    if tenant:
                        await connection.execute("select set_config('app.tenant_id',$1,true)", str(tenant))
                    return await connection.fetchval(f"select count(*) from {table}")

            seen = {table: (await visible(TENANT, table), await visible(uuid4(), table), await visible(None, table))
                    for table in ("platform_links", "platform_commands")}
            with pytest.raises(asyncpg.PostgresError):
                async with connection.transaction():
                    await connection.execute("select set_config('app.tenant_id',$1,true)", str(TENANT))
                    await connection.execute("insert into platform_inbox(tenant_id,platform_id,ticket_id) select $1,'msg_x',ticket_id "
                                             "from platform_links limit 1", uuid4())
            with pytest.raises(asyncpg.PostgresError):  # the role writes rows; it does not delete what was sent
                async with connection.transaction():
                    await connection.execute("select set_config('app.tenant_id',$1,true)", str(TENANT))
                    await connection.execute("delete from platform_commands")
            return seen
        finally:
            await connection.close()

    for own, other, none in asyncio.run(run()).values():
        assert own > 0 and other == 0 and none == 0


def test_the_bridge_is_off_without_a_url_and_refuses_a_half_configuration(monkeypatch):
    for name in ("URL", "CUSTOMER_KEY", "PROVIDER_KEY", "SIGNING_KEY_ID", "SIGNING_SECRET", "MCP_TOKEN"):
        monkeypatch.delenv("VINHOMES_API_PLATFORM_" + name, raising=False)
    assert Bridge.from_env() is None and bridge.enabled() is False
    monkeypatch.setenv("VINHOMES_API_PLATFORM_URL", "http://platform.test/")
    with pytest.raises(ValueError, match="CUSTOMER_KEY"):
        Bridge.from_env()
    for name, value in (("CUSTOMER_KEY", CUSTOMER_KEY), ("PROVIDER_KEY", PROVIDER_KEY), ("SIGNING_KEY_ID", KEY_ID), ("SIGNING_SECRET", SECRET)):
        monkeypatch.setenv("VINHOMES_API_PLATFORM_" + name, value)
    assert Bridge.from_env() == BRIDGE and bridge.enabled() is True
    monkeypatch.setenv("VINHOMES_API_PLATFORM_MCP_TOKEN", "short")
    with pytest.raises(ValueError, match="32"):
        Bridge.from_env()


# ---- emergencies ------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("words", [
    "Bóng đèn bị cháy", "Bóng đèn phòng khách bị cháy", "Bóng đèn phòng khách nhà tôi bị cháy rồi, nhờ thay giúp", "Đèn nhà tắm cháy rồi",
    "Bóng đèn ở bếp cháy mất rồi", "Cầu chì tủ điện bị cháy", "Cầu chì nhà tôi hay bị cháy", "Cháy bóng đèn hành lang",
    "Bóng đèn hành lang bị cháy bóng, tối om", "Nấu cơm bị cháy", "Không có cháy, chỉ là đèn không sáng",
    "Nhờ ban quản lý thay giúp bóng đèn hành lang bị cháy", "Em ơi bóng đèn nhà tắm bị cháy rồi ạ", "Bóng đèn tầng 12 bị cháy từ hôm qua",
    "Đèn trần phòng ngủ cháy rồi thay giúp tôi với"])
def test_a_burnt_out_bulb_or_fuse_is_not_a_fire(words):
    assert emergency_kind(words) is None


@pytest.mark.parametrize("words", [
    "Cháy", "Cháy nhà", "Bếp nhà tôi đang cháy", "Nhà hàng xóm bị cháy", "Rèm cửa bốc cháy", "Đèn phòng khách bốc cháy", "Đèn đang cháy",
    "Bóng đèn cháy lan sang rèm", "Bóng đèn bị cháy, có mùi khét và bốc khói", "Bóng đèn bị cháy và đang bốc khói", "Đèn bị cháy, có lửa ở ổ điện",
    "Bóng đèn bị cháy. Hành lang đang cháy", "Ổ cắm bị cháy", "Tủ điện bốc khói", "Có khói đen ở hành lang", "Cháy rồi, đèn tắt hết",
    # A lamp in the sentence does not make a fire a burnt-out bulb: a verb before "cháy", something else that burns,
    # how or what it burns.
    "Đèn cháy rồi lan sang rèm", "Ổ cắm cạnh đèn ngủ bị cháy", "Bóng đèn nổ rồi cháy rèm cửa phòng ngủ", "đèn chùm cháy rực",
    "Đèn chập làm cháy ổ điện, cứu với", "Đèn bắt cháy vào rèm rồi", "Bóng đèn bùng cháy", "Đèn ngủ cháy ngùn ngụt",
    "Đèn trần phòng ngủ cháy dữ dội", "Cạnh cột đèn có xe máy cháy", "Tắt đèn đi bếp cháy rồi", "Đèn sưởi nhà tắm cháy lên, lan sang rèm",
    "Đèn hành lang tầng 12 phát cháy", "Hộp đèn quảng cáo dưới sảnh cháy rất mạnh", "Cầu chì tổng tầng 5 cháy khét lẹt cả hành lang",
    "Đèn cháy. Rèm cũng đang bén", "Xe máy dưới hầm cạnh cột đèn B2 bị cháy", "Tủ điện tầng 12 gần bóng đèn hành lang bị cháy",
    "đèn sưởi bị chập gây cháy rèm cửa", "Đèn bàn bắt cháy vào rèm", "Đèn sưởi nhà tắm phát cháy", "Đèn hành lang chập cháy"])
def test_a_fire_is_still_a_fire(words):
    assert emergency_kind(words) == "fire"
