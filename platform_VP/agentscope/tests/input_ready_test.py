"""Tests for the coordinator customer-input readiness gate."""

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from agentscope.app._tool._input_ready import InputReady
from agentscope.message import ToolResultState, UserMsg


class InputReadyTest(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.storage = SimpleNamespace(
            list_messages=AsyncMock(
                return_value=(
                    [
                        UserMsg(
                            "user",
                            "Toi di tu Ha Noi, gom 2 nguoi vao cuoi tuan nay.",
                        ),
                    ],
                    False,
                ),
            ),
        )
        self.tool = InputReady(
            storage=self.storage,
            message_bus=object(),
            workspace_manager=object(),
            user_id="user-1",
            session_id="worker-session",
            agent_id="planner",
            required_inputs=(
                {"key": "origin", "description": "Departure location"},
                {"key": "party_size", "description": "Number of people"},
            ),
        )
        self.tool._require_team = AsyncMock(return_value=object())

    @patch(
        "agentscope.app._tool._input_ready._resolve_team_leader",
        new_callable=AsyncMock,
    )
    async def test_accepts_exact_customer_evidence(self, resolve: AsyncMock) -> None:
        resolve.return_value = SimpleNamespace(session_id="leader-session")

        result = await self.tool(
            inputs={
                "origin": {"value": "Ha Noi", "evidence_quote": "tu Ha Noi"},
                "party_size": {"value": "2", "evidence_quote": "2 nguoi"},
            },
        )

        self.assertEqual(ToolResultState.SUCCESS, result.state)
        self.assertTrue(result.metadata["input_ready"])

    @patch(
        "agentscope.app._tool._input_ready._resolve_team_leader",
        new_callable=AsyncMock,
    )
    async def test_rejects_missing_customer_evidence(self, resolve: AsyncMock) -> None:
        resolve.return_value = SimpleNamespace(session_id="leader-session")

        result = await self.tool(
            inputs={
                "origin": {"value": "Ho Chi Minh", "evidence_quote": "Ho Chi Minh"},
                "party_size": {"value": "2", "evidence_quote": "2 nguoi"},
            },
        )

        self.assertEqual(ToolResultState.ERROR, result.state)
        self.assertIn("origin", result.content[0].text)
