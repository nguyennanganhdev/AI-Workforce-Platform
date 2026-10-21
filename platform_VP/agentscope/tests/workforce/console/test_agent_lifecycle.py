"""Publishing works for agents made outside the Builder."""

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from fastapi import HTTPException

from agentscope.agent import ContextConfig, ReActConfig
from agentscope.app._router import _workforce_console as console
from agentscope.app.storage import AgentData, AgentRecord
from agentscope.app.storage._model._agent import InviteConfig


def _data(name: str, **kwargs) -> AgentData:
    return AgentData(name=name, context_config=ContextConfig(), react_config=ReActConfig(), **kwargs)


def _storage(record: AgentRecord) -> SimpleNamespace:
    return SimpleNamespace(
        get_agent=AsyncMock(return_value=record),
        upsert_agent=AsyncMock(),
    )


class TestAgentLifecycle(IsolatedAsyncioTestCase):
    async def test_manual_agent_publishes_with_its_invite_description(self):
        record = AgentRecord(user_id="u", data=_data(
            "Agent Khách sạn",
            invite_config=InviteConfig(invitable=False, invite_description="Tìm khách sạn."),
        ))
        view = await console.change_agent_lifecycle(
            record.id, console.LifecycleRequest(state="published"), "u", _storage(record),
        )
        self.assertEqual(view.lifecycle_state, "published")
        self.assertTrue(record.data.invite_config.invitable)
        self.assertEqual(record.data.invite_config.invite_description, "Tìm khách sạn.")

    async def test_publishing_without_any_description_is_a_clear_422(self):
        record = AgentRecord(user_id="u", data=_data("Agent trống"))
        with self.assertRaises(HTTPException) as error:
            await console.change_agent_lifecycle(
                record.id, console.LifecycleRequest(state="published"), "u", _storage(record),
            )
        self.assertEqual(error.exception.status_code, 422)

    async def test_withdrawing_without_description_still_works(self):
        record = AgentRecord(user_id="u", data=_data("Agent trống"))
        view = await console.change_agent_lifecycle(
            record.id, console.LifecycleRequest(state="draft"), "u", _storage(record),
        )
        self.assertEqual(view.lifecycle_state, "draft")
        self.assertFalse(record.data.invite_config.invitable)
