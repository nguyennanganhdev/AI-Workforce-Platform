"""Offline end-to-end: real platform (Docker) + scripted model + fake partner MCP.

No real model is called. With the Docker stack up (WORKFORCE_PARTNER_API=true):

    python fake_openai.py 18080 > model.log &
    python fake_partner_mcp.py 18765 > mcp.log &
    E2E_MCP_LOG=mcp.log python drive.py

It registers a manager whose credential points at the scripted model, onboards
a partner from a declaration, confirms the route, sends a ticket, then signed
provider events (template + wake), and closes after confirmation.
"""

import hashlib
import hmac
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path

import httpx

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
BASE = os.getenv("E2E_PLATFORM", "http://127.0.0.1:8000")
ENV = dict(re.findall(r"^([A-Z0-9_]+)=(.*)$", (HERE.parents[2] / ".env").read_text(encoding="utf-8"), re.M))
SECRET = {"X-Provisioning-Secret": ENV["PARTNER_API_PROVISIONING_SECRET"]}
RUN = uuid.uuid4().hex[:6]
EMAIL, PASSWORD = f"e2e.manager.{RUN}@example.com", "E2e-password-" + RUN
DECLARATION = {
    "declaration": "e2e-v1",
    "client": {"name": f"E2E Partner {RUN}", "domain": "vinhomes"},
    "profiles": [{
        "key": "lead", "name": f"E2ELeader{RUN}", "role": "leader", "mission": "điều phối thử",
        "instructions": "Tra phiếu, giao việc rồi báo người dùng bằng CaseSay.", "tools_allow": ["vh_*"],
    }],
    "route": {"leader_profile": "lead", "config": {"rules": {"safe_reply": "Chưa xác minh được.", "phrase_rules": []}}},
    "mcp_server": {"name": f"e2epartner{RUN}", "timeout": 8.0},
    "tools": [
        {"name": "vh_ticket_get", "mcp_tool": "vh_ticket_get", "read_only": True, "tracking": "none"},
        {"name": "vh_work_order_dispatch", "mcp_tool": "vh_work_order_dispatch", "read_only": False,
         "tracking": "events", "client_reference_arg": "client_reference"},
    ],
    "integration": {"event_schema": {"version": "1", "events": {
        "job.accepted": {"status": "accepted", "rank": 20, "public_fields": ["staff_name"],
                         "message": "Nhân viên {staff_name} đã nhận yêu cầu của bạn."},
        "job.result_published": {"status": "result_published", "rank": 90, "terminal": True,
                                 "outcome": "completed", "wake": True, "evidence": True},
    }}},
}


def check(r, *ok):
    if r.status_code not in ok:
        raise SystemExit(f"{r.request.method} {r.request.url.path} -> {r.status_code} {r.text[:400]}")
    return r.json() if r.content else {}


def step(text):
    print(f"\n== {text}", flush=True)


