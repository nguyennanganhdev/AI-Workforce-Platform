# -*- coding: utf-8 -*-
"""Tool sync failures are stored as sentences the user can act on."""
from unittest import TestCase

import httpx

from agentscope.app._router._mcp import _sync_error


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
