"""The assembled prompt distinguishes resident cases, manager review and chat."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from agentscope.agent import ContextConfig, ReActConfig
from agentscope.app._service import ChatService
from agentscope.app.message_bus import InMemoryMessageBus
from agentscope.app.storage import AgentData, AgentRecord, ChatModelConfig, SessionConfig, SessionRecord, TeamData, TeamRecord
from agentscope.middleware import MiddlewareBase
from tests.service_chat_run_context_test import _Storage, _WorkspaceManager


@pytest.mark.asyncio
@pytest.mark.parametrize("middleware_key,expected", [(None, "platform_chat"), ("partner_case", "partner_api"), ("partner_case_member", "partner_api"), ("management_case", "management")])
async def test_runtime_uses_bound_case_audience(middleware_key, expected):
    record = AgentRecord(id="agent", user_id="u", data=AgentData(name="Leader", system_role="leader", context_config=ContextConfig(), react_config=ReActConfig()))
    session = SessionRecord(id="run", user_id="u", agent_id="agent", config=SessionConfig(workspace_id="run", chat_model_config=ChatModelConfig(type="test", credential_id="offline", model="offline", parameters={})))
    visible = session.model_copy(update={"id": "case"}, deep=True)
    if middleware_key == "management_case":
        session.state.middle_context.update(management_case_session_id="case", management_output_session_id="case", workflow_id="wf")
    storage = _Storage({"run": session, "case": visible}, {"agent": record}, TeamRecord(id="unused", user_id="u", session_id="case", data=TeamData(name="unused")))
    captured = []

    class Captured(BaseException):
        pass

    class Probe:
        def __init__(self, **kwargs):
            captured.append(kwargs["system_prompt"])
            raise Captured()

    class Extra(MiddlewareBase):
        async def get_middleware_key(self):
            return middleware_key

    class Model:
        context_size = 128000

        async def count_tokens(self, messages, tools=None):
            return 20

    service = ChatService(storage=storage, workspace_manager=_WorkspaceManager(), scheduler_manager=object(), background_task_manager=object(), message_bus=InMemoryMessageBus(), resource_access_service=SimpleNamespace(resolve_agent=AsyncMock(return_value=record)), custom_agent_cls=Probe, extra_agent_middlewares=AsyncMock(return_value=[Extra()] if middleware_key else []))
    with patch("agentscope.app._service._chat.get_toolkit", AsyncMock(return_value=object())), patch("agentscope.app._service._chat.get_model", AsyncMock(return_value=Model())):
        with pytest.raises(Captured):
            await service._run_impl("u", "run", "agent", None)
    assert f'"source": "{expected}"' in captured[0]
    if expected != "platform_chat":
        assert "This is not an external partner ticket" not in captured[0]
