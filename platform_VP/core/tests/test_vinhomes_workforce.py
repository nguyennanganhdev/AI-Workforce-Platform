# ruff: noqa: F811 -- imported pytest fixtures are resolved by name
"""Real Vinhomes PostgreSQL + Workforce HTTP + MCP boundary acceptance, no paid model."""
import asyncio
import contextlib
import json
import os
import socket
import sys
import threading
import time
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
import uvicorn
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine

if os.getenv("AWP_TEST_INFRA") != "1":
    pytest.skip("Requires isolated Workforce and Vinhomes infrastructure", allow_module_level=True)
pytest.importorskip("vinhomes_api", reason="Install Vinhomes optional workforce dependencies for connected tests")

DOMAIN_TESTS = Path(__file__).resolve().parents[3] / "vinhome_Recident/services/vinhomes-api/tests"
sys.path.insert(0, str(DOMAIN_TESTS))
from test_domain_database import operation
from test_resident_contract import CATEGORY, TENANT, database, image, sql  # noqa: F401
from test_resident_contract import client as resident_client
from test_workforce import ADMIN, stack  # noqa: F401
from vinhomes_api import database as domain_database
from vinhomes_api.v3_config import V3Settings
from vinhomes_api.workforce import (
    WorkforceClient,
    poll_binding,
    process_one,
    reconcile_outbox,
    transaction,
)
from vinhomes_api.workforce_config import WorkforceConfig
from vinhomes_api.workforce_mcp import build_mcp
from vinhomes_api.workforce_provider import collect

from awp.profiles import AgentProfile
from awp.runtime import Binding
from awp.workforce import lifecycle, provider
from awp.workforce import schema as s
from awp.workforce.execution import Fence
from awp.workforce.mcp import perform, tools_for_case
from awp.workforce.service import row
from awp.workforce.worker import claim


@contextlib.contextmanager
def mcp_server(app):
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", lifespan="on"))
    thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(.01)
    assert server.started
    try:
        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        server.should_exit = True
        thread.join(10)
        listener.close()


