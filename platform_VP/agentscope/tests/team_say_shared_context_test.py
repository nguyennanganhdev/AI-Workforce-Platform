"""TeamSay persists shared output before delivering a handoff."""

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from agentscope.agent import ContextConfig, ReActConfig
from agentscope.app._manager import HandoffDispatcher
from agentscope.app._shared_context import SharedContextService
from agentscope.app._tool import TeamSay
from agentscope.app.message_bus import InMemoryMessageBus, MessageBusKeys
from agentscope.app.storage import (
    AgentData,
    AgentRecord,
    SessionConfig,
    SessionRecord,
    TeamData,
    TeamHandoffRecord,
    TeamMember,
    TeamRecord,
    TeamSharedContextRecord,
    TeamTurnRecord,
)


class _Storage:
    def __init__(self) -> None:
        self.agents = {
            "leader": AgentRecord(
                id="leader",
                user_id="u",
                data=AgentData(
                    name="Leader",
                    context_config=ContextConfig(),
                    react_config=ReActConfig(),
                ),
            ),
            "worker": AgentRecord(
                id="worker",
                user_id="u",
                source="team",
                data=AgentData(
                    name="Worker",
                    context_config=ContextConfig(),
                    react_config=ReActConfig(),
                ),
            ),
        }
        self.sessions = {
            "leader-session": SessionRecord(
                id="leader-session",
                user_id="u",
                agent_id="leader",
                team_id="ticket-1",
                config=SessionConfig(workspace_id="workspace"),
            ),
            "worker-session": SessionRecord(
                id="worker-session",
                user_id="u",
                agent_id="worker",
                team_id="ticket-1",
                config=SessionConfig(workspace_id="workspace"),
            ),
        }
        self.team = TeamRecord(
            id="ticket-1",
            user_id="u",
            session_id="leader-session",
            leader_agent_id="leader",
            data=TeamData(
                name="Trip",
                members=[
                    TeamMember(
                        owner_id="u",
                        agent_id="worker",
                        session_id="worker-session",
                        role="created",
                    ),
                ],
            ),
        )
        self.context: TeamSharedContextRecord | None = None
        self.turn: TeamTurnRecord | None = None
        self.handoffs: dict[str, TeamHandoffRecord] = {}

    async def get_session(self, _user: str, _agent: str, session: str):
        return self.sessions.get(session)

    async def get_team(self, _user: str, team: str):
        return self.team if team == self.team.id else None

    async def get_agent(self, _user: str, agent: str):
        return self.agents.get(agent)

    async def get_team_shared_context(self, _user: str, team: str):
        if self.context is None or self.context.team_id != team:
            return None
        return self.context.model_copy(deep=True)

    async def upsert_team_shared_context(
        self,
        _user: str,
        record: TeamSharedContextRecord,
    ):
        self.context = record.model_copy(deep=True)
        return record

    async def compare_and_swap_team_shared_context(
        self, _user: str, record: TeamSharedContextRecord, expected_revision: int
    ) -> bool:
        if (self.context.state.revision if self.context else 0) != expected_revision:
            return False
        self.context = record.model_copy(deep=True)
        return True

    async def get_team_turn(self, _user: str, _team: str):
        return self.turn.model_copy(deep=True) if self.turn else None

    async def upsert_team_turn(self, _user: str, record: TeamTurnRecord):
        self.turn = record.model_copy(deep=True)
        return record

    async def get_team_handoff(self, _user: str, record_id: str):
        value = self.handoffs.get(record_id)
        return value.model_copy(deep=True) if value else None

    async def upsert_team_handoff(self, _user: str, record: TeamHandoffRecord):
        self.handoffs[record.id] = record.model_copy(deep=True)
        return record

    async def list_outstanding_team_handoffs(self, **_kwargs):
        return [value.model_copy(deep=True) for value in self.handoffs.values()]


