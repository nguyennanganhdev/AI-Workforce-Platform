"""Dong's published agents and team sources survive the platform upgrade."""

import json
from unittest import IsolatedAsyncioTestCase

from agentscope.app._manager import BackgroundTaskManager, SchedulerManager
from agentscope.app._service import get_toolkit
from agentscope.app._service._agent_studio import ensure_spec
from agentscope.app._shared_context import (
    SharedContextConfig,
    SharedContextService,
)
from agentscope.app.message_bus import InMemoryMessageBus
from agentscope.app.storage import AgentRecord, TaskAssignment
from tests.service_toolkit_test import (
    _FakeWorkspace,
    _NoOpStorage,
    _NullBus,
    _StubTool,
    _make_access,
    _make_agent,
    _make_session,
    _tool_names,
)
from tests.team_shared_context_test import _MeasuredModel, _Storage
from tests.utils import FakeWorkspaceManager


class TestDongUpgrade(IsolatedAsyncioTestCase):
    def test_legacy_publication_keeps_knowledge_when_adopted(self):
        raw = _make_agent().model_dump(mode="json")
        raw["data"].update(
            knowledge_base_ids=["dong-kb"],
            execution_mode="context_only",
            lifecycle_state="published",
        )
        agent = AgentRecord.model_validate(raw)
        ensure_spec(agent)
        self.assertEqual(
            ["dong-kb"], [kb["kb_id"] for kb in agent.data.spec["knowledge"]]
        )
        reloaded = AgentRecord.model_validate_json(agent.model_dump_json())
        self.assertEqual(
            ["dong-kb"],
            [kb["kb_id"] for kb in reloaded.data.spec["knowledge"]],
        )

    async def toolkit(self, agent, team_id=None):
        storage, bus, manager = (
            _NoOpStorage(),
            _NullBus(),
            FakeWorkspaceManager(),
        )
        return await get_toolkit(
            storage=storage,
            workspace=_FakeWorkspace(tools=[_StubTool()]),
            workspace_manager=manager,
            scheduler_manager=SchedulerManager(
                storage=storage, message_bus=bus, workspace_manager=manager
            ),
            background_task_manager=BackgroundTaskManager(message_bus=bus),
            message_bus=bus,
            middlewares=[],
            user_id="u",
            agent_record=agent,
            session_record=_make_session(
                user_id="u",
                agent_id=agent.id,
                with_model=True,
                team_id=team_id,
            ),
            resource_access_service=_make_access(storage),
            shared_context_service=SharedContextService(storage, bus),
            team_role="worker" if team_id else None,
        )

    async def test_published_agent_without_mcp_has_no_coding_or_schedule_tools(
        self,
    ):
        agent = _make_agent()
        agent.data.lifecycle_state = "published"
        ensure_spec(agent)
        names = set(_tool_names(await self.toolkit(agent, "team")))
        self.assertTrue(
            names.isdisjoint(
                {"stub", "TaskCreate", "ScheduleCreate", "ToolStop"}
            ),
            names,
        )
        self.assertIn("TeamSay", names)

    async def test_first_leader_turn_can_read_the_team_it_creates(self):
        agent = _make_agent()
        agent.data.system_role = "leader"
        names = set(_tool_names(await self.toolkit(agent)))
        self.assertIn("TeamCreate", names)
        self.assertIn("SharedContextRead", names)

    async def test_long_assignment_keeps_readable_goal_and_acceptance_criteria(
        self,
    ):
        storage, bus = _Storage(), InMemoryMessageBus()
        service = SharedContextService(
            storage,
            bus,
            SharedContextConfig(
                packet_max_tokens=1500, history_budget_tokens=1000
            ),
        )
        task = await service.active_task_id("u", "ticket")
        await service.append_event(
            user_id="u",
            team_id="ticket",
            kind="customer_message",
            content="Compare options",
        )
        record = await storage.get_team_shared_context("u", "ticket")
        goal = "Preserve this requirement " * 400
        record.state.tasks[task].assignments["worker"] = TaskAssignment(
            goal=goal,
            expected_output="Complete comparison",
            done_when="Check all supplied constraints",
        )
        await storage.upsert_team_shared_context("u", record)
        model = _MeasuredModel()
        model.context_size = 100000
        text, tokens = await service.prepare_packet(
            model=model,
            user_id="u",
            team_id="ticket",
            allow_source_references=True,
        )
        self.assertLessEqual(tokens, 1500)
        packet = json.loads(text)
        section = packet["authoritative_state"]["tasks"]
        chunks, offset = [], 0
        while offset is not None:
            page = await service.read_packet_source(
                user_id="u",
                team_id="ticket",
                task_id=task,
                source_ref=section["source_ref"],
                offset=offset,
            )
            chunks.append(page["content"])
            offset = page["next_offset"]
        assignment = json.loads("".join(chunks))[0]["assignments"]["worker"]
        self.assertEqual(goal, assignment["goal"])
        self.assertEqual(
            "Check all supplied constraints", assignment["done_when"]
        )
