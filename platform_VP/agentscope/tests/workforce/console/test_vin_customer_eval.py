"""Positive C08 consumer run: actual adapters, fake Domain/MCP/model transport."""

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio

from test_vin_customer_cases import customer as customer  # noqa: F401
from vin_fixtures import authority as authority  # noqa: F401
from test_eval_sandbox import DISCOVERED, TicketModel, spec, not_production
from agentscope.app._service import _agent_eval, _eval_sandbox
from agentscope.app.storage import MCPRecord
from agentscope.app.vin_platform._contracts import CatalogEntry, ResourceGrant
from agentscope.app.vin_platform._domain import DomainAdapter
from agentscope.mcp import HttpMCPConfig, MCPClient


@pytest_asyncio.fixture
async def linked_eval(customer, monkeypatch):
    authority, storage = customer.authority, customer.storage
    admin = await authority.context("admin")
    adapter = DomainAdapter(authority)
    provider = await adapter.provider(admin, "vinhomes")
    await adapter.configure(admin, provider.model_copy(update={"environment": "sandbox"}))
    metadata = [{"name": key.split(":")[1], **meta} for key, meta in DISCOVERED.items()]
    source = MCPRecord(id="m", user_id="admin", client=MCPClient(name="prod-domain", is_stateful=False,
        mcp_config=HttpMCPConfig(url="https://production.fixture.invalid/mcp")), discovered_tools=metadata)
    sandbox = MCPRecord(id="sandbox-m", user_id="admin", client=MCPClient(name="sandbox-domain", is_stateful=False,
        mcp_config=HttpMCPConfig(url="https://domain.fixture.invalid/mcp", headers={"Authorization": "Bearer offline-sandbox-bootstrap"})),
        discovered_tools=metadata)
    records = {source.id: source, sandbox.id: sandbox}
    storage.get_mcp = AsyncMock(side_effect=lambda owner, ident: records.get(ident) if owner == "admin" else None)
    grants = []
    for record, environment in ((source, "production"), (sandbox, "sandbox")):
        entry = await authority.publish_catalog(admin, CatalogEntry(kind="mcp", resource_id=record.id, owner_id="admin", name=record.client.name, environment=environment))
        grants.append(await authority.grant(admin, ResourceGrant(catalog_id=entry, subject_kind="user", subject_id="alice", permissions=["view", "bind", "execute"])))
    profile = {"source_mcp_id": "m", "sandbox_mcp_id": "sandbox-m", "domain_provider_id": "vinhomes",
        "mcp_url": "https://domain.fixture.invalid/mcp", "grant_path": "/api/business/platform/mcp-grants", "ttl_seconds": 300}
    monkeypatch.setenv(_eval_sandbox.ENV, json.dumps([profile]))
    state = {"seeds": [], "cleanups": [], "grants": [], "calls": [], "cleanup_error": False, "tickets": {}, "tokens": {}}
    def transport(request):
        assert request.url.host == "domain.fixture.invalid", "No production or foreign HTTP permitted"
        body = json.loads(request.content) if request.content else None
        path = request.url.path
        if path == "/customer/grants":
            return httpx.Response(200, json={"access_token": "offline-linked-customer"})
        if path == "/customer/eval-fixtures":
            assert request.headers["Authorization"] == "Bearer offline-linked-customer"
            state["seeds"].append(body)
            tickets = [{"ticket_id": str(uuid4()), "external_request_id": str(uuid4()), "handover_text": ""} for _ in range(body["count"])]
            for ticket in tickets:
                ticket["handover_text"] = "ticket_id: " + ticket["ticket_id"] + "\nFixture rò nước riêng cư dân"
            state["tickets"][body["run_id"]] = tickets
            return httpx.Response(200, json={"tickets": tickets, "data_mode": "synthetic_test", "run_namespace": "fixture-scope"})
        if path == "/customer/eval-fixtures/cleanup":
            state["cleanups"].append(body)
            if state["cleanup_error"]:
                return httpx.Response(503, json={"detail": "offline-private-error-never-expose"})
            return httpx.Response(200, json={"data_mode": "synthetic_test", "retired": len(state["tickets"].get(body["run_id"], [])), "audit_retained": True})
        if path == "/api/business/platform/mcp-grants":
            assert request.headers["Authorization"] == "Bearer offline-sandbox-bootstrap"
            assert any(ticket["ticket_id"] == body["ticket_id"] for tickets in state["tickets"].values() for ticket in tickets)
            token = "offline-ticket-" + body["ticket_id"]
            state["tokens"][token] = body["ticket_id"]
            state["grants"].append(body)
            return httpx.Response(200, json={"bearer_token": token, "ticket_id": body["ticket_id"], "workflow_id": body["workflow_id"],
                "tools": body["tools"], "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()})
        raise AssertionError(path)
    real_client = httpx.AsyncClient
    monkeypatch.setattr(_eval_sandbox.httpx, "AsyncClient", lambda **kwargs: real_client(transport=httpx.MockTransport(transport), **kwargs))
    async with real_client(transport=httpx.MockTransport(transport)) as client:
        authority.http_client = client
        async def call_tool(bound, name, arguments, **kwargs):
            token = bound.mcp_config.headers["Authorization"].removeprefix("Bearer ")
            assert state["tokens"][token] == arguments["ticket_id"]
            state["calls"].append((arguments["ticket_id"], name))
            return json.dumps({"ticket_id": arguments["ticket_id"], "status": "cancelled" if name.endswith("cancel") else "open"})
        monkeypatch.setattr(_eval_sandbox, "call_tool", call_tool)
        yield SimpleNamespace(authority=authority, storage=storage, state=state, grant_ids=grants, profile=profile)


@pytest.mark.asyncio
async def test_positive_c08_linked_resident_eval_runs_five_cases_and_cleans_up(linked_eval):
    env = linked_eval
    box = await _eval_sandbox.eval_sandbox(env.storage, "alice", spec())
    model = TicketModel()
    report = await _agent_eval.run_spec_tests(spec=spec(), model=model, judge_model=model, discovered=DISCOVERED, run_tool=not_production, sandbox=box)
    assert report["passed"] == 5 and report["publishable"] is True
    assert report["environment"]["data_mode"] == "synthetic_test" and report["environment"]["isolated_business_sandbox"] is True
    assert report["environment"]["cleanup"] == {"status": "completed", "retired": 5, "audit_retained": True}
    assert len(env.state["grants"]) == 5 and len(env.state["calls"]) == 10
    assert len({ticket for ticket, _ in env.state["calls"]}) == 5
    assert env.state["seeds"][0]["run_id"] == env.state["cleanups"][0]["run_id"]
    assert report["results"][0]["tool_calls"][1]["consent_assumed"] is True
    assert "offline-ticket-" not in json.dumps(report) and "offline-sandbox-bootstrap" not in json.dumps(report)


@pytest.mark.asyncio
async def test_cleanup_failure_keeps_positive_cases_but_blocks_publication(linked_eval):
    env = linked_eval
    env.state["cleanup_error"] = True
    box = await _eval_sandbox.eval_sandbox(env.storage, "alice", spec())
    report = await _agent_eval.run_spec_tests(spec=spec(), model=TicketModel(), judge_model=TicketModel(), discovered=DISCOVERED, run_tool=not_production, sandbox=box)
    assert report["passed"] == 5 and report["publishable"] is False
    assert report["environment"]["cleanup"]["status"] == "pending" and report["errors"] == 1
    assert "offline-private-error" not in json.dumps(report)


@pytest.mark.asyncio
async def test_other_resident_and_revoked_sandbox_cannot_seed_or_fall_back(linked_eval):
    env = linked_eval
    # Bob has no execute entitlement or linked subject; never use Alice's fixture.
    box = await _eval_sandbox.eval_sandbox(env.storage, "bob", spec())
    report = await _agent_eval.run_spec_tests(spec=spec(), model=TicketModel(), judge_model=TicketModel(), discovered=DISCOVERED, run_tool=not_production, sandbox=box)
    assert not report["publishable"] and not env.state["seeds"]
    await env.authority.revoke_grant(await env.authority.context("admin"), env.grant_ids[1])
    box = await _eval_sandbox.eval_sandbox(env.storage, "alice", spec())
    report = await _agent_eval.run_spec_tests(spec=spec(), model=TicketModel(), judge_model=TicketModel(), discovered=DISCOVERED, run_tool=not_production, sandbox=box)
    assert not report["publishable"] and not env.state["seeds"]