class TestTeamSaySharedContext(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.storage = _Storage()
        self.bus = InMemoryMessageBus()
        self.shared = SharedContextService(
            self.storage,  # type: ignore[arg-type]
            self.bus,
        )
        self.tool = TeamSay(
            storage=self.storage,  # type: ignore[arg-type]
            message_bus=self.bus,
            workspace_manager=object(),
            user_id="u",
            session_id="leader-session",
            agent_id="leader",
            shared_context_service=self.shared,
            role="leader",
        )

    def test_resolution_schema_follows_reply_ownership_without_changing_class(self):
        for role, owner in (("worker", False), ("worker", True), ("leader", False)):
            tool = TeamSay(
                storage=self.storage, message_bus=self.bus,
                workspace_manager=object(), user_id="u",
                session_id="worker-session", agent_id="worker",
                role=role, is_reply_owner=owner,
            )
            self.assertEqual("resolution" in tool.input_schema["properties"], owner)
        self.assertIn("resolution", self.tool.input_schema["properties"])
        self.assertIn("resolution", TeamSay.input_schema["properties"])

    async def test_shared_result_is_persisted_before_recipient_wakeup(self) -> None:
        result = await self.tool(
            content="Hotel A is available",
            to="Worker",
            context_mode="task",
            result_scope="shared",
        )

        self.assertNotEqual(result.state, "error")
        record = await self.storage.get_team_shared_context("u", "ticket-1")
        self.assertEqual(record.state.events[0].content, "Hotel A is available")
        self.assertEqual(record.state.items[0].kind, "output")
        directives = await self.shared.pending_directives("worker-session")
        self.assertEqual(directives[0].mode, "task")
        self.assertEqual(directives[0].task_id, record.state.active_task_id)
        handoff = next(
            h
            for h in self.storage.handoffs.values()
            if "collaboration_intent" not in h.payload
        )
        self.assertEqual(handoff.context_ref, directives[0].context_ref)
        self.assertEqual(handoff.context_revision, directives[0].context_revision)
        self.assertTrue(handoff.context_ref)
        inbox = await self.bus.queue_drain(
            MessageBusKeys.inbox("worker-session"),
            max_count=10,
        )
        self.assertEqual(len(inbox), 1)

    async def test_system_leader_result_is_not_semantically_validated(
        self,
    ):
        self.storage.agents["leader"].data.system_role = "leader"
        result = await self.tool(
            content="Technician arrives in 30 minutes", to="Worker", kind="result"
        )
        self.assertNotEqual(result.state, "error")
        self.assertTrue(self.storage.handoffs)
        record = self.storage.context
        self.assertEqual(
            "Technician arrives in 30 minutes",
            record.state.events[-1].content,
        )

    async def test_isolated_defaults_to_caller_scope(self) -> None:
        result = await self.tool(
            content="Independent calculation",
            to="Worker",
            context_mode="isolated",
        )

        self.assertNotEqual(result.state, "error")
        self.assertEqual(self.storage.context.state.events, [])
        self.assertEqual(self.storage.context.state.items, [])
        directives = await self.shared.pending_directives("worker-session")
        self.assertEqual(directives[0].mode, "isolated")

    async def test_retry_of_same_handoff_does_not_duplicate_shared_state(self) -> None:
        for _ in range(2):
            result = await self.tool(
                content="Stable result",
                to="Worker",
                idempotency_key="stable-handoff-1",
            )
            self.assertNotEqual(result.state, "error")

        record = await self.storage.get_team_shared_context("u", "ticket-1")
        self.assertEqual(len(record.state.events), 1)
        self.assertEqual(len(record.state.items), 1)
        # Task snapshot, collaboration reservation, then the immutable event.
        self.assertEqual(record.state.revision, 3)
        inbox = await self.bus.queue_drain(
            MessageBusKeys.inbox("worker-session"),
            max_count=10,
        )
        self.assertEqual(len(inbox), 1)

    async def test_delivered_handoff_is_recovered_after_redis_restart(self) -> None:
        result = await self.tool(
            content="Restart-safe generic handoff",
            to="Worker",
            idempotency_key="restart-handoff-1",
        )
        self.assertNotEqual(result.state, "error")
        await self.bus.queue_drain(
            MessageBusKeys.inbox("worker-session"),
            max_count=10,
        )

        restarted_bus = InMemoryMessageBus()
        dispatcher = HandoffDispatcher(
            restarted_bus,
            self.storage,  # type: ignore[arg-type]
        )
        await dispatcher._recover(include_delivered=True)
        await dispatcher._recover(include_delivered=True)

        recovered = await restarted_bus.queue_drain(
            MessageBusKeys.inbox("worker-session"),
            max_count=10,
        )
        self.assertEqual(1, len(recovered))

    async def test_intent_recovery_uses_primary_team_membership_storage(self):
        task_id = await self.shared.active_task_id("u", "ticket-1")
        record = TeamHandoffRecord(
            id="intent-record",
            user_id="u",
            team_id="ticket-1",
            handoff_id="intent:handoff-1",
            task_id=task_id,
            kind="result",
            source_agent_id="worker",
            source_session_id="worker-session",
            recipient_agent_id="worker",
            recipient_session_id="worker-session",
            idempotency_key="handoff-1",
            payload={
                "collaboration_intent": {
                    "role": "worker",
                    "customer_revision": 0,
                    "arguments": {
                        "content": "verified result",
                        "to": "Leader",
                        "kind": "result",
                        "task_id": task_id,
                    },
                },
            },
        )
        membership_storage = object()
        captured = {}

        class _RecoveredTeamSay:
            def __init__(self, *, storage, **_kwargs):
                captured["storage"] = storage

            async def __call__(self, **_kwargs):
                return SimpleNamespace(state="success", metadata={}, content=[])

        dispatcher = HandoffDispatcher(
            self.bus,
            self.storage,  # type: ignore[arg-type]
            team_storage=membership_storage,  # type: ignore[arg-type]
        )
        with patch(
            "agentscope.app._manager._handoff_dispatcher.TeamSay",
            _RecoveredTeamSay,
        ):
            await dispatcher._deliver(record)

        self.assertIs(captured["storage"], membership_storage)

    async def test_handoff_inherits_the_server_bound_owner_scope(self) -> None:
        await self.shared.bind_scope(
            "u",
            "ticket-1",
            tenant_id="tenant-1",
            domain_id="domain-1",
            area_id="area-1",
            manager_account_id="u",
            workflow_id="workflow-1",
        )

        await self.tool(
            content="Scoped handoff",
            to="Worker",
            idempotency_key="scoped-handoff-1",
        )

        record = next(iter(self.storage.handoffs.values()))
        self.assertEqual("tenant-1", record.tenant_id)
        self.assertEqual("domain-1", record.domain_id)
        self.assertEqual("area-1", record.area_id)
        self.assertEqual("u", record.manager_account_id)
        self.assertEqual("workflow-1", record.workflow_id)

    async def test_explicit_task_is_used_for_event_and_recipient(self) -> None:
        await self.shared.active_task_id(
            "u", "ticket-1", requested_task_id="hotel-task"
        )
        result = await self.tool(
            content="Only the hotel subtask needs this result",
            to="Worker",
            task_id="hotel-task",
        )

        self.assertNotEqual(result.state, "error")
        record = await self.storage.get_team_shared_context("u", "ticket-1")
        self.assertEqual(record.state.events[0].task_id, "hotel-task")
        directives = await self.shared.pending_directives("worker-session")
        self.assertEqual(directives[0].task_id, "hotel-task")
