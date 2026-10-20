# -*- coding: utf-8 -*-
"""Tool sync failures are stored as sentences the user can act on."""
from unittest import IsolatedAsyncioTestCase, TestCase

import httpx

from agentscope.app._router._mcp import _sync_error, refresh_catalog
from agentscope.app.storage import MCPRecord
from agentscope.mcp import MCPClient, StdioMCPConfig


class SyncErrorTest(TestCase):
    """What the library shows when an MCP refuses or stalls."""

    def _status_error(self, code: int) -> httpx.HTTPStatusError:
        request = httpx.Request("POST", "https://mcp.example/mcp")
        response = httpx.Response(code, request=request)
        return httpx.HTTPStatusError("boom", request=request, response=response)

    def test_refused_key_asks_for_a_token(self) -> None:
        error = ExceptionGroup("task group", [self._status_error(401)])

        text = _sync_error(error, 20)

        self.assertIn("401", text)
        self.assertIn("API token", text)
        self.assertNotIn("mozilla", text)

    def test_timeout_names_the_limit(self) -> None:
        self.assertEqual(
            _sync_error(TimeoutError(), 20),
            "MCP không phản hồi trong 20 giây.",
        )

    def test_other_errors_keep_their_message(self) -> None:
        self.assertEqual(_sync_error(ValueError("bad url"), 20), "bad url")


class StdioRefreshTest(IsolatedAsyncioTestCase):
    """A stdio MCP has no timeout field and must be connected first."""

    async def test_missing_command_is_reported_not_raised(self) -> None:
        record = MCPRecord(
            user_id="u",
            client=MCPClient(
                name="markitdown",
                is_stateful=True,
                mcp_config=StdioMCPConfig(command="awp-no-such-command", args=["x"]),
            ),
        )

        ok = await refresh_catalog(record, timeout=10)

        self.assertFalse(ok)
        self.assertEqual(
            record.last_sync_error,
            "Server chưa cài `awp-no-such-command` nên chưa chạy được MCP này.",
        )
