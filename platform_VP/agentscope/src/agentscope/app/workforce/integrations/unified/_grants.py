"""Opt-in workflow grants exchanged by the backend, outside model context."""
from datetime import UTC, datetime
from urllib.parse import urlsplit, urlunsplit
from uuid import NAMESPACE_URL, UUID, uuid5

import httpx

from .....mcp import HttpMCPConfig, MCPClient


class WorkflowGrantUnavailable(ValueError):
    """The Domain no longer permits live access to this handover."""


async def scoped_client(client: MCPClient, config: dict, context: dict, workflow_id: str, tools: list[str]) -> MCPClient:
    """Clone the registered client and replace its bootstrap with a workflow bearer.

    Only a same-origin absolute path is accepted. Fail closed: an unavailable
    grant service must never silently authorize business tools with bootstrap.
    """
    if not isinstance(client.mcp_config, HttpMCPConfig):
        raise TypeError("Workflow grants require an HTTP MCP transport")
    base = urlsplit(client.mcp_config.url)
    path = str(config.get("path") or "")
    target = urlsplit(path)
    if not path.startswith("/") or path.startswith("//") or target.scheme or target.netloc or target.query or target.fragment:
        raise ValueError("Grant endpoint must be a same-origin absolute path")
    if base.scheme not in ("https", "http") or base.username or base.password or not tools:
        raise ValueError("Invalid grant transport")
    ticket = str(UUID(context["ticket_id"]))
    external_request = str(UUID(context["external_request_id"]))
    ttl = max(60, min(86400, int(config.get("ttl_seconds", 3600))))
    # A half-life bucket permits retries after a lost response and renews before expiry.
    bucket = int(datetime.now(UTC).timestamp()) // max(30, ttl // 2)
    request_id = str(uuid5(NAMESPACE_URL, f"mcp-grant:{workflow_id}:{client.name}:{ticket}:{sorted(tools)}:{ttl}:{bucket}"))
    url = urlunsplit((base.scheme, base.netloc, path, "", ""))
    async with httpx.AsyncClient(timeout=15, follow_redirects=False) as http:
        response = await http.post(url, headers=client.mcp_config.headers or {}, json={
            "ticket_id": ticket, "external_request_id": external_request, "workflow_id": workflow_id,
            "grant_request_id": request_id, "tools": sorted(set(tools)), "ttl_seconds": ttl,
        })
    # Never include an HTTP body, URL headers or credential in an exception/log.
    if response.status_code == 409:
        raise WorkflowGrantUnavailable("Live workflow MCP access is unavailable")
    if response.status_code != 200:
        raise ValueError(f"Workflow MCP grant refused (HTTP {response.status_code})")
    grant = response.json()
    token = grant.get("bearer_token")
    if (not isinstance(token, str) or not token or any(c.isspace() for c in token)
            or grant.get("ticket_id") != ticket or grant.get("workflow_id") != workflow_id
            or set(grant.get("tools") or []) != set(tools)
            or datetime.fromisoformat(grant["expires_at"]) <= datetime.now(UTC)):
        raise ValueError("Invalid workflow MCP grant response")
    clone = MCPClient.model_validate(client.model_dump(mode="json"))
    headers = {k: v for k, v in (clone.mcp_config.headers or {}).items() if k.lower() != "authorization"}
    clone.mcp_config.headers = {**headers, "Authorization": f"Bearer {token}"}
    return clone
