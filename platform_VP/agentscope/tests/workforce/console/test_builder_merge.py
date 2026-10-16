"""The merged Builder keeps resource selection tied to evaluated versions."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from agentscope.app._router import _workforce_console as console
from agentscope.app._service import _agent_studio as studio
from agentscope.message import AssistantMsg
from tests.workforce.console.test_builder_resources import (
    KBS, TOOLS, TestBuilderResources as _ResourceTests, _Model, approved, generated, valid_report,
)
from tests.workforce.console.test_builder_reuse import existing_agent


@pytest.mark.asyncio
async def test_missing_generated_tests_cannot_become_publishable():
    payload = generated()
    for agent in payload["agents"]:
        agent["tests"] = []
    proposal = await _ResourceTests._prepare(
        _ResourceTests(), approved(), _Model(payload),
    )
    assert proposal.status == "blocked"
    assert all(not agent.evaluation["passed"] for agent in proposal.agents)
    assert all(agent.evaluation["publish_blocker"] for agent in proposal.agents)


@pytest.mark.asyncio
async def test_ready_flag_cannot_bypass_model_publication_evidence():
    proposal = await _ResourceTests._prepare(
        _ResourceTests(), approved(), _Model(generated()),
    )
    proposal.agents[0].evaluation.pop("model_report")
    storage = SimpleNamespace(
        get_session=AsyncMock(return_value=object()),
        list_messages=AsyncMock(return_value=([
            AssistantMsg("builder", "Ready", structured_output={
                "workforce_builder_proposal": proposal.model_dump(mode="json"),
            }),
        ], False)),
        claim_builder_publish=AsyncMock(return_value=True),
        upsert_agent=AsyncMock(),
    )
    with (
        patch.object(console, "_catalog", AsyncMock(return_value=TOOLS)),
        patch.object(console, "_knowledge_catalog", AsyncMock(return_value=KBS)),
        pytest.raises(console.HTTPException) as error,
    ):
        await console.publish_builder(
            console.PublishRequest(conversation_id="builder", proposal_id=proposal.proposal_id,
                                   expected_revision=proposal.revision),
            request=SimpleNamespace(), user_id="user", storage=storage,
            workspace_manager=object(), access=object(),
        )
    assert error.value.status_code == 409
    storage.claim_builder_publish.assert_not_awaited()
    storage.upsert_agent.assert_not_awaited()


@pytest.mark.asyncio
async def test_resource_settings_save_a_draft_and_invalidate_its_previous_evaluation():
    record = existing_agent()
    original = record.data.model_dump(mode="json")
    spec = console.AgentSpec.model_validate(record.data.spec)
    studio.set_draft(record, spec, author="manager")
    studio.record_test_run(record, valid_report(spec))
    storage = SimpleNamespace(
        get_agent=AsyncMock(return_value=record), upsert_agent=AsyncMock(),
        list_mcps=AsyncMock(return_value=[]),
    )
    workspace_manager = SimpleNamespace(get_workspace=AsyncMock())
    with (
        patch.object(console, "_catalog", AsyncMock(return_value=TOOLS)),
        patch.object(console, "_knowledge_catalog", AsyncMock(return_value=KBS)),
    ):
        response = await console.update_agent_tool_settings(
            record.id,
            console.UpdateAgentToolsRequest(selected_tool_ids=[], selected_knowledge_base_ids=[]),
            user_id="user", storage=storage, workspace_manager=workspace_manager, access=object(),
        )
    assert response.selected_tool_ids == response.selected_knowledge_base_ids == []
    assert record.data.draft_spec["tools"] == record.data.draft_spec["knowledge"] == []
    assert "last_test" not in record.data.draft_meta
    assert record.data.spec == original["spec"]
    assert record.data.tool_bindings == original["tool_bindings"]
    assert record.data.knowledge_base_ids == original["knowledge_base_ids"]
    assert record.data.evaluation == original["evaluation"]
    workspace_manager.get_workspace.assert_not_awaited()


def test_publication_and_pinned_versions_keep_their_own_tools_and_knowledge():
    record = existing_agent()
    original_spec = console.AgentSpec.model_validate(record.data.spec)
    first = studio.materialize(record, original_spec, author="manager", note="First",
                               evaluation=valid_report(original_spec))
    revised = original_spec.model_copy(deep=True)
    revised.tools = []
    revised.knowledge = []
    studio.materialize(record, revised, author="manager", note="Remove resources",
                       evaluation=valid_report(revised))
    assert record.data.execution_mode == "context_only"
    assert record.data.knowledge_base_ids == record.data.tool_bindings == []
    pinned = studio.pinned_view(record, first)
    assert pinned.data.execution_mode == "tool_backed"
    assert pinned.data.knowledge_base_ids == [kb.id for kb in KBS]
    assert {tool["id"] for tool in pinned.data.tool_bindings} == {TOOLS[0].id}


def test_unevaluated_existing_agent_is_not_eligible_for_reuse():
    record = existing_agent()
    record.data.evaluation = {"passed": True}
    assert not console._reusable_agent(record, "user", TOOLS, KBS)
