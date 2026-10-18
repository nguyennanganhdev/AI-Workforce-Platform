"""Tests for the coordinator customer-input readiness gate."""

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from agentscope.app._tool._input_ready import InputReady
from agentscope.message import ToolResultState


class InputReadyTest(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.customer_source_id = "customer-message-1"
        self.storage = SimpleNamespace(
            get_team_shared_context=AsyncMock(
                return_value=SimpleNamespace(
                    state=SimpleNamespace(
                        active_task_id="task-1",
                        events=[
                            SimpleNamespace(
                                kind="customer_message",
                                task_id="task-1",
                                stale=False,
                                source_message_id=self.customer_source_id,
                            ),
                        ],
                    ),
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
        self.tool._require_team = AsyncMock(return_value=SimpleNamespace(id="team-1"))

    async def test_accepts_authoritative_customer_source(self) -> None:
        result = await self.tool(
            inputs={
                "origin": {
                    "value": "Ha Noi",
                    "source_message_id": self.customer_source_id,
                },
                "party_size": {
                    "value": "2",
                    "source_message_id": self.customer_source_id,
                },
            },
        )

        self.assertEqual(ToolResultState.SUCCESS, result.state)
        self.assertTrue(result.metadata["input_ready"])
        item_schema = self.tool.input_schema["properties"]["inputs"]["properties"]
        self.assertEqual(
            ["value", "source_message_id"],
            item_schema["origin"]["required"],
        )

    async def test_rejects_unknown_customer_source(self) -> None:
        result = await self.tool(
            inputs={
                "origin": {
                    "value": "Ho Chi Minh",
                    "source_message_id": "peer-message-1",
                },
                "party_size": {
                    "value": "2",
                    "source_message_id": self.customer_source_id,
                },
            },
        )

        self.assertEqual(ToolResultState.ERROR, result.state)
        self.assertIn("origin", result.content[0].text)
        self.assertIn("Do not ask the customer to repeat", result.content[0].text)
