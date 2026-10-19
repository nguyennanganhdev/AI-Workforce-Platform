"""Fault injection through C09 and actual Redis atomic batch activation."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import update

from vin_fixtures import authority as authority  # noqa: F401
from storage_redis_knowledge_base_test import make_storage
from test_agent_studio_api import _Model, _WorkspaceManager
from agentscope.app._agent_spec import AgentSpec, SpecTest
from agentscope.app._router._workforce_console import ProposalView, ProposedAgentView, _persist_builder_turn, _stored_proposal
from agentscope.app._service import _publish_batch as batch
from agentscope.app._service._agent_eval import run_spec_tests
from agentscope.app._service._personal_jobs import PersonalJobWorker
from agentscope.app.storage import AsyncSQLAlchemyStorage, ChatModelConfig, SessionConfig
from agentscope.app.vin_platform import PlatformError
from agentscope.app.workforce.foundation._tables import durable_jobs


@pytest_asyncio.fixture(params=["redis", "sql"])
async def publication(authority, monkeypatch, request, tmp_path):
    monkeypatch.setenv("VIN_PLATFORM_ENABLED", "true")
    storage = make_storage() if request.param == "redis" else AsyncSQLAlchemyStorage("sqlite+aiosqlite:///" + str(tmp_path / "batch.db"))
    if request.param == "sql":
        await storage.__aenter__()
    storage.vin_platform_service = authority
    async with authority.engine.begin() as db:
        await db.run_sync(durable_jobs.create)
    model_config = ChatModelConfig(type="openai_credential", credential_id="fixture-managed", model="fixture", parameters={})
    await storage.upsert_session("alice", "workforce-builder", session_id="conversation",
        config=SessionConfig(workspace_id="builder", chat_model_config=model_config))
    agents = []
    model = _Model()
    for name in ("Fixture kỹ thuật", "Fixture giải thích"):
        spec = AgentSpec(name=name, description="Chỉ trả lời từ nội dung fixture", tests=[SpecTest(id=f"test-{index}", scenario=f"Fixture {index}",
            expected="Khóa van trước", safety_critical=index == 0) for index in range(5)])
        report = await run_spec_tests(spec=spec, model=model, judge_model=model, discovered={}, run_tool=AsyncMock())
        assert report["publishable"] and report["passed"] == 5
        agents.append(ProposedAgentView(name=name, objective=spec.description, system_prompt="Answer only fixture facts.", selected_tools=[],
            skill_name="", skill_markdown="", spec=spec.model_dump(mode="json"), evaluation={"model_report": report, "checks": {"fixture": True}}))
    proposal = ProposalView(conversation_id="conversation", proposal_id="proposal-1", revision=1, status="ready", assistant_message="Fixture proposal",
        agents=agents, chat_model_config=model_config, fixed_config={})
    await _persist_builder_turn(storage, "alice", "conversation", "Tạo hai agent fixture", proposal)
    chat = SimpleNamespace(_access=SimpleNamespace(), _message_bus=None, _channel_clients=None)
    manager = _WorkspaceManager()
    worker = PersonalJobWorker(storage, chat, manager)
    activate = AsyncMock(wraps=storage.activate_agents_batch)
    monkeypatch.setattr(storage, "activate_agents_batch", activate)
    yield SimpleNamespace(authority=authority, storage=storage, proposal=proposal, worker=worker, manager=manager,
        activate=activate, command={"conversation_id": "conversation", "proposal_id": "proposal-1", "expected_revision": 1})
    if request.param == "redis":
        await storage._client.aclose()
    else:
        await storage.__aexit__(None, None, None)


@pytest.mark.asyncio
async def test_batch_activates_together_and_replay_returns_same_agents(publication):
    p = publication
    queued = await batch.enqueue(p.storage, "alice", p.command)
    assert queued["status"] == "queued" and queued["agents"] == []
    assert (await batch.enqueue(p.storage, "alice", p.command))["job_id"] == queued["job_id"]
    await p.worker.run_one()
    job = await batch.find_job(p.storage, "alice", queued["job_id"])
    assert job.status == "succeeded" and job.result["phase"] == "published"
    p.activate.assert_awaited_once()
    agents = await p.storage.list_agents("alice")
    assert len(agents) == 2 and all(a.data.published_version == 1 and a.data.lifecycle_state == "published" for a in agents)
    assert (await batch.enqueue(p.storage, "alice", p.command))["agents"] == job.result["agents"]
    messages, _ = await p.storage.list_messages("alice", "conversation")
    assert _stored_proposal(messages).status == "published"
    with pytest.raises(PlatformError, match="PUBLICATION_NOT_FOUND"):
        await batch.find_job(p.storage, "bob", job.job_id)


@pytest.mark.asyncio
async def test_only_passed_publishes_the_passing_agents_and_keeps_the_rest(publication):
    p = publication
    proposal = p.proposal.model_copy(deep=True)
    proposal.agents[0].evaluation["passed"] = True
    proposal.agents[1].evaluation["passed"] = False
    proposal.status, proposal.revision = "blocked", 2
    await _persist_builder_turn(p.storage, "alice", "conversation", "Một agent còn trượt", proposal)
    command = {**p.command, "expected_revision": 2}
    with pytest.raises(PlatformError, match="PUBLICATION_NOT_READY"):
        await batch.enqueue(p.storage, "alice", command)
    queued = await batch.enqueue(p.storage, "alice", {**command, "only_passed": True})
    assert queued["total"] == 1
    await p.worker.run_one()
    job = await batch.find_job(p.storage, "alice", queued["job_id"])
    assert job.status == "succeeded" and [a["name"] for a in job.result["agents"]] == ["Fixture kỹ thuật"]
    agents = await p.storage.list_agents("alice")
    assert [a.data.name for a in agents if a.data.lifecycle_state == "published"] == ["Fixture kỹ thuật"]
    messages, _ = await p.storage.list_messages("alice", "conversation")
    kept = _stored_proposal(messages)
    assert kept.status == "blocked" and kept.proposal_id != "proposal-1" and kept.revision == 3
    assert [bool(item.reuse_agent_id) for item in kept.agents] == [True, False]


@pytest.mark.asyncio
async def test_stage_crash_repairs_without_duplicate_agents_or_partial_publication(publication, monkeypatch):
    p = publication
    original, calls = batch.apply_bindings, []
    async def fail_second(*args, **kwargs):
        calls.append(args[3].id)
        if len(calls) == 2:
            raise RuntimeError("fixture crash during second stage")
        return await original(*args, **kwargs)
    monkeypatch.setattr(batch, "apply_bindings", fail_second)
    first = await batch.enqueue(p.storage, "alice", p.command)
    await p.worker.run_one()
    broken = await batch.find_job(p.storage, "alice", first["job_id"])
    assert broken.status == "failed" and broken.result["cursor"] == 1
    assert all(a.data.lifecycle_state == "draft" and a.data.published_version == 0 for a in await p.storage.list_agents("alice"))
    p.activate.assert_not_awaited()
    monkeypatch.setattr(batch, "apply_bindings", original)
    repair = await batch.enqueue(p.storage, "alice", p.command, previous=broken)
    assert (await batch.enqueue(p.storage, "alice", p.command, previous=broken))["job_id"] == repair["job_id"]
    await p.worker.run_one()
    repaired = await batch.find_job(p.storage, "alice", repair["job_id"])
    assert repaired.status == "succeeded"
    agents = await p.storage.list_agents("alice")
    assert len(agents) == 2 and all(len(a.data.versions) == a.data.published_version == 1 for a in agents)


@pytest.mark.asyncio
async def test_crash_after_atomic_activation_reconciles_without_new_version(publication, monkeypatch):
    from agentscope.app.vin_platform._jobs import PersonalJobs
    p = publication
    checkpoint = PersonalJobs.checkpoint
    async def lose_receipt(jobs, job, worker_id, result):
        if result.get("phase") == "activated":
            raise RuntimeError("fixture process death after atomic activation")
        return await checkpoint(jobs, job, worker_id, result)
    monkeypatch.setattr(PersonalJobs, "checkpoint", lose_receipt)
    first = await batch.enqueue(p.storage, "alice", p.command)
    await p.worker.run_one()
    previous = await batch.find_job(p.storage, "alice", first["job_id"])
    assert previous.status == "failed" and previous.result["phase"] == "activating"
    assert all(a.data.published_version == 1 for a in await p.storage.list_agents("alice"))
    monkeypatch.setattr(PersonalJobs, "checkpoint", checkpoint)
    repair = await batch.enqueue(p.storage, "alice", p.command, previous=previous)
    await p.worker.run_one()
    assert (await batch.find_job(p.storage, "alice", repair["job_id"])).status == "succeeded"
    p.activate.assert_awaited_once()
    assert all(a.data.published_version == 1 for a in await p.storage.list_agents("alice"))


@pytest.mark.asyncio
async def test_conversation_guard_and_head_revision_reject_stale_publish(publication):
    p = publication
    queued = await batch.enqueue(p.storage, "alice", p.command)
    async with batch.builder_guard(p.storage, "alice", "conversation"):
        # A separate request cannot use the worker's context-local guard.
        import contextvars
        import asyncio
        with pytest.raises(HTTPException):
            await asyncio.create_task(batch.builder_guard(p.storage, "alice", "conversation").__aenter__(), context=contextvars.Context())
    newer = p.proposal.model_copy(deep=True)
    newer.revision = 2
    await _persist_builder_turn(p.storage, "alice", "conversation", "Đổi đề xuất", newer)
    await p.worker.run_one()
    job = await batch.find_job(p.storage, "alice", queued["job_id"])
    assert job.status == "failed" and job.error["code"] == "BUILDER_HEAD_CHANGED"
    p.activate.assert_not_awaited()


@pytest.mark.asyncio
async def test_revocation_after_queue_prevents_stage_and_activation(publication):
    p = publication
    await batch.enqueue(p.storage, "alice", p.command)
    from agentscope.app.vin_platform import _tables as t
    async with p.authority.engine.begin() as db:
        await db.execute(update(t.accounts).where(t.accounts.c.user_id == "alice").values(eligible=False, revision=2))
    assert not await p.worker.run_one()
    p.activate.assert_not_awaited()
    # Claim performs the server eligibility check, before any workspace IO.
    assert p.manager.workspaces == {}
