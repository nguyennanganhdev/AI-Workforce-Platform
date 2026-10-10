"""Human workspace uses the partner engine without impersonating partner users."""
# ruff: noqa: F811
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

from sqlalchemy import insert
from test_workforce import ADMIN, stack, start  # noqa: F401

from awp.providers import ModelCatalog, ModelSpec
from awp.workforce import schema as s
from awp.workforce import worker
from awp.workforce.console import password_hash

BASE = "/workforce/v1/admin/workspace"


def test_specialist_setup_failure_blocks_work_without_waiting_for_leader(stack, monkeypatch):
    client, service, _, _ = stack
    ready(client, service)
    accepted = client.post(BASE + "/sessions", headers=ADMIN,
        json={"request_id": "failed-specialist", "text": "Inspect"}).json()
    job = client.portal.call(worker.claim, service, "failure-test")
    case = {"leader_session_id": "current-leader", "leader_agent_id": "leader"}

    async def seed():
        async with service.tx() as conn:
            for session_id, generation in [("current-leader", job["generation"]), ("stale-child", 0)]:
                await conn.execute(insert(s.session_fences).values(id=session_id, job_id=job["id"],
                    owner=job["owner"], generation=generation, role="leader" if generation else "worker"))
    client.portal.call(seed)
    monkeypatch.setattr(service.rt.storage, "get_session", AsyncMock(return_value=SimpleNamespace(team_id="current-team")))
    team = SimpleNamespace(session_id="current-leader", data=SimpleNamespace(
        members=[SimpleNamespace(session_id="failed-child")]))
    monkeypatch.setattr(service.rt.storage, "get_team", AsyncMock(return_value=team))
    failures = {"stale-child"}

    async def messages(_user, session_id):
        return ([SimpleNamespace(finished_reason="error")] if session_id in failures else []), None
    monkeypatch.setattr(service.rt.storage, "list_messages", messages)
    assert client.portal.call(worker.failed_session, service, job, "tenant", case) is None
    failures.add("failed-child")  # Setup failed before this member could bind a session fence.
    monkeypatch.setattr(worker, "prepare", AsyncMock(return_value=("tenant", case, "Inspect")))
    from awp.workforce import assets
    monkeypatch.setattr(assets, "vision_blocks", AsyncMock(return_value=[]))
    monkeypatch.setattr(service.intake.client, "say", AsyncMock())
    client.portal.call(worker.execute, service, job)
    detail = client.get(BASE + "/sessions/" + accepted["workflow_id"], headers=ADMIN).json()
    assert detail["workflow"]["state"] == "needs_attention"
    assert detail["requests"][0]["status"] == "blocked"
    assert detail["requests"][0]["error"] == {
        "code": "AGENT_EXECUTION_FAILED", "retryable": False, "session_id": "failed-child"}


def ready(client, service):
    service.rt.catalog = ModelCatalog([ModelSpec(id="test-model", provider="openai", model="scripted",
        price_in=1, price_out=2)], env={"OPENAI_API_KEY": "test-not-a-real-key"})
    assert client.put(BASE + "/setup", headers=ADMIN, json={"leader_profile": "supervisor"}).status_code == 200


def test_model_readiness_setup_and_no_user_selected_team(stack):
    client, service, _, _ = stack
    assert client.post(BASE + "/sessions", headers=ADMIN, json={"request_id": "1", "text": "Review"}).status_code == 409
    assert client.put(BASE + "/setup", headers=ADMIN, json={"leader_profile": "missing"}).status_code == 422
    assert client.put(BASE + "/setup", headers=ADMIN, json={"leader_profile": "supervisor"}).status_code == 200
    assert client.post(BASE + "/sessions", headers=ADMIN, json={"request_id": "1", "text": "Review"}).status_code == 503
    ready(client, service)
    service.rt.catalog.specs["test-model"].price_in = None
    blocked = client.post(BASE + "/sessions", headers=ADMIN, json={"request_id": "1", "text": "Review"})
    assert blocked.json()["error"]["code"] == "MODEL_PRICE_NOT_CONFIGURED"
    service.rt.catalog.specs["test-model"].price_in = 1
    assert client.post(BASE + "/sessions", headers=ADMIN,
        json={"request_id": "1", "text": "Review", "agent_ids": ["invented"]}).status_code == 422
    body = {"request_id": "1", "text": "Review source evidence"}
    accepted = client.post(BASE + "/sessions", headers=ADMIN, json=body)
    assert accepted.status_code == 202, accepted.text
    flow = accepted.json()["workflow_id"]
    replay = client.post(BASE + "/sessions", headers=ADMIN, json=body)
    assert replay.json()["workflow_id"] == flow
    assert replay.json()["request_id"] == accepted.json()["request_id"]
    detail = client.get(BASE + "/sessions/" + flow, headers=ADMIN).json()
    assert detail["team"] == []  # The configured pool is not an invented roster.
    assert detail["workflow"]["snapshot"]["profiles"] == {"supervisor": 1}
    assert detail["source"] == "internal" and detail["can_reply"]
    assert client.get(BASE + "/sessions", headers=ADMIN).json()["items"][0]["title"] == body["text"]


