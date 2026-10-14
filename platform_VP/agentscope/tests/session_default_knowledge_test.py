"""Agent-level knowledge defaults for newly created sessions."""

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from agentscope.app._router._schema import CreateSessionRequest
from agentscope.app._router._session import create_session


class SessionDefaultKnowledgeTest(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.storage = SimpleNamespace(
            upsert_session=AsyncMock(return_value=SimpleNamespace(id="session-1")),
        )
        self.workspace_manager = SimpleNamespace(
            assign_workspace_id=AsyncMock(return_value="workspace-1"),
        )
        self.access = SimpleNamespace(
            resolve_agent=AsyncMock(
                return_value=SimpleNamespace(
                    data=SimpleNamespace(knowledge_base_ids=["kb-policy"]),
                ),
            ),
            get_resource=AsyncMock(return_value=SimpleNamespace(id="kb-policy")),
        )

    async def test_omitted_config_inherits_agent_defaults(self) -> None:
        await create_session(
            body=CreateSessionRequest(agent_id="agent-1"),
            user_id="user-1",
            storage=self.storage,
            workspace_manager=self.workspace_manager,
            access=self.access,
        )

        config = self.storage.upsert_session.await_args.kwargs["config"]
        self.assertEqual(
            config.knowledge_config.knowledge_base_ids,
            ["kb-policy"],
        )
        self.assertEqual(config.knowledge_config.parameters["mode"], "agentic")

    async def test_explicit_null_opts_out_of_agent_defaults(self) -> None:
        await create_session(
            body=CreateSessionRequest(
                agent_id="agent-1",
                knowledge_config=None,
            ),
            user_id="user-1",
            storage=self.storage,
            workspace_manager=self.workspace_manager,
            access=self.access,
        )

        config = self.storage.upsert_session.await_args.kwargs["config"]
        self.assertIsNone(config.knowledge_config)
