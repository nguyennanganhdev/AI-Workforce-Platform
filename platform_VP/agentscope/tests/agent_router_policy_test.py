"""Agent CRUD projections for server-owned Workforce policy."""

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from fastapi import HTTPException

from agentscope.agent import ContextConfig, ReActConfig
from agentscope.app._router._agent import list_agents, update_agent
from agentscope.app._router._schema import UpdateAgentRequest
from agentscope.app._service import AgentView
from agentscope.app._workforce_policy import WORKFORCE_LEADER_PROMPT
from agentscope.app.storage import AgentData, AgentRecord


def _leader(prompt: str) -> AgentRecord:
    return AgentRecord(
        id="leader-1",
        user_id="user-1",
        data=AgentData(
            name="Workforce Leader",
            system_prompt=prompt,
            system_role="leader",
            context_config=ContextConfig(),
            react_config=ReActConfig(),
        ),
    )


class AgentRouterPolicyTest(IsolatedAsyncioTestCase):
    async def test_list_projects_current_runtime_prompt_for_stale_leader(self) -> None:
        view = AgentView.model_validate(
            {**_leader("old prompt").model_dump(), "editable": True},
        )
        access = SimpleNamespace(list_resource=AsyncMock(return_value=[view]))

        response = await list_agents("user-1", access)

        self.assertEqual(WORKFORCE_LEADER_PROMPT, response.agents[0].data.system_prompt)

    async def test_update_cannot_restore_stale_leader_prompt(self) -> None:
        leader = _leader("old prompt")
        access = SimpleNamespace(
            resolve_for_edit=AsyncMock(return_value=("user-1", leader)),
        )
        storage = SimpleNamespace(upsert_agent=AsyncMock())

        with self.assertRaises(HTTPException) as error:
            await update_agent(
                "leader-1", UpdateAgentRequest(system_prompt="custom stale prompt"),
                "user-1", storage, access,
            )
        self.assertEqual(error.exception.status_code, 409)
        storage.upsert_agent.assert_not_awaited()
