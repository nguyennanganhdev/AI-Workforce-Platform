from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from mcp.types import Tool, ToolAnnotations
from sqlalchemy import select

from vp import integrations, runtime
from vp.context import build_context
from vp.db import Artifact, Job, Record, Reservation, Revision, Session, now, transaction
from vp.domain import create_session, freeze_agent
from vp.evaluations import score_case
from vp.knowledge import space_name
from vp.limits import BudgetExceeded, reserve
from vp.maintenance import settle_abandoned
from vp.queue import claim, fence, settle_orphaned_reservations
from vp.schemas import AgentResult


async def test_context_memory_agent_session_owner_isolation(principal, registry, leased):
    _, job = leased
    async with transaction() as db:
        other = await create_session(db, principal, "Other", registry, 500000)
        db.add(
            Artifact(
                id="proof",
                workspace="default",
                session_id=other.id,
                kind="evidence",
                body={"verified": True, "source": "fixture", "text": "Scoped memory"},
            )
        )
        for rid, owner, agent_id, status in [
            ("mine", "admin", "coordinator", "verified"),
            ("other-agent", "admin", "specialist", "verified"),
            ("other-owner", "another", "coordinator", "verified"),
            ("unverified", "admin", "coordinator", "candidate"),
        ]:
            db.add(
                Record(
                    id=rid,
                    workspace="default",
                    owner=owner,
                    kind="memory",
                    body={
                        "agent_id": agent_id,
                        "status": status,
                        "session_id": other.id,
                        "evidence_ids": ["proof"],
                        "text": rid,
                    },
                )
            )
        db.add(
            Artifact(
                workspace="default",
                session_id=other.id,
                kind="message",
                turn=1,
                body={"recipient": "coordinator", "text": "SECRET OTHER SESSION"},
            )
        )
    async with transaction() as db:
        session, _ = await fence(db, job.id, job.generation)
        spec = (await db.get(Revision, "coordinator-r1")).body
        context, _ = await build_context(db, session, job, spec)
        assert [m["id"] for m in context["memory"]] == ["mine"]
        assert not context["inbox"]
        assert context["goal"] == "Verify the source"


async def test_abandoned_call_charged_once_after_reclaim(leased):
    sid, job = leased
    model = {
        "id": "paid",
        "context_tokens": 1000,
        "max_output_tokens": 0,
        "input_micros_per_million": 1000000,
        "output_micros_per_million": 0,
        "pricing_version": "fixture",
        "rpm": 100,
        "tpm": 100000,
    }
    async with transaction() as db:
        session, _ = await fence(db, job.id, job.generation)
        rid = (await reserve(db, session, job, model)).id
        (await db.get(Job, job.id)).lease_until = now() - 1
    recovered = await claim("recovered")
    async with transaction() as db:
        session, current = await fence(db, recovered.id, recovered.generation)
        await settle_orphaned_reservations(db, session, current)
        await settle_orphaned_reservations(db, session, current)
    async with transaction() as db:
        session = await db.get(Session, sid)
        reservation = await db.get(Reservation, rid)
        assert session.spent == 1000 and session.reserved == 0
        assert reservation.status == "estimated_uncertain"


async def test_cancelled_abandoned_reservation_settled(leased):
    sid, job = leased
    price = {
        "id": "paid",
        "context_tokens": 1000,
        "max_output_tokens": 0,
        "input_micros_per_million": 1000000,
        "output_micros_per_million": 0,
        "pricing_version": "fixture",
        "rpm": 100,
        "tpm": 100000,
    }
    async with transaction() as db:
        session, _ = await fence(db, job.id, job.generation)
        await reserve(db, session, job, price)
        current = await db.get(Job, job.id)
        current.status = "cancelled"
        current.lease_until = now() - 1
    await settle_abandoned()
    async with transaction() as db:
        session = await db.get(Session, sid)
        assert session.spent == 1000 and session.reserved == 0


