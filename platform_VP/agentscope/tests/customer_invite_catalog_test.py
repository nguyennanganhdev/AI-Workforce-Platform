"""Invited specialists use granted MCPs rather than looking in customer storage."""
from unittest.mock import AsyncMock, patch
from tests.service_team_tools_test import _AgentInviteTestBase
from agentscope.app._tool import AgentInvite
from agentscope.app.storage import MCPRecord
from agentscope.mcp import HttpMCPConfig, MCPClient
from fastapi import HTTPException


class TestGrantedMCPInvite(_AgentInviteTestBase):
    async def test_invite_resolves_shared_mcp_with_execute_permission(self):
        record = MCPRecord(user_id="catalog-owner", client=MCPClient(
            name="Traveling", is_stateful=False,
            mcp_config=HttpMCPConfig(url="http://unused.test/mcp")),
            discovered_tools=[{"name": "lookup", "read_only": True}])
        self.monday_agent.data.tool_bindings = [{"mcp_id": record.id, "tool_name": "lookup"}]
        await self.storage.upsert_agent(self.user_id, self.monday_agent)
        resolver = AsyncMock(return_value=record)
        with patch("agentscope.app._service._catalog_resources.resolve_catalog_resource", resolver):
            result = await AgentInvite(storage=self.storage, message_bus=self.bus,
                workspace_manager=self.workspace_manager, user_id=self.user_id,
                session_id=self.leader_session.id, agent_id=self.leader_agent.id,
                invitable_pool=[self.monday_agent])(
                    target=f"Monday@{self.monday_agent.id[:8]}", prompt="Look up options")
        self.assertNotEqual("error", result.state, result.content)
        resolver.assert_awaited_once_with(self.storage, self.user_id, "mcp", record.id, permission="execute")
        self.assertEqual(["lookup"], self.invite_workspace.add_mcp.call_args.args[0].enable_tools)

    async def test_denied_mcp_does_not_create_an_orphan_member_session(self):
        self.monday_agent.data.tool_bindings = [{"mcp_id": "revoked", "tool_name": "lookup"}]
        await self.storage.upsert_agent(self.user_id, self.monday_agent)
        before = await self.storage.list_sessions(self.user_id, self.monday_agent.id)
        with patch("agentscope.app._service._catalog_resources.resolve_catalog_resource",
                   AsyncMock(side_effect=HTTPException(404, "RESOURCE_NOT_FOUND"))):
            result = await AgentInvite(storage=self.storage, message_bus=self.bus,
                workspace_manager=self.workspace_manager, user_id=self.user_id,
                session_id=self.leader_session.id, agent_id=self.leader_agent.id,
                invitable_pool=[self.monday_agent])(
                    target=f"Monday@{self.monday_agent.id[:8]}", prompt="Look up options")
        self.assertEqual("error", result.state)
        after = await self.storage.list_sessions(self.user_id, self.monday_agent.id)
        self.assertEqual({s.id for s in before}, {s.id for s in after})
        self.invite_workspace.add_mcp.assert_not_awaited()

    async def test_binding_replaces_an_mcp_the_member_session_inherited(self):
        # A pack copy stages its MCP at agent level, so a fresh team session
        # already declares it; the binding's allowlisted spec must replace it
        # instead of failing every invite with "already exists".
        record = MCPRecord(user_id="catalog-owner", client=MCPClient(
            name="Traveling", is_stateful=False,
            mcp_config=HttpMCPConfig(url="http://unused.test/mcp")),
            discovered_tools=[{"name": "lookup", "read_only": True}])
        self.monday_agent.data.tool_bindings = [{"mcp_id": record.id, "tool_name": "lookup"}]
        await self.storage.upsert_agent(self.user_id, self.monday_agent)
        self.invite_workspace.add_mcp.side_effect = [
            ValueError("MCP 'Traveling' already exists for agent='x' session='y'."), None]
        with patch("agentscope.app._service._catalog_resources.resolve_catalog_resource",
                   AsyncMock(return_value=record)):
            result = await AgentInvite(storage=self.storage, message_bus=self.bus,
                workspace_manager=self.workspace_manager, user_id=self.user_id,
                session_id=self.leader_session.id, agent_id=self.leader_agent.id,
                invitable_pool=[self.monday_agent])(
                    target=f"Monday@{self.monday_agent.id[:8]}", prompt="Look up options")
        self.assertNotEqual("error", result.state, result.content)
        removed = [call.args[0] for call in self.invite_workspace.remove_mcp.await_args_list]
        self.assertIn("Traveling", removed)
        self.assertEqual(2, self.invite_workspace.add_mcp.await_count)
        self.assertEqual(["lookup"], self.invite_workspace.add_mcp.call_args.args[0].enable_tools)
