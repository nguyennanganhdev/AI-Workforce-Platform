"""New standalone Builder sessions inherit the agent's MCP allowlist."""

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, call

from fastapi import HTTPException

from agentscope.app._router._schema import CreateSessionRequest
from agentscope.app._router._session import create_session
from agentscope.mcp import HttpMCPConfig, MCPClient


class SessionDefaultMCPTest(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.client = MCPClient(
            name="hotel",
            is_stateful=False,
            mcp_config=HttpMCPConfig(url="https://example.test/mcp"),
        )
        self.agent = SimpleNamespace(
            source="user",
            data=SimpleNamespace(
                system_role="business",
                execution_mode="tool_backed",
                knowledge_base_ids=[],
                tool_bindings=[
                    {"mcp_id": "hotel-id", "tool_name": name}
                    for name in ["search", "availability", "search"]
                ],
            ),
        )
        self.workspace = SimpleNamespace(
            default_mcps=[SimpleNamespace(name="playwright"), self.client],
            remove_mcp=AsyncMock(),
            add_mcp=AsyncMock(),
        )
        self.storage = SimpleNamespace(
            get_mcp=AsyncMock(
                return_value=SimpleNamespace(enabled=True, client=self.client),
            ),
            upsert_session=AsyncMock(
                side_effect=[SimpleNamespace(id="session-1"), SimpleNamespace(id="session-2")],
            ),
        )
        self.manager = SimpleNamespace(
            assign_workspace_id=AsyncMock(return_value="workspace-1"),
            get_workspace=AsyncMock(return_value=self.workspace),
        )
        self.access = SimpleNamespace(resolve_agent=AsyncMock(return_value=self.agent))
        self.session_service = SimpleNamespace(delete_session=AsyncMock())

    async def create(self):
        return await create_session(
            body=CreateSessionRequest(agent_id="agent-1"),
            user_id="user-1",
            storage=self.storage,
            workspace_manager=self.manager,
            access=self.access,
            session_service=self.session_service,
        )

    async def test_equips_only_assigned_tools_and_replaces_defaults(self) -> None:
        response = await self.create()

        self.assertEqual(response.session_id, "session-1")
        self.storage.get_mcp.assert_awaited_once_with("user-1", "hotel-id")
        self.workspace.remove_mcp.assert_has_awaits([
            call("playwright", agent_id="agent-1", session_id="session-1"),
            call("hotel", agent_id="agent-1", session_id="session-1"),
        ])
        self.workspace.add_mcp.assert_awaited_once()
        args = self.workspace.add_mcp.await_args
        self.assertEqual(args.kwargs, {"agent_id": "agent-1", "session_id": "session-1"})
        client = args.args[0]
        self.assertEqual(client.name, "hotel")
        self.assertEqual(client.enable_tools, ["search", "availability"])
        self.assertIsNone(self.client.enable_tools)

    async def test_sessions_get_independent_clients(self) -> None:
        await self.create()
        await self.create()

        first, second = self.workspace.add_mcp.await_args_list
        self.assertIsNot(first.args[0], second.args[0])
        self.assertEqual(first.kwargs["session_id"], "session-1")
        self.assertEqual(second.kwargs["session_id"], "session-2")

    async def test_each_server_gets_its_own_tool_allowlist(self) -> None:
        self.agent.data.tool_bindings.append(
            {"mcp_id": "booking-id", "tool_name": "reserve"},
        )
        booking = self.client.model_copy(update={"name": "booking"}, deep=True)
        records = {
            "hotel-id": SimpleNamespace(enabled=True, client=self.client),
            "booking-id": SimpleNamespace(enabled=True, client=booking),
        }
        self.storage.get_mcp.side_effect = lambda _user_id, mcp_id: records[mcp_id]
        await self.create()

        clients = [args.args[0] for args in self.workspace.add_mcp.await_args_list]
        self.assertEqual(
            {client.name: client.enable_tools for client in clients},
            {"hotel": ["search", "availability"], "booking": ["reserve"]},
        )

    async def test_context_only_agent_does_not_inherit_default_mcps(self) -> None:
        self.agent.data.execution_mode = "context_only"
        self.agent.data.tool_bindings = []
        await self.create()

        self.storage.get_mcp.assert_not_awaited()
        self.assertEqual(self.workspace.remove_mcp.await_count, 2)
        self.workspace.add_mcp.assert_not_awaited()

    async def test_regular_agents_and_leader_keep_existing_behavior(self) -> None:
        for mode, role, source in [
            (None, "business", "user"),
            ("tool_backed", "leader", "user"),
            ("tool_backed", "business", "team"),
        ]:
            with self.subTest(mode=mode, role=role, source=source):
                self.agent.data.execution_mode = mode
                self.agent.data.system_role = role
                self.agent.source = source
                self.storage.upsert_session.side_effect = None
                self.storage.upsert_session.return_value = SimpleNamespace(id="session-1")
                await self.create()
                self.manager.get_workspace.assert_not_awaited()
                self.storage.get_mcp.assert_not_awaited()

    async def test_unavailable_mcp_is_rejected_before_creating_session(self) -> None:
        for record in [None, SimpleNamespace(enabled=False, client=self.client)]:
            with self.subTest(record=record):
                self.storage.get_mcp.return_value = record
                with self.assertRaises(HTTPException) as raised:
                    await self.create()
                self.assertEqual(raised.exception.status_code, 409)
                self.storage.upsert_session.assert_not_awaited()
                self.manager.get_workspace.assert_not_awaited()

    async def test_connection_failure_cleans_up_only_the_new_session(self) -> None:
        self.workspace.add_mcp.side_effect = RuntimeError("Cannot connect to hotel MCP")
        with self.assertRaises(HTTPException) as raised:
            await self.create()

        self.assertEqual(raised.exception.status_code, 502)
        self.assertIn("Cannot connect", raised.exception.detail)
        self.session_service.delete_session.assert_awaited_once_with(
            "user-1", "agent-1", "session-1",
        )
