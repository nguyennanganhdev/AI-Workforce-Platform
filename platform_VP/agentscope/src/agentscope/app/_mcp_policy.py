# -*- coding: utf-8 -*-
"""Which MCPs a user may run on this platform.

A stdio MCP is a process started on the server. Workspaces are local, so
that process runs inside the app container, as the app's user, next to
every secret the app holds. On a platform where anyone can sign up, a
user-chosen package or command must not run there. Users therefore get
remote (HTTP) MCPs only; the operator's own ``default_mcps`` still run.
``MCP_ALLOW_STDIO=true`` lifts the rule for a trusted, single-tenant
deployment.
"""
import os
from typing import Iterable

from ..mcp import MCPClient, StdioMCPConfig

STDIO_DISABLED = (
    "Platform chỉ chạy MCP kết nối từ xa (HTTP). MCP chạy bằng package "
    "(npx, uvx, docker) chưa được hỗ trợ vì nó sẽ chạy ngay trên máy chủ "
    "của platform."
)


class MCPPolicyError(ValueError):
    """Raised when a user tries to run an MCP the platform does not allow."""


def stdio_allowed() -> bool:
    """Whether this deployment lets users run stdio MCPs."""
    return os.getenv("MCP_ALLOW_STDIO", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def is_stdio(client: MCPClient) -> bool:
    """Whether ``client`` starts a local process."""
    return isinstance(getattr(client, "mcp_config", None), StdioMCPConfig)


def mcp_allowed(
    client: MCPClient,
    defaults: Iterable[MCPClient] = (),
) -> bool:
    """Whether ``client`` may run: remote, allowed stdio, or an operator
    default (matched on its whole config, so a user cannot borrow a
    default's name for another command)."""
    if not is_stdio(client) or stdio_allowed():
        return True
    return any(client.mcp_config == default.mcp_config for default in defaults)


def check_mcp_allowed(
    client: MCPClient,
    defaults: Iterable[MCPClient] = (),
) -> None:
    """Raise :class:`MCPPolicyError` unless ``client`` may run."""
    if not mcp_allowed(client, defaults):
        raise MCPPolicyError(STDIO_DISABLED)
