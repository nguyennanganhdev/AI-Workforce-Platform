"""Agent-evaluation tickets: control-plane only, sandbox only, never handed to the platform."""

import asyncio
import os
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from vinhomes_api import business_sandbox_fixture as fixture
from vinhomes_api import eval_fixture
from vinhomes_api.platform_access import router


def client(monkeypatch, *, enabled=True):
    monkeypatch.setenv("VINHOMES_API_PLATFORM_MCP_TOKEN", "control-plane")
    if enabled:
        monkeypatch.setenv(eval_fixture.ENABLED_ENV, "enabled")
    else:
        monkeypatch.delenv(eval_fixture.ENABLED_ENV, raising=False)
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_requires_the_control_plane_bearer(monkeypatch):
    response = client(monkeypatch).post("/platform/eval-fixtures", json={"run_id": "r1"},
                                        headers={"Authorization": "Bearer discovery"})
    assert response.status_code == 401


def test_is_off_unless_explicitly_enabled(monkeypatch):
    response = client(monkeypatch, enabled=False).post("/platform/eval-fixtures", json={"run_id": "r1"},
                                                       headers={"Authorization": "Bearer control-plane"})
    assert response.status_code == 404


@pytest.mark.parametrize("run,count", [("../prod", 1), ("Upper", 1), ("ok", 0), ("ok", 21)])
def test_rejects_bad_run_or_count_before_touching_data(run, count):
    with pytest.raises(ValueError):
        asyncio.run(eval_fixture.create_eval_tickets(object(), run, count))


def test_real_tickets_are_handed_over_only_to_the_eval(tmp_path, monkeypatch):
    # Explicit opt-in: a NEW marked synthetic sandbox, never an existing runtime database.
    url = os.getenv("BUSINESS_SANDBOX_TEST_URL")
    if not url:
        pytest.skip("Set BUSINESS_SANDBOX_TEST_URL to a fresh isolated marked sandbox")
    monkeypatch.setenv("VINHOMES_API_PLATFORM_URL", "http://platform.invalid")  # enables the handover; never called

    async def exercise():
        await fixture.initialize(url, tmp_path / "private", os.environ["BUSINESS_SANDBOX_TEST_RUNTIME_PASSWORD"])
        engine = fixture.create_async_engine(url.replace("postgresql:", "postgresql+asyncpg:", 1))
        try:
            async with engine.begin() as db:
                await db.execute(fixture.text("select set_config('app.tenant_id',:t,true)"), {"t": fixture.TENANT})
                first = await eval_fixture.create_eval_tickets(db, "eval-contract", 3)
            async with engine.begin() as db:
                await db.execute(fixture.text("select set_config('app.tenant_id',:t,true)"), {"t": fixture.TENANT})
                assert await eval_fixture.create_eval_tickets(db, "eval-contract", 3) == first
                other = await eval_fixture.create_eval_tickets(db, "eval-other", 1)
                assert other[0]["ticket_id"] not in {t["ticket_id"] for t in first}
                ids = [UUID(t["ticket_id"]) for t in first]
                links = (await db.execute(fixture.text(
                    "select status,state from platform_links where ticket_id=any(:ids)"), {"ids": ids})).all()
                assert links == [("pending", "closed")] * 3
                pending = (await db.execute(fixture.text(
                    "select count(*) from platform_commands where ticket_id=any(:ids) and status='pending'"),
                    {"ids": ids})).scalar_one()
                assert pending == 0, "the sync worker must have nothing to send"
            for ticket in first:
                assert f"ticket_id: {ticket['ticket_id']}" in ticket["handover_text"]
                UUID(ticket["external_request_id"])
            return first
        finally:
            await engine.dispose()
    first = asyncio.run(exercise())

    # The platform then obtains a ticket-scoped bearer exactly as at runtime.
    from types import SimpleNamespace
    from uuid import uuid4

    from sqlalchemy.pool import NullPool
    monkeypatch.setenv("VINHOMES_API_PLATFORM_MCP_TOKEN", "control-plane")
    app = FastAPI()
    app.include_router(router)
    app.state.engine = fixture.create_async_engine(url.replace("postgresql:", "postgresql+asyncpg:", 1), poolclass=NullPool)
    app.state.settings = SimpleNamespace(tenant_id=fixture.TENANT)
    ticket = first[0]
    response = TestClient(app).post("/platform/mcp-grants", headers={"Authorization": "Bearer control-plane"}, json={
        "ticket_id": ticket["ticket_id"], "external_request_id": ticket["external_request_id"],
        "workflow_id": "agent-eval:eval-contract", "grant_request_id": str(uuid4()),
        "tools": ["vh_ticket_get", "vh_ticket_cancel"], "ttl_seconds": 600})
    assert response.status_code == 200, response.text
    assert response.json()["ticket_id"] == ticket["ticket_id"] and response.json()["bearer_token"].startswith("vhm_")
