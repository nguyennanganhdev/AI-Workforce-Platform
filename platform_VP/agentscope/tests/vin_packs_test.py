"""Library packs (PM 19/10): pack groups grant catalog resources; sample agents are copied."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from vin_fixtures import authority as authority  # noqa: F401
from agentscope.app._agent_spec import AgentSpec, SpecTest, spec_hash
from agentscope.app._service import _pack_agents
from agentscope.app._service._publish_gate import EVALUATOR, seal_report
from agentscope.app.storage import AgentData, AgentRecord
from agentscope.app.vin_platform._contracts import CatalogEntry, Pack, PlatformError
from agentscope.app.vin_platform._packs import get_pack, list_packs, pack_group, save_pack, set_installed
from agentscope.agent import ContextConfig, ReActConfig


async def _admin(authority):
    return await authority.context("admin")


async def _catalog_mcp(authority):
    return await authority.publish_catalog(await _admin(authority), CatalogEntry(
        kind="mcp", resource_id="travel-mcp", owner_id="admin", name="Travelling", tool_names=["search_flights"]))


@pytest.mark.asyncio
async def test_admin_saves_a_pack_and_its_resources_are_granted_to_the_pack_group(authority):
    admin = await _admin(authority)
    catalog_id = await _catalog_mcp(authority)
    pack = Pack(name="Travelling", catalog_ids=[catalog_id], template_agent_ids=["planner"])
    assert await save_pack(authority, admin, "travelling", pack) == 1
    assert await save_pack(authority, admin, "travelling", pack, expected_revision=1) == 2
    alice = await authority.context("alice")
    assert [entry["resource_id"] for entry in await authority.catalog(alice, "mcp", "view")] == []
    with pytest.raises(PlatformError, match="REVISION_CONFLICT"):
        await save_pack(authority, admin, "travelling", pack, expected_revision=1)
    with pytest.raises(PlatformError, match="CAPABILITY_DENIED"):
        await save_pack(authority, alice, "travelling", pack)
    with pytest.raises(PlatformError, match="INVALID_PACK_ID"):
        await save_pack(authority, admin, "Bad Id", pack)


@pytest.mark.asyncio
async def test_installing_joins_the_pack_group_and_removing_revokes_access(authority):
    admin = await _admin(authority)
    catalog_id = await _catalog_mcp(authority)
    await save_pack(authority, admin, "travelling", Pack(name="Travelling", catalog_ids=[catalog_id]))
    alice, bob = await authority.context("alice"), await authority.context("bob")
    assert [p.installed for p in await list_packs(authority, alice)] == [False]
    await set_installed(authority, alice, "travelling", True)
    await set_installed(authority, alice, "travelling", True)  # idempotent
    assert [p.installed for p in await list_packs(authority, alice)] == [True]
    assert [e["resource_id"] for e in await authority.catalog(alice, "mcp", "execute")] == ["travel-mcp"]
    assert await authority.catalog(bob, "mcp", "execute") == []
    await set_installed(authority, alice, "travelling", False)
    assert await authority.catalog(alice, "mcp", "execute") == []
    assert pack_group("travelling") == "pack:travelling"


@pytest.mark.asyncio
async def test_inactive_pack_cannot_be_installed(authority):
    admin = await _admin(authority)
    await save_pack(authority, admin, "old", Pack(name="Old", active=False))
    with pytest.raises(PlatformError, match="PACK_NOT_FOUND"):
        await get_pack(authority, await authority.context("alice"), "old")
    assert [p.id for p in await list_packs(authority, await authority.context("alice"))] == []


def _template(evaluated=True):
    spec = AgentSpec(name="Planner", tests=[SpecTest(id=f"t{n}", scenario=f"Q{n}", expected="ok",
                                                     safety_critical=n == 0) for n in range(5)])
    report = seal_report(spec, {"spec_hash": spec_hash(spec), "evaluator": EVALUATOR, "ran_at": "2026-10-19T00:00:00Z",
        "total": 5, "passed": 5, "pass_rate": 1.0, "errors": 0, "model_error": None,
        "results": [{"test_id": t.id, "passed": True, "model_evaluated": True, "judge": {"passed": True},
                     "checks": [], "error": None} for t in spec.tests]})
    return AgentRecord(id="planner", user_id="admin", data=AgentData(
        name="Planner", system_role="business", lifecycle_state="published", context_config=ContextConfig(),
        react_config=ReActConfig(), spec=spec.model_dump(mode="json"), evaluation=report if evaluated else {}))


@pytest.mark.asyncio
async def test_sample_agents_are_copied_published_once_and_withdrawn_on_remove(monkeypatch):
    agents = {("admin", "planner"): _template(), ("admin", "draft"): _template(evaluated=False)}
    sessions = {}

    async def get_agent(owner, ident):
        return agents.get((owner, ident))

    async def upsert_agent(owner, record):
        agents[(owner, record.id)] = record

    async def get_session(owner, agent, ident):
        return sessions.get((owner, agent, ident))

    async def upsert_session(owner, agent, *, session_id, config):
        sessions[(owner, agent, session_id)] = config

    storage = SimpleNamespace(get_agent=get_agent, upsert_agent=upsert_agent,
                              get_session=get_session, upsert_session=upsert_session)
    bindings = AsyncMock()
    monkeypatch.setattr(_pack_agents, "apply_bindings", bindings)
    first = await _pack_agents.install_templates(storage, object(), object(), "alice", "travelling", "admin",
                                                 ["planner", "draft", "missing"], None)
    ident = _pack_agents.copy_id("alice", "travelling", "planner")
    assert first == [ident]
    copy = agents[("alice", ident)]
    assert copy.data.lifecycle_state == "published" and copy.data.invite_config.invitable
    assert copy.data.evaluation == agents[("admin", "planner")].data.evaluation
    again = await _pack_agents.install_templates(storage, object(), object(), "alice", "travelling", "admin",
                                                 ["planner"], None)
    assert again == [ident] and bindings.await_count == 1
    await _pack_agents.withdraw_templates(storage, "alice", "travelling", ["planner"])
    assert agents[("alice", ident)].data.lifecycle_state == "withdrawn"
    assert not agents[("alice", ident)].data.invite_config.invitable
