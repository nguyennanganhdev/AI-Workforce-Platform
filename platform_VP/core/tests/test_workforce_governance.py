# ruff: noqa: F811 -- imported pytest fixtures are resolved by name
import json
import time

import pytest
from sqlalchemy import insert, update
from test_workforce import ADMIN, stack, start  # noqa: F401 -- pytest fixture

from awp.middleware.room import ToolGateMiddleware
from awp.profiles import AgentProfile
from awp.runtime import Binding
from awp.workforce import lifecycle
from awp.workforce import schema as s
from awp.workforce.execution import Fence, reserve
from awp.workforce.knowledge import SearchKnowledge
from awp.workforce.memory import MemoryRecall, MemoryRemember
from awp.workforce.retention import prune
from awp.workforce.service import Fault, row
from awp.workforce.worker import claim


def test_old_session_cannot_adopt_new_execution_and_monthly_limit(stack):
    from awp.workforce.execution import current_fence
    client, service, headers, _ = stack
    response, _ = start(client, headers)
    first = client.portal.call(claim, service, "old")
    async def expire():
        async with service.tx() as conn:
            await conn.execute(update(s.workflows).where(s.workflows.c.id == response.json()["workflow_id"]).values(case_id="case-fence"))
            await conn.execute(insert(s.session_fences).values(id="old-session", job_id=first["id"], owner="old",
                generation=first["generation"], role="leader"))
            await conn.execute(update(s.jobs).where(s.jobs.c.id == first["id"]).values(lease_until=0))
    client.portal.call(expire)
    second = client.portal.call(claim, service, "new")
    with pytest.raises(Fault, match="STALE_EXECUTION"):
        client.portal.call(current_fence, service, "case-fence", "old-session", "awp:tenant", "agent")
    object.__setattr__(service.rt.settings, "workforce_monthly_budget_usd", .000001)
    fence = Fence(second["id"], second["owner"], second["generation"])
    client.portal.call(reserve, service, fence, 1, 1)
    with pytest.raises(Fault, match="MONTHLY_BUDGET_EXHAUSTED"):
        client.portal.call(reserve, service, fence, 1, 1)


def test_uncertain_mcp_write_is_never_repeated(stack, monkeypatch):
    from contextlib import asynccontextmanager

    from awp.workforce import mcp
    client, service, headers, _ = stack
    response, _ = start(client, headers)
    job = client.portal.call(claim, service, "owner")
    dispatched = []
    class Remote:
        async def call_tool(self, name, args):
            dispatched.append((name, args))
            raise TimeoutError("Response lost after domain applied operation")
    @asynccontextmanager
    async def lost_response(*args):
        yield Remote()
    monkeypatch.setattr(mcp, "session", lost_response)
    async def setup():
        async with service.tx() as conn:
            await conn.execute(insert(s.integrations).values(id="test-domain", tenant="tenant", status="active", revision=1,
                config={"url": "http://unused/mcp", "encrypted_headers": service.cipher().encrypt(b"{}").decode()}))
            await conn.execute(insert(s.operations).values(id="uncertain", workflow_id=response.json()["workflow_id"],
                integration_id="test-domain", client_reference="stable-reference", status="queued", provider_version=0,
                created=time.time(), data={"arguments": {"ticket_id": "ticket-1"}, "tool": "create_order",
                    "revision": 1, "request_id": job["request_id"], "arguments_hash": "hash", "policy": {"tracks_events": True}}))
    client.portal.call(setup)
    fence = Fence(job["id"], job["owner"], job["generation"])
    first = client.portal.call(mcp.perform_operation, service, "uncertain", fence)
    second = client.portal.call(mcp.perform_operation, service, "uncertain", fence)
    assert first["error"] == second["error"] == "OUTCOME_UNKNOWN"
    assert len(dispatched) == 1
    inspect = client.get(f"/workforce/v1/admin/workflows/{response.json()['workflow_id']}", headers=ADMIN).json()
    assert inspect["workflow"]["state"] == "needs_attention"
    assert inspect["operations"][0]["status"] == "unknown"
    # An operator verifies the real outcome; resume once without redispatching.
    client.portal.call(lifecycle.complete, service, response.json()["workflow_id"], "Operator review needed.")
    async def require_continuation():
        async with service.tx() as conn:
            op = await row(conn, s.operations, s.operations.c.id == "uncertain")
            await conn.execute(update(s.operations).where(s.operations.c.id == op["id"]).values(
                data={**op["data"], "continuation_required": True}))
    client.portal.call(require_continuation)
    verified = {"expected_status": "unknown", "status": "confirmed", "evidence": "Domain receipt verified by operator."}
    assert client.post("/workforce/v1/admin/operations/uncertain/reconcile", headers=ADMIN, json=verified).status_code == 200
    assert client.post("/workforce/v1/admin/operations/uncertain/reconcile", headers=ADMIN, json=verified).status_code == 409
    continued = client.portal.call(claim, service, "reconciled")
    async def continuation():
        async with service.rt.db.engine.connect() as conn:
            return await row(conn, s.requests, s.requests.c.id == continued["request_id"])
    request = client.portal.call(continuation)
    assert request["command"] == "system_continuation"
    assert verified["evidence"] in request["body"]["message"]["text"]
    assert len(dispatched) == 1


