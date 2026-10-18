"""Studio learning must consume core state without changing its bounded runtime."""

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from agentscope.app._agent_learning import ticket_succeeded
from agentscope.app._shared_context import SharedContextService
from agentscope.app.message_bus import InMemoryMessageBus
from agentscope.app.middleware import LeaderEvidenceMiddleware
from agentscope.app.storage import SharedTaskState, TeamMember, TeamSharedContextRecord
from agentscope.app.storage._model._team_context import CollaborationBranch
from agentscope.event import ReplyEndEvent, TextBlockEndEvent
from agentscope.state import AgentState
from agentscope.types import ReplyFinishedReason
from team_shared_context_test import _Storage


class CoreLearningIntegrationTests(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.storage = _Storage()
        self.bus = InMemoryMessageBus()
        self.shared = SharedContextService(self.storage, self.bus)
        self.record = TeamSharedContextRecord(user_id="u", team_id="ticket")
        self.task = SharedTaskState(id="task", objective="Verified repair", status="completed", latest_customer_revision=1)
        self.task.collaboration["worker"] = CollaborationBranch(customer_revision=1, status="completed")
        self.record.state.active_task_id = self.task.id
        self.record.state.tasks[self.task.id] = self.task
        self.members = [TeamMember(owner_id="u", agent_id="business", session_id="worker", role="invited")]
        await self.storage.upsert_team_shared_context("u", self.record)

    async def test_learning_snapshot_does_not_expand_the_core_packet(self):
        before = self.shared._packet_value(self.record, [], mode="task", task_id="task")
        self.assertTrue(await self.shared.prepare_learning_snapshot("u", "ticket", self.members))
        record = await self.storage.get_team_shared_context("u", "ticket")
        self.assertTrue(ticket_succeeded(record.state.tasks["task"]))
        after = self.shared._packet_value(record, [], mode="task", task_id="task")
        self.assertEqual(before["authoritative_state"]["tasks"], after["authoritative_state"]["tasks"])
        self.assertEqual(record.state.tasks["task"].collaboration, self.task.collaboration)

    async def test_new_customer_turn_invalidates_verified_learning_snapshot(self):
        await self.shared.prepare_learning_snapshot("u", "ticket", self.members)
        await self.shared.append_event(user_id="u", team_id="ticket", kind="customer_message", content="A new requirement")
        record = await self.storage.get_team_shared_context("u", "ticket")
        self.assertFalse(ticket_succeeded(record.state.tasks["task"]))

    async def test_running_or_stopped_work_never_becomes_learning_evidence(self):
        for status in ("running", "waiting_peer", "review", "stopped"):
            self.task.collaboration["worker"].status = status
            await self.storage.upsert_team_shared_context("u", self.record)
            self.assertFalse(await self.shared.prepare_learning_snapshot("u", "ticket", self.members), status)

    async def test_callback_runs_only_after_a_verified_complete_reply(self):
        self.storage.sessions[("u", "leader")] = SimpleNamespace(team_id="ticket")
        callback = AsyncMock()
        middleware = LeaderEvidenceMiddleware(self.storage, self.shared, "u", "leader-agent", "leader", on_verified_answer=callback)
        middleware._review = AsyncMock(return_value=[])
        middleware._question = AsyncMock(return_value=None)
        middleware._workers_running = AsyncMock(return_value=False)
        middleware._has_unseen_context = AsyncMock(return_value=False)
        middleware._seal_final_answer = AsyncMock(return_value=True)
        agent = SimpleNamespace(state=AgentState(), name="Leader")

        async def reply(**kwargs):
            yield TextBlockEndEvent(reply_id="reply", block_id="text", text="Verified useful result.")
            yield ReplyEndEvent(reply_id="reply", session_id="leader", finished_reason=ReplyFinishedReason.COMPLETED)

        events = [event async for event in middleware.on_reply(agent, {}, reply)]
        self.assertEqual(len(events), 2)
        callback.assert_awaited_once_with("ticket")
        callback.reset_mock()

        async def interrupted(**kwargs):
            yield ReplyEndEvent(reply_id="reply", session_id="leader", finished_reason=ReplyFinishedReason.INTERRUPTED)

        _ = [event async for event in middleware.on_reply(agent, {}, interrupted)]
        callback.assert_not_called()
