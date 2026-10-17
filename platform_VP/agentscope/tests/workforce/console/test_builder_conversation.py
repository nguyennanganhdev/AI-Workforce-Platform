"""Builder feedback is a conversation, not an implicit request to replace the plan."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from agentscope.app._router import _workforce_console as console
from agentscope.app.storage import ChatModelConfig
from agentscope.message import AssistantMsg


@pytest.mark.parametrize("status", ["needs_input", "ready"])
def test_discussion_answers_the_latest_message_without_replacing_the_reviewed_plan(status):
    import asyncio

    config = ChatModelConfig(type="openai_credential", credential_id="c", model="gpt-5.4", parameters={})
    previous = console.ProposalView(
        conversation_id="builder-1", status=status, proposal_id="proposal-1", revision=3,
        assistant_message="Initial outline", planned_agents=[console.PlannedAgentView(name="Technical", objective="Inspect leaks")],
        chat_model_config=config, fixed_config={},
    )
    message = AssistantMsg(name="builder", content=previous.assistant_message,
                           structured_output={"workforce_builder_proposal": previous.model_dump(mode="json")})
    reply = "I understand you want a team that reviews evidence before dispatching."
    outline = SimpleNamespace(kind="reply", assistant_message=reply, agents=[], clarification_question=None)
    persist = AsyncMock()
    with patch.multiple(console,
                        _builder_session=AsyncMock(return_value=SimpleNamespace(id="builder-1")),
                        _list_all_builder_messages=AsyncMock(return_value=[message]),
                        _catalog=AsyncMock(return_value=[]), _library=AsyncMock(return_value=({}, {})),
                        get_model=AsyncMock(), _prepare_builder_memory=AsyncMock(return_value="Full conversation"),
                        _outline=AsyncMock(return_value=(outline, 100, 100)),
                        _record_builder_prompt_measurement=AsyncMock(), _persist_builder_turn=persist):
        result = asyncio.run(console.prepare_builder(
            console.PrepareRequest(message="Do you understand my goal? Don't repeat the agent list.", chat_model_config=config),
            "u", object(), object(),
        ))
    assert result.assistant_message == reply
    assert result.planned_agents == previous.planned_agents
    assert (result.status, result.proposal_id, result.revision) == (status, "proposal-1", 3)
    assert result.clarification_question is None
    persist.assert_awaited_once()


def test_builder_schema_accepts_a_direct_reply_without_inventing_agents_or_a_question():
    result = console.BuilderOutline.model_validate({"kind": "reply", "assistant_message": "I understand your goal."})
    assert result.agents == []
    assert result.clarification_question is None


def test_compact_display_keeps_the_full_outline_in_model_context_and_raw_history():
    config = ChatModelConfig(type="openai_credential", credential_id="c", model="gpt-5.4", parameters={})
    text = "Mình đề xuất các agent như sau:\n1. Technical: Inspect leaks"
    proposal = console.ProposalView(conversation_id="b", status="needs_input", assistant_message=text,
                                   planned_agents=[console.PlannedAgentView(name="Technical", objective="Inspect leaks")],
                                   chat_model_config=config, fixed_config={})
    message = AssistantMsg(name="builder", content=text,
                           structured_output={"workforce_builder_proposal": proposal.model_dump(mode="json")})
    assert "Inspect leaks" not in console._builder_display_text(message)
    assert "Inspect leaks" in console._builder_transcript([message], "Explain the plan")
    assert message.get_text_content() == text
