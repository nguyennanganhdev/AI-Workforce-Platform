"""MCP tools run without a confirmation card, even declared writes or consent tools."""

import asyncio

from mcp.types import Tool, ToolAnnotations

from agentscope.mcp import HttpMCPConfig, MCPClient
from agentscope.permission import PermissionBehavior
from agentscope.permission._mcp import mcp_tool_permission


def test_declared_write_and_spec_flag_run_without_confirmation() -> None:
    read = ToolAnnotations(readOnlyHint=True)
    write = ToolAnnotations(readOnlyHint=False, destructiveHint=False)

    assert mcp_tool_permission("update_status", read).behavior == PermissionBehavior.ALLOW
    assert mcp_tool_permission("update_status", write).behavior == PermissionBehavior.ALLOW
    assert mcp_tool_permission("update_status", None).behavior == PermissionBehavior.ALLOW
    assert (
        mcp_tool_permission("update_status", read, force_confirmation=True).behavior
        == PermissionBehavior.ALLOW
    )


def test_spec_consent_tools_are_not_read_only_but_still_run() -> None:
    client = MCPClient(
        name="demo",
        is_stateful=False,
        mcp_config=HttpMCPConfig(url="http://127.0.0.1:8765/mcp"),
        confirm_tools=["update_status"],
    )
    client._cached_tools = [
        Tool(name="update_status", inputSchema={"type": "object"}, annotations=ToolAnnotations(readOnlyHint=True)),
        Tool(name="lookup", inputSchema={"type": "object"}, annotations=ToolAnnotations(readOnlyHint=True)),
    ]

    async def decisions():
        guarded = await client.get_tool("update_status")
        plain = await client.get_tool("lookup")
        return (await guarded.check_permissions()).behavior, (await plain.check_permissions()).behavior, guarded.is_read_only

    guarded, plain, read_only = asyncio.run(decisions())
    assert guarded == PermissionBehavior.ALLOW
    assert plain == PermissionBehavior.ALLOW
    assert read_only is False
