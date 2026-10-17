"""Agent eval on a partner's synthetic sandbox: fresh tickets, ticket-scoped grants.

The operator lists sandbox MCP endpoints in ``WORKFORCE_EVAL_SANDBOXES`` (JSON):

    [{"mcp_url": "http://host.docker.internal:8087/mcp",
      "fixture_path": "/api/business/platform/eval-fixtures",
      "grant_path": "/api/business/platform/mcp-grants", "ttl_seconds": 900}]

Only an MCP whose URL is listed there is a sandbox. For it, each eval case gets
its own fresh ticket and its hand-over, obtains a ticket-scoped bearer exactly
as the runtime does, and every tool of that MCP (reads and writes) runs for
real against the sandbox data. Any other MCP keeps the default behaviour:
server-classified reads only, everything else simulated.
"""

from __future__ import annotations

import json
import os
from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import httpx

from ...mcp import HttpMCPConfig, MCPClient
from ...message import TextBlock
from .._agent_spec import AgentSpec
from ._agent_eval import EvalToolError, tool_result_error

ENV = "WORKFORCE_EVAL_SANDBOXES"


def sandbox_configs() -> list[dict]:
    raw = os.getenv(ENV, "").strip()
    if not raw:
        return []
    value = json.loads(raw)
    if not isinstance(value, list):
        raise ValueError(f"{ENV} must be a JSON list")
    return [item for item in value if isinstance(item, dict) and item.get("mcp_url")]


def _same_origin(mcp_url: str, path: str) -> str:
    base, target = urlsplit(mcp_url), urlsplit(path)
    if not path.startswith("/") or path.startswith("//") or target.scheme or target.netloc:
        raise ValueError("Sandbox paths must be same-origin absolute paths")
    return urlunsplit((base.scheme, base.netloc, path, "", ""))


async def call_tool(client: MCPClient, name: str, arguments: dict, *, require_read_only: bool) -> str:
    """Call one MCP tool on an isolated client; a failed result raises EvalToolError."""
    try:
        if client.is_stateful:
            await client.connect()
        mcp_tool = await client.get_tool(name)
        # get_tool refreshes the provider descriptor on this isolated
        # client. Refuse revoked/unknown classification before invoking it.
        if require_read_only and getattr(mcp_tool, "is_read_only", False) is not True:
            raise RuntimeError("Sandbox tool classification changed or requires confirmation")
        result = await mcp_tool(**arguments)
        content = getattr(result, "content", result)
        if isinstance(content, list):
            output = "\n".join(
                block.text if isinstance(block, TextBlock) else json.dumps(
                    getattr(block, "model_dump", lambda **_: str(block))(mode="json"),
                    ensure_ascii=False,
                )
                for block in content
            )
        else:
            output = str(content)
        error = tool_result_error(output, failed=str(getattr(result, "state", "success")) in {"error", "denied", "interrupted"})
        if error:
            raise error
        return output
    finally:
        if client.is_stateful and client.is_connected:
            await client.close()


class EvalSandbox:
    """One eval run on one sandbox MCP: a ticket per case, a grant per ticket."""

    def __init__(self, record, config: dict, tools: list[str]) -> None:
        self.record, self.config, self.tools = record, config, sorted(set(tools))
        self.run_id = "eval-" + uuid4().hex[:24]
        self.tickets: list[dict] = []

    async def prepare(self, count: int) -> None:
        client = self.record.client
        url = _same_origin(client.mcp_config.url, str(self.config.get("fixture_path") or ""))
        async with httpx.AsyncClient(timeout=60, follow_redirects=False) as http:
            response = await http.post(url, headers=client.mcp_config.headers or {},
                                       json={"run_id": self.run_id, "count": count})
        # Never surface the response body or headers: they may carry credentials.
        if response.status_code != 200:
            raise EvalToolError(f"Sandbox không tạo được ticket mẫu (HTTP {response.status_code}).",
                                "SANDBOX_FIXTURE_UNAVAILABLE")
        tickets = response.json().get("tickets") or []
        if len(tickets) != count or not all(t.get("ticket_id") and t.get("handover_text") for t in tickets):
            raise EvalToolError("Sandbox trả về ticket mẫu không đầy đủ.", "SANDBOX_FIXTURE_UNAVAILABLE")
        self.tickets = tickets

    async def case(self, index: int) -> tuple[dict, Callable[[str, dict], Awaitable[str]]]:
        """The ticket for case ``index`` and a runner bound to its own bearer."""
        from ..workforce.integrations.unified._grants import scoped_client

        ticket = self.tickets[index]
        base = MCPClient.model_validate(self.record.client.model_dump(mode="json"))
        try:
            client = await scoped_client(
                base, {"path": self.config.get("grant_path"), "ttl_seconds": int(self.config.get("ttl_seconds", 900))},
                {"ticket_id": ticket["ticket_id"], "external_request_id": ticket["external_request_id"]},
                f"agent-eval:{self.run_id}", self.tools,
            )
        except Exception as exc:  # noqa: BLE001 - the grant service decides; never fall back to bootstrap
            raise EvalToolError(f"Sandbox từ chối cấp quyền theo ticket ({type(exc).__name__}).",
                                "SANDBOX_GRANT_REFUSED") from exc

        async def run(name: str, arguments: dict) -> str:
            if name not in self.tools:
                raise RuntimeError("Tool is not bound to the sandbox MCP")
            return await call_tool(MCPClient.model_validate(client.model_dump(mode="json")), name, arguments,
                                   require_read_only=False)

        return ticket, run


async def eval_sandbox(storage, user_id: str, spec: AgentSpec) -> EvalSandbox | None:
    """The sandbox for this spec's tools, when the operator configured one."""
    configs = {item["mcp_url"]: item for item in sandbox_configs()}
    if not configs:
        return None
    for mcp_id in dict.fromkeys(tool.mcp_id for tool in spec.tools):
        record = await storage.get_mcp(user_id, mcp_id)
        if record is None or not record.enabled or not isinstance(record.client.mcp_config, HttpMCPConfig):
            continue
        config = configs.get(record.client.mcp_config.url)
        if config:
            names = [t.tool_name for t in spec.tools if t.mcp_id == mcp_id and t.tool_id == f"{mcp_id}:{t.tool_name}"]
            return EvalSandbox(record, config, names) if names else None
    return None
