"""Discovery includes both ticket-scoped tools and read-only management tools."""

import asyncio
import json
from types import SimpleNamespace

from vinhomes_api.platform_access import TOOLS as TICKET_TOOLS
from vinhomes_api.platform_management import TOOLS as MANAGEMENT_TOOLS
from vinhomes_api.platform_mcp import build


def test_complete_catalog_keeps_ticket_and_management_schemas_separate():
    tools = {tool.name: tool for tool in asyncio.run(build(SimpleNamespace()).list_tools())}
    assert set(tools) == set(TICKET_TOOLS) | set(MANAGEMENT_TOOLS)
    for name in MANAGEMENT_TOOLS:
        tool = tools[name]
        assert tool.annotations.readOnlyHint is True
        assert "ticket_id" not in tool.inputSchema["properties"]
        assert "client_reference" not in tool.inputSchema["properties"]
    assert all("ticket_id" in tools[name].inputSchema["required"] for name in TICKET_TOOLS)


if __name__ == "__main__":
    tools = {tool.name for tool in asyncio.run(build(SimpleNamespace()).list_tools())}
    print(json.dumps({"ticket_count": len(TICKET_TOOLS), "discovered_count": len(tools),
        "extra_over_legacy_ticket_expectation": sorted(tools - set(TICKET_TOOLS)),
        "management_tools": sorted(MANAGEMENT_TOOLS)}, indent=2))