def test_console_cookie_csrf_and_roles(stack):
    from awp.workforce.console import password_hash
    client, wf, _, _ = stack
    object.__setattr__(wf.rt.settings, "console_secure_cookie", False)
    users = wf.rt.settings.console_users
    hashed = password_hash("test-only-password")
    users.update({"maintainer": {"password_hash": hashed, "tenant": "tenant", "role": "admin"},
                  "viewer": {"password_hash": hashed, "tenant": "tenant", "role": "viewer"}})
    assert client.get("/console").status_code == 200
    assert client.post("/console/login", json={"username": "maintainer", "password": "wrong"}).status_code == 401
    response = client.post("/console/login", json={"username": "maintainer", "password": "test-only-password"})
    assert response.status_code == 200
    assert "httponly" in response.headers["set-cookie"].lower()
    csrf = response.json()["csrf"]
    assert client.get("/workforce/v1/admin/clients").status_code == 200
    assert client.post("/workforce/v1/admin/clients/customer/rotate").status_code == 403
    assert client.post("/workforce/v1/admin/clients/customer/rotate", headers={"X-CSRF-Token": csrf, "Origin": "http://evil.invalid"}).status_code == 403
    assert client.post("/workforce/v1/admin/clients/customer/rotate", headers={"X-CSRF-Token": csrf}).status_code == 200
    audits = client.get("/workforce/v1/admin/audit").json()["items"]
    assert any(a["actor"] == "maintainer" and a["action"] == "client.rotate" for a in audits)
    response = client.post("/console/login", json={"username": "viewer", "password": "test-only-password"})
    assert client.get("/workforce/v1/admin/clients").status_code == 200
    assert client.post("/workforce/v1/admin/clients/customer/rotate", headers={"X-CSRF-Token": response.json()["csrf"]}).status_code == 403
    users["viewer"]["disabled"] = True
    assert client.get("/workforce/v1/admin/clients").status_code == 401