def test_reception_handoff_mcp_consent_staff_progress_and_tracking_close(stack, database, monkeypatch):
    pc, workforce, customer, _ = stack
    class Transport(httpx.AsyncBaseTransport):
        def __init__(self):
            self.local = httpx.ASGITransport(app=pc.app)
            self.network = httpx.AsyncHTTPTransport()
        async def handle_async_request(self, request):
            if request.url.host == "testserver":
                return await self.local.handle_async_request(request)
            assert request.url.host == "127.0.0.1" and request.url.port == 9090
            return await self.network.handle_async_request(request)
        async def aclose(self):
            await self.local.aclose()
            await self.network.aclose()
    import vinhomes_api.v3_files as ticket_files
    monkeypatch.setattr("vinhomes_api.v3_resident_support.FILE_ROOT", ticket_files.FILE_ROOT)
    event_schema = {"type": "object", "additionalProperties": False,
        "properties": {"business_status": {"type": "string"}, "business_version": {"type": "integer"}},
        "required": ["business_status", "business_version"]}
    created = pc.post("/workforce/v1/admin/clients", headers=ADMIN, json={"id": "vh-provider", "purpose": "provider",
        "operations": ["publish_job_event", "read_event_receipt"], "settings": {
        "event_map": {event: {"status": status, "mode": "snapshot", "schema": event_schema,
            "public_fields": ["business_status"]} for event, status in {
            "job.progress": "pending", "job.completed": "completed", "job.failed": "failed", "job.cancelled": "cancelled"}.items()},
        "transitions": {before: ["pending", "completed", "failed", "cancelled"] for before in ["pending", "offered", "assigned", "unknown"]}}})
    assert created.status_code == 201, created.text
    provider_key = created.json()
    config = WorkforceConfig("http://testserver", customer["Authorization"][7:], provider_key["api_key"],
        provider_key["signing_key_id"], provider_key["signing_secret"], "workforce-test", "s" * 40, "c" * 40, "vh-provider")
    for key, value in {"ENABLED": "1", "URL": config.url, "CUSTOMER_KEY": config.customer_key,
        "PROVIDER_KEY": config.provider_key, "SIGNING_KEY_ID": config.signing_key_id, "SIGNING_SECRET": config.signing_secret,
        "INTEGRATION_CLIENT_ID": config.integration_client_id, "MCP_SERVICE_KEY": config.mcp_service_key,
        "MCP_CONTEXT_KEY": config.mcp_context_key, "MCP_AUDIENCE": config.mcp_audience}.items():
        monkeypatch.setenv("VINHOMES_WORKFORCE_" + key, value)
    # Only the adapter scheduler is controlled here; requests/MCP/database use real implementations.
    async def parked(*args):
        await args[2].wait()
    monkeypatch.setattr("vinhomes_api.workforce.loop", parked)
    sql(database, "update integration_clients set accepts_cases=false where tenant_id=$1 returning id", TENANT)
    asyncio.run(domain_database.client(database["admin"], config.integration_client_id, "platform", True, {}, str(TENANT)))
    settings = V3Settings("127.0.0.1", 8000, database["runtime"], TENANT, "local-v3-resident")
    with mcp_server(build_mcp(settings, config)) as mcp_url, resident_client(database) as rc:
        context, _ = operation(rc, "get_verified_resident_context")
        place = context["residences"][0]
        channel = rc.post("/resident/chats", json={"title": "Workforce connected"}).json()["id"]
        photo = rc.post(f"/resident/chats/{channel}/photos?filename=leak.png&mimeType=image/png",
            content=image(), headers={"Idempotency-Key": str(uuid4()), "Content-Type": "image/png"})
        assert photo.status_code == 201, photo.text
        message = rc.post(f"/resident/chats/{channel}/messages", json={"text": "Bathroom is overflowing",
            "file_ids": [photo.json()["id"]], "client_message_id": str(uuid4())}).json()
        draft, _ = operation(rc, "create_ticket_draft", {"channel_id": channel, "domain_id": place["domain_id"],
            "building_id": place["building_id"], "unit_id": place["unit_id"], "category_id": CATEGORY})
        target = {"channel_id": channel, "draft_id": draft["draftId"]}
        operation(rc, "update_ticket_incident", {**target, "fields": {"request_kind": "incident", "source_message_id": message["id"],
            "facts": [{"key": "symptom", "value": "is overflowing", "source": "customer_report", "source_message_id": message["id"]},
                      {"key": "item", "value": "Bathroom", "source": "customer_report", "source_message_id": message["id"]}]}})
        operation(rc, "submit_ticket_assessment", {**target, "assessment": {"priority": "high", "severity": "major", "reason": "Resident report"}})
        handoff, retry = operation(rc, "handoff_ticket", {**target, "plan_required": False})
        assert handoff["accepted"], handoff
        ticket_id = handoff["ticket"]["id"]
        assert rc.post("/internal/reception/operations/execute", json=retry).json()["replayed"]
        binding_db = sql(database, "select * from vh_workforce_bindings where ticket_id=$1", UUID(ticket_id))[0]
        assert sql(database, "select count(*) n from vh_reception_supervisor_messages where ticket_id=$1", UUID(ticket_id))[0]["n"] == 0
        management = binding_db["management_ref"]
        async def profile_setup():
            profile = AgentProfile(key="supervisor", name="Supervisor", role="leader", mission="Verify then coordinate", tools_allow=["mcp__vh-provider__*"])
            rec = await workforce.rt.profiles.create_draft("tenant", profile)
            await workforce.rt.profiles.publish("tenant", rec.key, rec.version)
            return await workforce.intake.client.agent_id("tenant", profile, rec.version)
        agent_id = pc.portal.call(profile_setup)
        integration = pc.post("/workforce/v1/admin/integrations", headers=ADMIN, json={"id": "vh-provider", "url": mcp_url,
            "headers": {"Authorization": "Bearer " + config.mcp_service_key}, "context_signing_key": config.mcp_context_key,
            "tools": {"get_ticket": {"read_only": True, "requires_consent": False},
                      "create_work_order": {"requires_consent": True}, "offer_assignment": {"requires_consent": True, "tracks_events": True}}})
        assert integration.status_code == 201, integration.text
        route = pc.post("/workforce/v1/admin/routes", headers=ADMIN, json={"client_id": "customer", "external_management_ref": management,
            "workspace": "sandbox", "manager_ref": management, "leader_profile": "supervisor", "integration_ids": ["vh-provider"],
            "asset_capability": True, "read_only_auto_close": False}).json()
        assert pc.post(f"/workforce/v1/partner/routes/{route['route_id']}/confirm", headers=customer,
            json={"external_management_ref": management, "expected_revision": 1}).status_code == 200
        # A real scoped management actor is required; no admin override is supplied.
        manager = sql(database, "select m.user_id from scoped_user_roles r join tenant_memberships m on m.id=r.membership_id where r.role_code='management' and m.tenant_id=$1 limit 1", TENANT)[0]["user_id"]
        sql(database, "insert into vh_workforce_management_grants(tenant_id,management_unit_id,service_actor,tools,active) values($1,$2,$3,$4,true) returning service_actor",
            TENANT, UUID(management), manager, ["create_work_order", "offer_assignment"])
        async def connected():
            engine = create_async_engine(database["runtime"])
            api = WorkforceClient(config, Transport())
            try:
                assert await process_one(engine, TENANT, api, "adapter")
                async with transaction(engine, TENANT) as db:
                    binding = dict((await db.execute(text("select * from vh_workforce_bindings where id=:id"), {"id": binding_db["id"]})).mappings().one())
                assert binding["workflow_id"]
                async with workforce.tx() as conn:
                    assets = (await conn.execute(select(s.assets).where(s.assets.c.workflow_id == binding["workflow_id"]))).mappings().all()
                assert len(assets) == 1 and assets[0]["status"] == "ready"
                job = await claim(workforce, "supervisor-worker")
                b = Binding("test-case", "test-session", agent_id, "Supervisor", "leader", "awp:tenant", Fence(job["id"], job["owner"], job["generation"]))
                # Resolve tools through the real MCP initialize/list_tools protocol.
                async with workforce.tx() as conn:
                    flow = await row(conn, s.workflows, s.workflows.c.id == binding["workflow_id"])
                    await conn.execute(s.workflows.update().where(s.workflows.c.id == flow["id"]).values(case_id=b.case_id))
                tools = {tool.remote_name: tool for tool in await tools_for_case(workforce, b)}
                read = json.loads((await tools["get_ticket"].call(ticket_id=ticket_id)).content[0].text)
                assert read["ticket"]["id"] == ticket_id
                args = {"ticket_id": ticket_id, "category_id": CATEGORY, "required_specialty_id": CATEGORY,
                        "description": "Inspect bathroom overflow", "ticket_version": read["ticket"]["version"]}
                pending = json.loads((await tools["create_work_order"].call(**args)).content[0].text)
                assert pending["status"] == "awaiting_approval"
                await lifecycle.complete(workforce, flow["id"], "Please approve the inspection request")
                await poll_binding(engine, TENANT, api, binding)
                await reconcile_outbox(engine, TENANT, api)
                return binding, pending["operation_id"]
            finally:
                await api.http.aclose()
                await engine.dispose()
        binding, operation_id = pc.portal.call(connected)
        assert not sql(database, "select id from work_orders where ticket_id=$1", UUID(ticket_id))
        snapshot = rc.get(f"/api/domains/vinhomes/resident/workforce/tickets/{ticket_id}").json()
        approval = snapshot["snapshot"]["pending_approvals"][0]
        decision = {"external_request_id": "resident-decision", "decision": "approve", "expected_revision": approval["revision"],
                    "arguments_hash": approval["arguments_hash"], "quote_ref": approval["quote_ref"]}
        sent = rc.post(f"/api/domains/vinhomes/resident/workforce/tickets/{ticket_id}/approvals/{approval['id']}/decision", json=decision)
        assert sent.status_code == 202, sent.text
        async def execute_approval():
            engine = create_async_engine(database["runtime"])
            api = WorkforceClient(config, httpx.ASGITransport(app=pc.app))
            try:
                await process_one(engine, TENANT, api, "adapter")
                job = await claim(workforce, "operation-worker")
                assert job["kind"] == "operation"
                await perform(workforce, job)
                async with workforce.tx() as conn:
                    op = await row(conn, s.operations, s.operations.c.id == operation_id)
                assert op["status"] == "confirmed", op
                assert op["data"]["resume_request_id"]
                # Retrying a confirmed operation never creates a second work order.
                from awp.workforce.mcp import perform_operation
                await perform_operation(workforce, operation_id)
            finally:
                await api.http.aclose()
                await engine.dispose()
        pc.portal.call(execute_approval)
        assert len(sql(database, "select id from work_orders where ticket_id=$1", UUID(ticket_id))) == 1
        assert len(sql(database, "select id from messages where channel_id=$1 and body->'workforce'->>'workflow_id'=$2", channel, binding["workflow_id"])) == 1
        assert sql(database, "select status from tickets where id=$1", UUID(ticket_id))[0]["status"] == "assigned"
        staff = sql(database, "select id from staff_profiles where user_id='local-v3-technical'")[0]["id"]
        from datetime import UTC, datetime, timedelta
        async def offer_staff():
            engine = create_async_engine(database["runtime"])
            api = WorkforceClient(config, httpx.ASGITransport(app=pc.app))
            try:
                job = await claim(workforce, "resumed-supervisor")
                assert job["kind"] == "agent"
                b = Binding("test-case", "test-session", agent_id, "Supervisor", "leader", "awp:tenant", Fence(job["id"], job["owner"], job["generation"]))
                tools = {tool.remote_name: tool for tool in await tools_for_case(workforce, b)}
                read = json.loads((await tools["get_ticket"].call(ticket_id=ticket_id)).content[0].text)
                order = read["work_orders"][0]
                result = json.loads((await tools["offer_assignment"].call(ticket_id=ticket_id,
                    work_order_id=order["id"], staff_id=str(staff), work_order_version=order["version"],
                    offer_expires_at=(datetime.now(UTC) + timedelta(hours=1)).isoformat())).content[0].text)
                assert result["status"] == "awaiting_approval"
                await lifecycle.complete(workforce, binding["workflow_id"], "Please approve offering the work to staff")
                await poll_binding(engine, TENANT, api, binding)
                return result["operation_id"]
            finally:
                await api.http.aclose()
                await engine.dispose()
        offer_id = pc.portal.call(offer_staff)
        snapshot = rc.get(f"/api/domains/vinhomes/resident/workforce/tickets/{ticket_id}").json()["snapshot"]
        approval = snapshot["pending_approvals"][0]
        decision.update(external_request_id="approve-staff-offer", expected_revision=approval["revision"],
                        arguments_hash=approval["arguments_hash"], quote_ref=approval["quote_ref"])
        assert rc.post(f"/api/domains/vinhomes/resident/workforce/tickets/{ticket_id}/approvals/{approval['id']}/decision", json=decision).status_code == 202
        async def run_offer():
            engine = create_async_engine(database["runtime"])
            api = WorkforceClient(config, httpx.ASGITransport(app=pc.app))
            try:
                await process_one(engine, TENANT, api, "adapter")
                job = await claim(workforce, "offer-worker")
                assert job["kind"] == "operation"
                await perform(workforce, job)
                async with workforce.tx() as conn:
                    op = await row(conn, s.operations, s.operations.c.id == offer_id)
                assert op["status"] == "offered", op
                return op["data"]["result"]["assignment_id"], op["external_job_id"]
            finally:
                await api.http.aclose()
                await engine.dispose()
        assignment, external_job = pc.portal.call(run_offer)
        with resident_client(database, "technical") as technician:
            accepted = technician.post(f"/assignments/{assignment}/response", json={"status": "accepted", "eta_at": datetime.now(UTC).isoformat()})
            assert accepted.status_code == 200, accepted.text
        async def send_progress():
            engine = create_async_engine(database["runtime"])
            api = WorkforceClient(config, httpx.ASGITransport(app=pc.app))
            try:
                await collect(engine, TENANT)
                await process_one(engine, TENANT, api, "provider-adapter")
                async with workforce.tx() as conn:
                    receipt = (await conn.execute(select(s.receipts).where(s.receipts.c.external_id.like("vh:" + external_job + ":%"))
                        .order_by(s.receipts.c.received.desc()))).mappings().first()
                assert receipt and await provider.apply(workforce, receipt["id"])
                await reconcile_outbox(engine, TENANT, api)
                await poll_binding(engine, TENANT, api, binding)
            finally:
                await api.http.aclose()
                await engine.dispose()
        pc.portal.call(send_progress)
        snapshot = rc.get(f"/api/domains/vinhomes/resident/workforce/tickets/{ticket_id}").json()["snapshot"]
        assert snapshot["workflows"][0]["state"] == "waiting_external_event"
        closed = rc.post(f"/api/domains/vinhomes/resident/workforce/tickets/{ticket_id}/close", json={
            "external_request_id": "stop-tracking", "expected_revision": snapshot["workflows"][0]["revision"],
            "reason": "resident_requested_stop_tracking", "stop_tracking_only": True})
        assert closed.status_code == 202, closed.text
        async def stop_tracking():
            engine = create_async_engine(database["runtime"])
            api = WorkforceClient(config, httpx.ASGITransport(app=pc.app))
            try:
                await process_one(engine, TENANT, api, "close-adapter")
                await poll_binding(engine, TENANT, api, binding)
                async with workforce.tx() as conn:
                    flow = await row(conn, s.workflows, s.workflows.c.id == binding["workflow_id"])
                    assert flow["state"] == "closed"
            finally:
                await api.http.aclose()
                await engine.dispose()
        pc.portal.call(stop_tracking)
        assert sql(database, "select status from work_assignments where id=$1", UUID(assignment))[0]["status"] == "accepted"
        assert sql(database, "select status from tickets where id=$1", UUID(ticket_id))[0]["status"] == "assigned"
        # Business work continues through the real staff/evidence/QC/resident APIs.
        order_id = external_job.split(":", 1)[1]
        with resident_client(database, "technical") as technician:
            order = technician.get(f"/work-orders/{order_id}").json()["workOrder"]
            for status in ("en_route", "arrived"):
                changed = technician.patch(f"/work-orders/{order_id}/status", json={
                    "version": order["version"], "status": status, "note": "Verified staff step"})
                assert changed.status_code == 200, changed.text
                order = changed.json()
            proposal = technician.post(f"/work-orders/{order_id}/repair-proposal", json={
                "version": order["version"], "note": "Clear the blockage and inspect the pipe", "labor_cost": 0, "lines": []})
            assert proposal.status_code == 201, proposal.text
            order = technician.get(f"/work-orders/{order_id}").json()["workOrder"]
            unapproved = technician.patch(f"/work-orders/{order_id}/status", json={
                "version": order["version"], "status": "in_progress", "note": "Attempt before resident approval"})
            assert unapproved.status_code == 409
            current = rc.get(f"/resident/tickets/{ticket_id}").json()["ticket"]
            approved_repair = rc.post(f"/resident/approvals/{proposal.json()['id']}/decision",
                headers={"Idempotency-Key": str(uuid4())},
                json={"approved": True, "note": "Resident approves the onsite repair", "version": current["version"]})
            assert approved_repair.status_code == 200, approved_repair.text
            order = technician.get(f"/work-orders/{order_id}").json()["workOrder"]
            started = technician.patch(f"/work-orders/{order_id}/status", json={
                "version": order["version"], "status": "in_progress", "note": "Resident-approved work"})
            assert started.status_code == 200, started.text
            order = started.json()
            blocked = technician.patch(f"/work-orders/{order_id}/status", json={
                "version": order["version"], "status": "completed", "note": "Missing evidence"})
            assert blocked.status_code == 409
            for purpose in ("before", "after"):
                photo = technician.post(f"/tickets/{ticket_id}/files", content=image(),
                    headers={"Content-Type": "application/octet-stream"},
                    params={"filename": purpose + ".png", "mimeType": "image/png", "purpose": purpose})
                assert photo.status_code == 201, photo.text
                version = technician.get(f"/tickets/{ticket_id}").json()["ticket"]["version"]
                evidence = technician.post(f"/tickets/{ticket_id}/evidence", json={
                    "file_id": photo.json()["fileId"], "work_order_id": order_id,
                    "assignment_id": assignment, "purpose": purpose, "version": version})
                assert evidence.status_code == 201, evidence.text
            done = technician.patch(f"/work-orders/{order_id}/status", json={
                "version": order["version"], "status": "completed", "note": "Inspection completed with evidence"})
            assert done.status_code == 200, done.text
            assert technician.post(f"/work-orders/{order_id}/qc", json={"outcome": "pass", "criteria": []}).status_code == 403
        assert rc.get(f"/resident/tickets/{ticket_id}").json()["ticket"]["status"] == "in_progress"
        with resident_client(database, "management") as reviewer:
            qc = reviewer.post(f"/work-orders/{order_id}/qc", json={
                "outcome": "pass", "criteria": [{"name": "Overflow resolved", "passed": True}]})
            assert qc.status_code == 201, qc.text
        current = rc.get(f"/resident/tickets/{ticket_id}").json()["ticket"]
        assert current["status"] == "resolved"
        completion = next(a for a in rc.get("/resident/approvals?limit=100").json()["items"]
                          if a["ticket_id"] == ticket_id and a["kind"] == "customer_completion" and a["status"] == "pending")
        confirmed = rc.post(f"/resident/approvals/{completion['id']}/decision", headers={"Idempotency-Key": str(uuid4())},
            json={"approved": True, "note": "Resident verified the repair", "version": current["version"]})
        assert confirmed.status_code == 200, confirmed.text
        assert rc.get(f"/resident/tickets/{ticket_id}").json()["ticket"]["status"] == "closed"
        # A late business snapshot is recorded without reopening the closed workflow.
        pc.portal.call(send_progress)
        final = rc.get(f"/api/domains/vinhomes/resident/workforce/tickets/{ticket_id}").json()
        assert final["state"] == "closed"
