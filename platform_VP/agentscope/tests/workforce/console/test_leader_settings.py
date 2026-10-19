"""The platform user tunes the fixed Leader without replacing its policy."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from agentscope.agent import ContextConfig, ReActConfig
from agentscope.app._router import _workforce_console as console
from agentscope.app._workforce_policy import WORKFORCE_LEADER_PROMPT, with_leader_instructions
from agentscope.app.storage import AgentData, AgentRecord, ChatModelConfig, SessionConfig, SessionRecord


def _storage():
    agent = AgentRecord(id="leader", user_id="u", data=AgentData(
        name="Workforce Leader", system_role="leader",
        context_config=ContextConfig(), react_config=ReActConfig(),
    ))
    case = SessionRecord(id="case", user_id="u", agent_id="leader", config=SessionConfig(workspace_id="case"))
    case.state.middle_context["workflow_id"] = "wf"
    return agent, SimpleNamespace(
        list_agents=AsyncMock(return_value=[agent]),
        upsert_agent=AsyncMock(),
        list_sessions=AsyncMock(return_value=[case]),
        upsert_session=AsyncMock(),
    )


MANAGER = SimpleNamespace(get_workspace=AsyncMock(return_value=SimpleNamespace(default_mcps=[])))
MODEL = ChatModelConfig(type="test", credential_id="offline", model="offline", parameters={})


@pytest.mark.asyncio
async def test_settings_are_saved_and_survive_the_next_bootstrap():
    agent, storage = _storage()
    with patch.object(console, "_model_config", AsyncMock(return_value=MODEL)):
        saved = await console.update_leader_settings(
            console.LeaderSettingsUpdate(instructions="  Luôn trả lời bằng tiếng Việt.  ", max_iters=30),
            user_id="u", storage=storage, workspace_manager=MANAGER,
        )
        again = await console.get_leader_settings(user_id="u", storage=storage, workspace_manager=MANAGER)
    assert (saved.instructions, saved.max_iters) == ("Luôn trả lời bằng tiếng Việt.", 30)
    assert again == saved
    assert agent.data.system_prompt == console._LEADER_PROMPT
    assert agent.data.name == "Workforce Leader"
    storage.upsert_agent.assert_awaited()


def test_step_budget_and_length_are_bounded():
    with pytest.raises(ValidationError):
        console.LeaderSettingsUpdate(instructions="", max_iters=500)
    with pytest.raises(ValidationError):
        console.LeaderSettingsUpdate(instructions="x" * 4001, max_iters=50)


def test_instructions_follow_the_server_policy_and_never_replace_it():
    prompt = with_leader_instructions(WORKFORCE_LEADER_PROMPT, "Ưu tiên phiếu khẩn cấp.")
    assert prompt.startswith(WORKFORCE_LEADER_PROMPT.rstrip())
    assert prompt.endswith("Ưu tiên phiếu khẩn cấp.")
    assert "server-owned policy above, which always wins" in prompt
    assert with_leader_instructions(WORKFORCE_LEADER_PROMPT, "   ") == WORKFORCE_LEADER_PROMPT