def test_settings_change_does_not_invalidate_existing_workflow_and_reply_deduplicates(stack):
    client, service, _, _ = stack
    ready(client, service)
    accepted = client.post(BASE + "/sessions", headers=ADMIN, json={"request_id": "first", "text": "Research"}).json()
    flow = accepted["workflow_id"]
    assert client.put(BASE + "/setup", headers=ADMIN,
        json={"leader_profile": "supervisor", "budget_micros": 800000}).status_code == 200
    assert client.post(BASE + "/sessions", headers=ADMIN,
        json={"request_id": "first", "text": "Research"}).json()["workflow_id"] == flow
    body = {"request_id": "reply", "text": "Additional evidence"}
    reply = client.post(BASE + "/sessions/" + flow + "/messages", headers=ADMIN, json=body)
    assert reply.status_code == 202, reply.text
    assert client.post(BASE + "/sessions/" + flow + "/messages", headers=ADMIN, json=body).json()["request_id"] == reply.json()["request_id"]
    assert client.get(BASE + "/sessions/" + flow, headers=ADMIN).json()["workflow"]["snapshot"]["budget_micros"] == 500000


def test_partner_is_observable_but_cannot_be_replied_to_from_workspace(stack):
    client, service, headers, _ = stack
    ready(client, service)
    response, _ = start(client, headers)
    flow = response.json()["workflow_id"]
    detail = client.get(BASE + "/sessions/" + flow, headers=ADMIN).json()
    assert detail["source"] == "partner" and not detail["can_reply"]
    assert client.post(BASE + "/sessions/" + flow + "/messages", headers=ADMIN,
        json={"request_id": "no-impersonation", "text": "Approve"}).status_code == 404
    assert client.get(BASE + "/sessions/" + flow, headers={"Authorization": "Bearer other-admin"}).status_code == 401
    service.rt.settings.admin_keys["other-admin"] = "other-tenant"
    assert client.get(BASE + "/sessions/" + flow, headers={"Authorization": "Bearer other-admin"}).status_code == 404
    assert client.get(BASE + "/sessions", headers={"Authorization": "Bearer other-admin"}).json()["items"] == []


def test_human_rbac_csrf_and_owner_boundary(stack):
    client, service, _, _ = stack
    ready(client, service)
    hashed = password_hash("workspace-test-password")
    object.__setattr__(service.rt.settings, "console_secure_cookie", False)
    users = service.rt.settings.console_users
    for username, role in [("alice", "admin"), ("bob", "admin"), ("viewer", "viewer"), ("operator", "operator")]:
        users[username] = {"tenant": "tenant", "role": role, "password_hash": hashed}
    login = client.post("/console/login", json={"username": "alice", "password": "workspace-test-password"}).json()
    assert client.post(BASE + "/sessions", json={"request_id": "1", "text": "No CSRF"}).status_code == 403
    csrf = {"X-CSRF-Token": login["csrf"]}
    accepted = client.post(BASE + "/sessions", headers=csrf, json={"request_id": "1", "text": "Alice request"})
    assert accepted.status_code == 202
    flow = accepted.json()["workflow_id"]
    for username in ("viewer", "operator", "bob"):
        login = client.post("/console/login", json={"username": username, "password": "workspace-test-password"}).json()
        csrf = {"X-CSRF-Token": login["csrf"]}
        assert not client.get(BASE + "/sessions/" + flow).json()["can_reply"]
        assert client.post(BASE + "/sessions/" + flow + "/messages", headers=csrf,
            json={"request_id": "cross-owner", "text": "Not Alice"}).status_code == (404 if username == "bob" else 403)


def test_team_memory_and_case_file_are_real_and_tenant_scoped(stack):
    client, service, _, _ = stack
    ready(client, service)
    flow = client.post(BASE + "/sessions", headers=ADMIN, json={"request_id": "inspect", "text": "Inspect"}).json()["workflow_id"]
    async def seed():
        case_id = await service.rt.cases.create_case(tenant="tenant", domain="workforce", external_ref=flow,
            user_id="awp:tenant", intake={}, budget_usd=.5, budget_tokens=100000)
        from sqlalchemy import update
        async with service.tx() as conn:
            await conn.execute(update(s.workflows).where(s.workflows.c.id == flow).values(case_id=case_id))
            await conn.execute(insert(s.memory).values(workflow_id=flow, profile_key="supervisor", key="next",
                text="Unverified next step", updated=time.time()))
        await service.rt.cases.bind_session(case_id, "actual-session", "actual-agent", "Supervisor", "leader")
        await service.rt.cases.add(case_id, "question", "Supervisor", {"text": "Can you verify this?"}, addressee="Researcher")
    client.portal.call(seed)
    detail = client.get(BASE + "/sessions/" + flow, headers=ADMIN).json()
    assert detail["team"][0]["session_id"] == "actual-session"
    assert detail["items"][0]["kind"] == "question"
    assert detail["memory"][0]["text"] == "Unverified next step"
    assert detail["cost"]["totals"]["calls"] == 0
    assert client.get("/console/assets/workspace.js").status_code == 200
    assert client.get("/console/assets/console.py").status_code == 404


def test_stop_tracking_fences_jobs_and_is_idempotent(stack):
    client, service, _, _ = stack
    ready(client, service)
    flow = client.post(BASE + "/sessions", headers=ADMIN, json={"request_id": "stop-me", "text": "Research"}).json()["workflow_id"]
    body = {"request_id": "stop", "expected_revision": 1, "action": "confirm"}
    assert client.post(BASE + "/sessions/" + flow + "/close", headers=ADMIN, json=body).status_code == 409
    body["action"] = "stop"
    stopped = client.post(BASE + "/sessions/" + flow + "/close", headers=ADMIN, json=body)
    assert stopped.status_code == 200, stopped.text
    assert client.post(BASE + "/sessions/" + flow + "/close", headers=ADMIN, json=body).json() == stopped.json()
    detail = client.get(BASE + "/sessions/" + flow, headers=ADMIN).json()
    assert detail["workflow"]["state"] == "closed" and not detail["can_reply"]
    from awp.workforce.worker import claim
    assert client.portal.call(claim, service, "must-not-run") is None