def test_knowledge_versions_route_acl_and_private_memory(stack):
    client, wf, headers, route_id = stack
    document = {"knowledge_base_id": "building_a", "document_key": "procedure", "title": "Water leak",
                "text": "Water leak procedure OLD: call management. Verified policy 1.", "source": "approved-procedure"}
    first = client.post("/workforce/v1/admin/knowledge/documents", headers=ADMIN, json=document)
    assert first.status_code == 201
    client.post("/workforce/v1/admin/knowledge/documents", headers=ADMIN,
                json={**document, "knowledge_base_id": "building_b", "text": "Water leak PRIVATE-B"})
    async def configure():
        profile = AgentProfile(key="supervisor", name="Supervisor", role="leader", mission="Verify and organize",
            knowledge={"knowledge_base_ids": ["building_a", "building_b"]}, memory={"enabled": True}, tools_allow=["*"])
        rec = await wf.rt.profiles.create_draft("tenant", profile)
        await wf.rt.profiles.publish("tenant", rec.key, rec.version)
        aid = await wf.intake.client.agent_id("tenant", profile, rec.version)
        async with wf.tx() as conn:
            route = await row(conn, s.routes, s.routes.c.id == route_id)
            await conn.execute(update(s.routes).where(s.routes.c.id == route_id).values(
                config={**route["config"], "knowledge_base_ids": ["building_a"]}))
        return profile, aid
    profile, aid = client.portal.call(configure)
    _result, _ = start(client, headers)
    job = client.portal.call(claim, wf, "owner")
    binding = Binding("case", "session", aid, "Supervisor", "leader", "awp:tenant", Fence(job["id"], "owner", job["generation"]))
    client.post("/workforce/v1/admin/knowledge/documents", headers=ADMIN,
                json={**document, "text": "Water leak NEW must not enter existing workflow"})
    output = client.portal.call(SearchKnowledge(wf, binding).call, "Water leak")
    data = json.loads(output.content[0].text)
    assert data["hits"] and "OLD" in data["hits"][0]["text"]
    assert all("NEW" not in h["text"] and "PRIVATE-B" not in h["text"] for h in data["hits"])
    client.portal.call(MemoryRemember(wf, binding).call, "next", "Unverified note")
    assert "Unverified note" in client.portal.call(MemoryRecall(wf, binding).call).content[0].text
    second, _ = start(client, headers, external_request_id="second", external_ticket_id="second", external_conversation_id="second")
    second_job = client.portal.call(claim, wf, "owner2")
    assert second_job["workflow_id"] == second.json()["workflow_id"]
    other = Binding("other", "other", aid, "Supervisor", "leader", "awp:tenant", Fence(second_job["id"], "owner2", second_job["generation"]))
    assert "Unverified note" not in client.portal.call(MemoryRecall(wf, other).call).content[0].text
    gate = ToolGateMiddleware(wf.rt, binding, profile, "tenant")
    for name in ("Bash", "PowerShell", "Read", "Write", "Edit", "Skill", "AgentInvite", "TeamDelete", "CaseRequest"):
        assert not gate.allowed(name)
    assert gate.allowed("memory_recall") and gate.allowed("AgentCreate")
    assert client.post(f"/workforce/v1/admin/knowledge/documents/{first.json()['id']}/revoke", headers=ADMIN).status_code == 200
    assert not json.loads(client.portal.call(SearchKnowledge(wf, binding).call, "Water leak").content[0].text)["hits"]


def test_membership_revocation_blocks_history_and_model_spend(stack):
    client, wf, headers, _ = stack
    response, _ = start(client, headers)
    job = client.portal.call(claim, wf, "owner")
    assert client.put("/workforce/v1/partner/residences/A-101", headers=headers, json={
        "external_user_id": "resident-1", "external_management_ref": "BQL-1", "expected_revision": 1, "status": "inactive"}).status_code == 200
    assert client.get(response.json()["conversation_url"] + "/event-history", headers=headers,
        params={"external_user_id": "resident-1"}).status_code == 403
    with pytest.raises(Fault) as error:
        client.portal.call(reserve, wf, Fence(job["id"], "owner", job["generation"]), 1, 1)
    assert error.value.code == "RESIDENCE_NOT_AUTHORIZED"


def test_retention_requires_closed_flow_and_snapshot_recovers_cursor(stack):
    client, wf, headers, _ = stack
    response, _ = start(client, headers)
    data = response.json()
    client.portal.call(claim, wf, "owner")
    client.portal.call(lifecycle.complete, wf, data["workflow_id"], "Read-only result")
    path = data["conversation_url"]
    before = client.get(path + "/event-history", headers=headers, params={"external_user_id": "resident-1"}).json()
    old_cursor = before["items"][0]["event_id"]
    client.portal.call(prune, wf, time.time() + 91 * 86400)
    assert client.get(path + "/event-history", headers=headers, params={"external_user_id": "resident-1", "after_cursor": old_cursor}).status_code == 410
    snapshot = client.get(path, headers=headers, params={"external_user_id": "resident-1"}).json()
    assert snapshot["messages"][0]["text"] == "Read-only result"
    recovered = client.get(path + "/event-history", headers=headers,
        params={"external_user_id": "resident-1", "after_cursor": snapshot["snapshot_cursor"]})
    assert recovered.status_code == 200 and not recovered.json()["items"]
