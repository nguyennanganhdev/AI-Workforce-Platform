# -*- coding: utf-8 -*-
"""Users run remote MCPs only; operator defaults and opted-in hosts may
run stdio."""
import os
from unittest import TestCase
from unittest.mock import patch

from agentscope.app._mcp_policy import (
    MCPPolicyError,
    check_mcp_allowed,
    mcp_allowed,
)
from agentscope.mcp import HttpMCPConfig, MCPClient, StdioMCPConfig


def _stdio(command: str = "npx", name: str = "pkg") -> MCPClient:
    return MCPClient(
        name=name,
        is_stateful=True,
        mcp_config=StdioMCPConfig(command=command, args=["-y", "thing"]),
    )


class MCPPolicyTest(TestCase):
    """The stdio rule and its two exceptions."""

    def setUp(self) -> None:
        patcher = patch.dict(os.environ, {"MCP_ALLOW_STDIO": ""})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_remote_mcp_is_allowed(self) -> None:
        client = MCPClient(
            name="remote",
            is_stateful=False,
            mcp_config=HttpMCPConfig(url="https://mcp.example/mcp"),
        )
        check_mcp_allowed(client)

    def test_user_stdio_is_refused(self) -> None:
        with self.assertRaises(MCPPolicyError):
            check_mcp_allowed(_stdio())

    def test_operator_default_still_runs(self) -> None:
        default = _stdio(name="playwright")
        self.assertTrue(mcp_allowed(_stdio(name="playwright"), [default]))

    def test_default_name_does_not_cover_another_command(self) -> None:
        default = _stdio(name="playwright")
        self.assertFalse(mcp_allowed(_stdio("sh", name="playwright"), [default]))

    def test_opt_in_allows_stdio(self) -> None:
        with patch.dict(os.environ, {"MCP_ALLOW_STDIO": "true"}):
            check_mcp_allowed(_stdio())
