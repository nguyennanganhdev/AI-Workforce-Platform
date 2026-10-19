"""Restored Builder contracts and publication safety, using in-process models."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from agentscope.app._router import _workforce_console as console
from agentscope.app._service import _agent_studio
from agentscope.app.storage import ChatModelConfig
from agentscope.credential import CredentialFactory
from agentscope.message import AssistantMsg
from tests.workforce.console.test_agent_studio_api import BASE, env


def test_removed_classifier_is_not_a_credential_or_builder_stage():
    types = {s["properties"]["type"]["const"] for s in CredentialFactory.list_schemas()}
    assert "typesafe_credential" not in types
    assert "classifier_status" not in console.ProposalView.model_fields
    assert "scope" not in console.ProposalView.model_fields
    assert not any("verification" in r.path for r in console.workforce_console_router.routes)


def test_old_classifier_proposals_cannot_be_published_but_history_is_preserved():
    payload = {"classifier_status": {"state": "active"}, "status": "ready"}
    message = AssistantMsg(name="builder", content="Saved conversation",
                           structured_output={"workforce_builder_proposal": payload})
    assert console._stored_proposal([message]) is None
    assert message.get_text_content() == "Saved conversation"
    assert message.structured_output["workforce_builder_proposal"] == payload


@pytest.mark.parametrize("binding_fails", [False, True])
def test_builder_stages_resources_before_claiming_or_publishing(env, monkeypatch, binding_fails):
    client, storage, _, _ = env
    agent = client.post(f"{BASE}/agents", json={"template_id": "resident_technical"}).json()
    report = client.post(f"{BASE}/agents/{agent['agent_id']}/tests/run").json()
    assert report["publishable"]
    original = storage.agents[agent["agent_id"]].model_copy(deep=True)
    proposal = console.ProposalView(
        conversation_id="builder-rollback", proposal_id="p", revision=1, status="ready",
        assistant_message="Reviewed", fixed_config={},
        chat_model_config=ChatModelConfig(type="openai_credential", credential_id="c", model="m", parameters={}),
        agents=[console.ProposedAgentView(
            name=agent["draft"]["name"], objective="Handle technical incidents",
            system_prompt="Handle technical incidents safely", selected_tools=[], skill_name="", skill_markdown="",
            spec=agent["draft"], evaluation={"checks": {"valid": True}, "model_report": report},
        )],
    )
    storage.get_session = AsyncMock(return_value=SimpleNamespace(id=proposal.conversation_id))
    storage.list_messages = AsyncMock(return_value=([
        AssistantMsg(name="builder", content="Reviewed", structured_output={
            "workforce_builder_proposal": proposal.model_dump(mode="json")}),
    ], None))
    storage.upsert_message = AsyncMock()
    storage.claim_builder_publish = AsyncMock(return_value=True)

    async def stage(*args, **kwargs):
        assert kwargs["stage"] is True
        assert all(a.data.lifecycle_state == "draft" for a in storage.agents.values())
        storage.claim_builder_publish.assert_not_awaited()
        if binding_fails:
            raise HTTPException(409, "offline: resource unavailable")

    monkeypatch.setattr(_agent_studio, "apply_bindings", stage)
    response = client.post("/workforce/console/builder/publish", json={
        "conversation_id": proposal.conversation_id, "proposal_id": "p", "expected_revision": 1,
    })
    assert response.status_code == (409 if binding_fails else 200), response.text
    assert storage.agents[original.id] == original
    published = [a for a in storage.agents.values() if a.data.lifecycle_state == "published"]
    if binding_fails:
        storage.claim_builder_publish.assert_not_awaited()
        assert published == []
    else:
        storage.claim_builder_publish.assert_awaited_once()
        assert len(published) == 1
        assert published[0].data.resource_workspace_id.startswith("published-")
