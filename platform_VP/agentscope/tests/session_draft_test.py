"""Chat drafts are saved together with their first user message."""

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from pydantic import ValidationError

from agentscope.app._router import _workforce_console as console
from agentscope.app._router._schema import CreateSessionRequest
from agentscope.app._router._session import create_session
from agentscope.app.storage import ChatModelConfig
from agentscope.message import AssistantMsg, UserMsg


class SessionDraftTest(IsolatedAsyncioTestCase):
    async def test_first_message_is_saved_before_creation_returns(self) -> None:
        message = UserMsg("user", "Tôi muốn đi du lịch")
        storage = SimpleNamespace(
            upsert_session=AsyncMock(return_value=SimpleNamespace(id="session-1")),
            upsert_message=AsyncMock(),
        )
        manager = SimpleNamespace(assign_workspace_id=AsyncMock())
        access = SimpleNamespace(resolve_agent=AsyncMock(return_value=SimpleNamespace(
            data=SimpleNamespace(knowledge_base_ids=[]),
        )))

        result = await create_session(
            CreateSessionRequest(
                agent_id="agent-1", workspace_id="draft-1", initial_message=message,
            ),
            user_id="user-1", storage=storage, workspace_manager=manager, access=access,
        )

        self.assertEqual(result.session_id, "session-1")
        storage.upsert_message.assert_awaited_once_with("user-1", "session-1", message)
        manager.assign_workspace_id.assert_not_awaited()
        self.assertEqual(storage.upsert_session.await_args.kwargs["config"].workspace_id, "draft-1")

    def test_empty_or_assistant_input_cannot_create_a_chat_draft(self) -> None:
        for message in [UserMsg("user", "  "), UserMsg("user", []), AssistantMsg("agent", "Hello")]:
            with self.subTest(message=message), self.assertRaises(ValidationError):
                CreateSessionRequest(agent_id="agent-1", initial_message=message)

    async def test_leader_bootstrap_does_not_save_an_empty_session(self) -> None:
        leader = SimpleNamespace(
            id="leader", source="user", data=SimpleNamespace(
                system_role="leader", name="Leader", system_prompt=console._LEADER_PROMPT,
            ),
        )
        storage = SimpleNamespace(
            list_agents=AsyncMock(return_value=[leader]),
            list_sessions=AsyncMock(return_value=[]),
            upsert_session=AsyncMock(),
        )
        manager = SimpleNamespace(get_workspace=AsyncMock())
        model = ChatModelConfig(type="openai", model="model", credential_id="credential", parameters={})
        with patch.object(console, "_model_config", AsyncMock(return_value=model)):
            result = await console.bootstrap_leader(
                user_id="user-1", storage=storage, workspace_manager=manager,
            )

        self.assertEqual(result.agent_id, "leader")
        self.assertIsNone(result.session_id)
        self.assertEqual(result.chat_model_config, model)
        storage.upsert_session.assert_not_awaited()
        manager.get_workspace.assert_not_awaited()

    async def test_new_leader_chat_saves_message_without_demo_mcps(self) -> None:
        message = UserMsg("user", "Hello")
        workspace = SimpleNamespace(
            default_mcps=[SimpleNamespace(name="demo")], remove_mcp=AsyncMock(),
        )
        storage = SimpleNamespace(
            upsert_session=AsyncMock(return_value=SimpleNamespace(id="session-1")),
            upsert_message=AsyncMock(),
        )
        access = SimpleNamespace(resolve_agent=AsyncMock(return_value=SimpleNamespace(
            data=SimpleNamespace(system_role="leader", knowledge_base_ids=[]),
        )))
        await create_session(
            CreateSessionRequest(agent_id="leader", workspace_id="draft-1", initial_message=message),
            user_id="user-1", storage=storage, access=access,
            workspace_manager=SimpleNamespace(get_workspace=AsyncMock(return_value=workspace)),
        )
        workspace.remove_mcp.assert_awaited_once_with("demo", agent_id="leader", session_id="session-1")
        storage.upsert_message.assert_awaited_once_with("user-1", "session-1", message)
