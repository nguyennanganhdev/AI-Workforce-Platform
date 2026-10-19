"""Compatibility checks for Dong's Builder on the merged platform, offline."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from agentscope.app._router import _workforce_console as console
from agentscope.app.storage import AgentData, AgentRecord
from agentscope.message import AssistantMsg
from tests.workforce.console.test_builder_resources import CONFIG


def proposal_message(**overrides):
    item = console.ProposedAgentView(
        name="Planner", objective="Summarize supplied facts",
        execution_mode="context_only", system_prompt="Use only supplied facts.",
        selected_tools=[], skill_name="planner", skill_markdown="# Supplied facts",
        evaluation={"passed": True},
    )
    proposal = console.ProposalView(
        conversation_id="builder", proposal_id="proposal", revision=1,
        status="ready", assistant_message="Ready", agents=[item],
        chat_model_config=CONFIG, fixed_config={},
    ).model_dump(mode="json")
    proposal["agents"][0].update(overrides)
    return AssistantMsg("builder", "Ready", structured_output={"workforce_builder_proposal": proposal})


def storage_for(message, claimed=True):
    return SimpleNamespace(
        get_session=AsyncMock(return_value=object()),
        list_messages=AsyncMock(return_value=([message], False)),
        claim_builder_publish=AsyncMock(return_value=claimed),
        activate_agents_batch=AsyncMock(),
        upsert_agent=AsyncMock(), upsert_message=AsyncMock(),
    )


async def publish(storage, manager, access):
    return await console.publish_builder(
        console.PublishRequest(conversation_id="builder", proposal_id="proposal", expected_revision=1),
        user_id="u", storage=storage, workspace_manager=manager, access=access,
    )


@pytest.mark.asyncio
async def test_spec_proposals_remain_readable_but_cannot_publish_as_dong_proposals():
    message = proposal_message(spec={"name": "Old Studio proposal"})
    assert console._stored_proposal([message]).status == "blocked"
    storage = storage_for(message)
    with pytest.raises(HTTPException) as error:
        await publish(storage, object(), object())
    assert error.value.status_code == 409
    storage.claim_builder_publish.assert_not_awaited()
    storage.upsert_agent.assert_not_awaited()


def test_incompatible_old_proposal_keeps_history_without_crashing():
    payload = {"classifier_status": {"state": "active"}, "status": "ready"}
    message = AssistantMsg("builder", "Saved conversation", structured_output={"workforce_builder_proposal": payload})
    assert console._stored_proposal([message]) is None
    assert message.get_text_content() == "Saved conversation"
    assert message.structured_output["workforce_builder_proposal"] == payload


@pytest.mark.asyncio
async def test_old_async_publication_worker_rejects_the_restored_flow(monkeypatch):
    from agentscope.app._service import _publish_batch as batch
    from agentscope.app.vin_platform import PlatformError

    proposal = console._stored_proposal([proposal_message()])
    # An old queued job must fail before its AgentSpec-only materialization.
    storage = SimpleNamespace(get_session=AsyncMock(return_value=object()))
    monkeypatch.setattr(console, "_list_all_builder_messages", AsyncMock(return_value=[]))
    monkeypatch.setattr(console, "_stored_proposal", lambda _: proposal)
    with pytest.raises(PlatformError) as error:
        await batch.proposal_for(storage, "u", {"conversation_id": "builder", "proposal_id": "proposal", "expected_revision": 1})
    assert error.value.code == "BUILDER_FLOW_CHANGED"


@pytest.mark.asyncio
async def test_durable_claim_rejects_duplicate_before_creating_any_agent():
    storage = storage_for(proposal_message(), claimed=False)
    access = SimpleNamespace(list_resource=AsyncMock(return_value=[]))
    with pytest.raises(HTTPException) as error:
        await publish(storage, object(), access)
    assert error.value.status_code == 409
    storage.upsert_agent.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("skill_fails", [False, True])
async def test_new_agents_are_invitable_only_after_resources_are_installed(monkeypatch, skill_fails):
    storage = storage_for(proposal_message())
    snapshots = []

    async def save(_user, record):
        snapshots.append(record.model_copy(deep=True))

    storage.upsert_agent.side_effect = save
    async def activate(user, records):
        for record in records:
            await save(user, record)
    storage.activate_agents_batch.side_effect = activate
    session = SimpleNamespace(id="s", config=SimpleNamespace(workspace_id="w"))
    monkeypatch.setattr(console, "_primary_session", AsyncMock(return_value=session))
    workspace = SimpleNamespace(default_mcps=[], add_skill_archive=AsyncMock())
    if skill_fails:
        workspace.add_skill_archive.side_effect = RuntimeError("offline skill failure")
    manager = SimpleNamespace(get_workspace=AsyncMock(return_value=workspace))
    access = SimpleNamespace(list_resource=AsyncMock(return_value=[]))
    if skill_fails:
        with pytest.raises(RuntimeError, match="offline skill failure"):
            await publish(storage, manager, access)
        assert len(snapshots) == 1
        storage.activate_agents_batch.assert_not_awaited()
        storage.upsert_message.assert_not_awaited()
    else:
        result = await publish(storage, manager, access)
        assert len(result.agents) == 1
        assert len(snapshots) == 2
        storage.activate_agents_batch.assert_awaited_once()
        assert snapshots[-1].data.lifecycle_state == "published"
        assert snapshots[-1].data.invite_config.invitable
    assert snapshots[0].data.lifecycle_state == "draft"
    assert not snapshots[0].data.invite_config.invitable
    storage.claim_builder_publish.assert_awaited_once_with("u", "builder", "proposal")


@pytest.mark.asyncio
async def test_builder_tool_edit_cannot_change_a_versioned_studio_agent():
    record = AgentRecord(user_id="u", data=AgentData(
        name="Versioned", context_config=console._FIXED_CONTEXT,
        react_config=console._FIXED_REACT, execution_mode="context_only",
        spec={"name": "Versioned"},
    ))
    before = record.model_dump()
    storage = SimpleNamespace(get_agent=AsyncMock(return_value=record), upsert_agent=AsyncMock())
    with pytest.raises(HTTPException) as error:
        await console.update_agent_tool_settings(
            record.id, console.UpdateAgentToolsRequest(selected_tool_ids=[]),
            user_id="u", storage=storage, workspace_manager=object(), access=object(),
        )
    assert error.value.status_code == 409
    assert record.model_dump() == before
    storage.upsert_agent.assert_not_awaited()


@pytest.mark.asyncio
async def test_tool_settings_include_shared_catalog_mcps(monkeypatch):
    mcp = SimpleNamespace(id="shared", display_name="Shared", client=SimpleNamespace(name="shared"), enabled=True)
    monkeypatch.setattr(console, "_catalog", AsyncMock(return_value=[]))
    catalog = AsyncMock(return_value=[mcp])
    monkeypatch.setattr(console, "list_catalog_resources", catalog)
    record = SimpleNamespace(id="agent", data=SimpleNamespace(tool_bindings=[], knowledge_base_ids=[]))
    storage = object()
    view = await console._agent_tool_settings(
        storage, SimpleNamespace(list_resource=AsyncMock(return_value=[])), "u", record,
    )
    assert [group.mcp_id for group in view.mcps] == ["shared"]
    catalog.assert_awaited_once_with(storage, "u", "mcp")