async def test_mcp_write_requires_exact_approval_and_uncertain_not_retried(
    client, leased, monkeypatch
):
    sid, job = leased
    calls = []

    class Client:
        async def list_tools(self):
            return SimpleNamespace(
                tools=[
                    Tool(
                        name="write",
                        inputSchema={
                            "type": "object",
                            "properties": {"value": {"type": "string"}},
                            "required": ["value"],
                        },
                        annotations=ToolAnnotations(readOnlyHint=False),
                    )
                ]
            )

        async def call_tool(self, name, args):
            calls.append((name, args))
            raise TimeoutError("effect may already have happened")

    @asynccontextmanager
    async def connection(config):
        yield Client()

    monkeypatch.setattr(integrations, "connection", connection)
    async with transaction() as db:
        db.add(
            Record(
                id="mcp",
                workspace="default",
                owner="admin",
                kind="mcp",
                body={
                    "url": "https://fixture.example/mcp",
                    "enabled": True,
                    "read_only": False,
                    "allowed_tools": ["write"],
                },
            )
        )
        spec = (await db.get(Revision, "coordinator-r1")).body
    tools = await integrations.mcp_tools(job, {**spec, "mcp_ids": ["mcp"]})
    await tools[0].call(value="exact approved value")
    assert calls == []
    await runtime.accept_result(
        job, AgentResult(status="blocked", answer="Need approval"), "missing-snapshot"
    )
    async with transaction() as db:
        execution = await db.scalar(select(Artifact).where(Artifact.kind == "tool_execution"))
        eid = execution.id
        assert (await db.get(Session, sid)).status == "awaiting_approval"
    response = await client.post(
        f"/api/sessions/{sid}/approvals/{eid}",
        json={"approve": True, "reason": "Test exact input approved"},
    )
    assert response.status_code == 200
    approval = await claim("approval-worker")
    await integrations.execute_approved(approval)
    assert calls == [("write", {"value": "exact approved value"})]
    async with transaction() as db:
        assert (await db.get(Artifact, eid)).body["status"] == "uncertain"
        assert (await db.get(Session, sid)).status == "needs_review"
    assert await claim("no-retry") is None


async def test_budget_block_prevents_provider_call(leased):
    _, job = leased
    spec = {
        "id": "paid",
        "context_tokens": 1000,
        "max_output_tokens": 0,
        "input_micros_per_million": 1000000000,
        "output_micros_per_million": 0,
        "pricing_version": "fixture",
        "rpm": 100,
        "tpm": 100000,
    }
    model = object()
    guard = runtime.Governance(job, {id(model): spec})
    called = False

    async def next_handler():
        nonlocal called
        called = True

    with pytest.raises(BudgetExceeded):
        await guard.on_model_call(
            None, {"current_model": model, "messages": [], "tools": []}, next_handler
        )
    assert not called


async def test_pinned_skill_and_catalog(principal, registry):
    async with transaction() as db:
        db.add(
            Record(
                id="skill",
                workspace="default",
                owner="admin",
                kind="skills",
                body={"name": "Fact check", "instructions": "Verify source before answering"},
            )
        )
        await db.flush()
        spec = (await db.get(Revision, "coordinator-r1")).body
        frozen = await freeze_agent(db, {**spec, "skill_ids": ["skill"]})
        (await db.get(Record, "skill")).body = {
            "name": "Changed",
            "instructions": "New instruction",
        }
        model = await db.get(Record, "model")
        model.body = {**model.body, "max_output_tokens": 999}
        assert frozen["skill_snapshots"][0]["instructions"] == "Verify source before answering"
        assert frozen["model_snapshots"]["model"]["max_output_tokens"] == 2048


def test_embedding_spaces_are_version_and_model_isolated():
    spec = {
        "id": "embedding",
        "version": 1,
        "adapter": "openai",
        "base_url": "",
        "model": "a",
        "dimensions": 3,
    }
    assert space_name("workspace", spec) != space_name("workspace", {**spec, "model": "b"})
    assert space_name("workspace", spec) != space_name("workspace", {**spec, "version": 2})
    assert space_name("workspace", spec) != space_name("other", spec)


def test_eval_does_not_accept_fabricated_success():
    case = {
        "expected_status": "complete",
        "must_contain": ["100"],
        "must_not_contain": ["200"],
        "require_sources": True,
    }
    assert not score_case(case, {"status": "complete", "answer": "200", "claims": []})["passed"]