with httpx.Client(base_url=BASE, timeout=180) as http:
    step("manager + fake-model credential")
    check(http.post("/auth/register", json={"email": EMAIL, "username": f"e2e_{RUN}", "password": PASSWORD,
                                            "domain_id": "vinhomes", "area_id": "ocean-park-2"}), 201)
    token = check(http.post("/auth/login", json={"tenant_id": "default", "identity": EMAIL, "password": PASSWORD}), 200)["access_token"]
    auth = {"Authorization": "Bearer " + token}
    me = check(http.get("/auth/me", headers=auth), 200)
    check(http.post("/workforce/v1/admin/memberships/verify", headers=SECRET, json={"manager_account_id": me["id"]}), 200)
    check(http.post("/credential/", headers=auth, json={"data": {
        "type": "openai_credential", "name": "Fake model", "api_key": "fake-key", "base_url": "http://host.docker.internal:18080/v1"}}), 201)

    step("onboard partner from its declaration")
    onboarded = check(http.post("/workforce/v1/admin/partner-onboarding", headers=SECRET, json={
        "declaration": DECLARATION, "manager_account_id": me["id"],
        "mcp_url": "http://host.docker.internal:18765/mcp", "mcp_token": "t" * 40,
        "management_refs": ["e2e-ref"], "environment": "sandbox"}), 200)
    keys = onboarded.pop("keys")
    print(json.dumps(onboarded, ensure_ascii=False))
    customer = {"Authorization": "ApiKey " + keys["customer_key"]}
    route = onboarded["routes"][0]
    confirmed = check(http.post(f"/workforce/v1/partner/routes/{route['route_id']}/confirm", headers=customer,
                                json={"schema_version": "1", "external_management_ref": "e2e-ref", "expected_revision": route["revision"]}), 200)
    print("route", confirmed["status"])

    step("start_workflow (handover message)")
    ids = {"external_user_id": "resident-e2e", "external_ticket_id": f"T-{RUN}", "external_conversation_id": f"chat-{RUN}:T-{RUN}"}
    started = check(http.post("/workforce/v1/partner/requests", headers=customer, json={
        "schema_version": "1", "command_type": "start_workflow", "external_request_id": f"cmd-{RUN}-1",
        "external_management_ref": "e2e-ref", "timezone": "Asia/Ho_Chi_Minh", **ids,
        "message": {"type": "text", "text": f"ticket_id: T-{RUN}\nMô tả của cư dân: Rò nước bồn rửa"}}), 200, 202)
    deadline = time.time() + 120
    while True:
        result = check(http.get(f"/workforce/v1/partner/requests/{started['request_id']}", headers=customer,
                                params={"external_user_id": "resident-e2e"}), 200)
        if result["request_status"] in ("completed", "failed", "blocked") or time.time() > deadline:
            break
        time.sleep(2)
    print("request", result["request_status"], "state", result["workflow_state"])
    print("messages", [m["text"] for m in (result.get("result") or {}).get("messages") or []])

    step("provider events (signed)")
    history = lambda: check(http.get(f"/workforce/v1/partner/conversations/{started['conversation_id']}/event-history",
                                     headers=customer, params={"external_user_id": "resident-e2e", "limit": 200}), 200)["items"]

    def send(event_id, event_type, data):
        body = {"schema_version": "1", "external_event_id": event_id, "event_type": event_type,
                "client_reference": client_reference, "occurred_at": "2026-10-14T08:00:00Z", "data": data}
        raw = json.dumps(body, ensure_ascii=False).encode()
        stamp = str(int(time.time()))
        sig = "v1=" + hmac.new(keys["signing_secret"].encode(), stamp.encode() + b"." + raw, hashlib.sha256).hexdigest()
        return check(http.post("/workforce/v1/provider/job-events", content=raw, headers={
            "Authorization": "ApiKey " + keys["provider_key"], "Content-Type": "application/json",
            "X-Partner-Timestamp": stamp, "X-Partner-Key-Id": keys["signing_key_id"], "X-Partner-Signature": sig}), 202)

    client_reference = sys.argv[1] if len(sys.argv) > 1 else None
    if client_reference is None:
        mcp_log = Path(os.getenv("E2E_MCP_LOG", "mcp.log")).read_text(encoding="utf-8")
        client_reference = re.findall(r'"client_reference": "([^"]+)"', mcp_log)[-1]
    print("accepted ->", send(f"ev-{RUN}-1", "job.accepted", {"staff_name": "Bình"})["ingestion_status"])
    print("published ->", send(f"ev-{RUN}-2", "job.result_published", {})["ingestion_status"])
    deadline = time.time() + 120
    while time.time() < deadline:
        items = history()
        states = [i["payload"]["state"] for i in items if i["event_type"] == "workflow.status_changed"]
        if states and states[-1] == "awaiting_confirmation":
            break
        time.sleep(2)
    for item in history():
        payload = item["payload"]
        print(item["sequence"], item["event_type"], payload.get("text") or payload.get("state") or payload.get("status") or "")
    revision = [i["payload"]["revision"] for i in history() if i["event_type"] == "workflow.status_changed"][-1]

    step("close after confirmation")
    closed = check(http.post(f"/workforce/v1/partner/workflows/{started['workflow_id']}/close", headers=customer, json={
        "schema_version": "1", "external_request_id": f"close-{RUN}", **ids,
        "expected_revision": revision, "reason": "resident_confirmed"}), 200)
    print("closed:", closed["workflow_state"])
