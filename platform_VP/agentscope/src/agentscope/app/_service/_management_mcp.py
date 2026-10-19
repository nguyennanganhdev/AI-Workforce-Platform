"""Vinhomes test pack: the Domain's read-only management tools on a demo area.

The Domain ``/mcp`` endpoint only answers with a short-lived grant (15 min)
issued for a ``platform_management_bindings`` row. The pack's catalog MCP keeps
the Domain control-plane token server-side; each run asks for a fresh grant
for the one demo binding the operator configured, never one picked by the
model or the customer.

``VINHOMES_TEST_BINDING`` = ``<platform_tenant>/<platform_domain>/<platform_area>/<platform_user>``
"""
import os
from urllib.parse import urlsplit, urlunsplit

import httpx
from fastapi import HTTPException

from ...mcp import MCPClient

TOOL_PREFIX = "vh_management_"


def _binding():
    parts = os.getenv("VINHOMES_TEST_BINDING", "").strip().split("/")
    if len(parts) != 4 or not all(parts):
        raise HTTPException(409, "Gói thử Vinhomes chưa được cấu hình (VINHOMES_TEST_BINDING).")
    keys = ("platform_tenant", "platform_domain", "platform_area", "platform_user")
    return dict(zip(keys, parts))


async def manager_clients(storage, user_id, agent, clients):
    """Attach a fresh management grant to each Vinhomes MCP the agent's spec binds."""
    from ._catalog_resources import resolve_catalog_resource

    selected = {}
    for tool in (agent.data.spec or {}).get("tools", []):
        if tool.get("tool_name", "").startswith(TOOL_PREFIX):
            selected.setdefault(tool["mcp_id"], []).append(tool["tool_name"])
    if not selected:
        return clients
    binding = _binding()
    output = list(clients)
    for mcp_id, names in selected.items():
        # Catalog-granted (the pack's group) or owned; never another user's record.
        record = await resolve_catalog_resource(storage, user_id, "mcp", mcp_id, permission="execute")
        if not record or not record.enabled or record.client.mcp_config.type != "http_mcp":
            raise HTTPException(409, "Vinhomes connector unavailable")
        config = record.client.mcp_config
        parsed = urlsplit(config.url)
        if parsed.scheme not in {"http", "https"} or parsed.path.rstrip("/") != "/mcp":
            raise HTTPException(409, "Vinhomes connector must use the Domain /mcp endpoint")
        descriptors = {t["name"]: t for t in record.discovered_tools}
        if any(descriptors.get(name, {}).get("read_only") is not True for name in names):
            raise HTTPException(409, "Vinhomes tool catalog is stale or not read-only")
        prefix = "" if parsed.port == 8000 else "/api/business"
        endpoint = urlunsplit((parsed.scheme, parsed.netloc, prefix + "/platform/management-grants", "", ""))
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as http:
            response = await http.post(endpoint, headers=config.headers, json={**binding, "tools": names})
        if response.status_code != 200:
            raise HTTPException(409, "Domain từ chối cấp quyền cho gói thử Vinhomes; kiểm tra binding demo.")
        client = MCPClient.model_validate(record.client.model_dump(mode="json"))
        client.enable_tools = names
        client.disable_tools = None
        client.confirm_tools = None
        # A dedicated clone: the control-plane token never reaches a tool call.
        client.mcp_config.headers = {"Authorization": "Bearer " + response.json()["bearer_token"]}
        output = [c for c in output if c.name != client.name]
        output.append(client)
    return output
