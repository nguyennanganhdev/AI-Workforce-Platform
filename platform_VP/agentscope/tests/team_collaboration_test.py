"""Generic bounded peer collaboration; no provider credentials or travel fixtures."""

import asyncio
import json
from dataclasses import replace
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from agentscope.app._manager import HandoffDispatcher
from agentscope.app._shared_context import (
    CollaborationStoppedError,
    SharedContextConcurrencyError,
    SharedContextService,
)
from agentscope.app._tool import TeamSay
from agentscope.app.message_bus import InMemoryMessageBus, MessageBusKeys
from agentscope.app.storage import TeamMember
from tests.team_say_shared_context_test import _Storage


class TestCollaboration(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.storage = _Storage()
        self.bus = InMemoryMessageBus()
        self.service = SharedContextService(self.storage, self.bus)
        self.storage.agents["peer"] = self.storage.agents["worker"].model_copy(
            deep=True, update={"id": "peer"}
        )
        self.storage.agents["peer"].data.name = "Peer"
        self.storage.sessions["peer-session"] = self.storage.sessions[
            "worker-session"
        ].model_copy(update={"id": "peer-session", "agent_id": "peer"})
        self.storage.team.data.members.append(
            TeamMember(
                owner_id="u", agent_id="peer", session_id="peer-session", role="created"
            )
        )
        self.task = await self.service.active_task_id("u", "ticket-1")
        await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            kind="customer_message",
            content="Compare available options and calculate the total",
            event_id="customer-1",
        )

    def tool(self, name):
        return TeamSay(
            storage=self.storage,
            message_bus=self.bus,
            workspace_manager=object(),
            user_id="u",
            session_id=f"{name}-session",
            agent_id=name,
            shared_context_service=self.service,
            role="leader" if name == "leader" else "worker",
        )

    def branch(self, name):
        return self.storage.context.state.tasks[self.task].collaboration[
            f"{name}-session"
        ]

    async def say(self, name, **kwargs):
        result = await self.tool(name)(**kwargs)
        self.assertNotEqual(result.state, "error", result.content)
        return result

    async def test_peer_question_sleeps_and_reply_wakes_requester_after_restart(self):
        question = await self.say(
            "worker",
            to="Peer",
            kind="question",
            content="Look up the available options",
        )
        self.assertEqual(
            "waiting_peer",
            await self.service.collaboration_pause("u", "ticket-1", "worker-session"),
        )
        self.assertIsNone(await self.service.pending_user_question("u", "ticket-1"))
        self.service = SharedContextService(self.storage, InMemoryMessageBus())
        self.bus = self.service._bus
        answer = await self.say(
            "peer",
            to="Worker",
            kind="answer",
            content="Two options were returned",
            in_reply_to=question.metadata["handoff_id"],
        )

        self.assertIsNone(
            await self.service.collaboration_pause("u", "ticket-1", "worker-session")
        )
        recipients = {
            h.recipient_session_id
            for h in self.storage.handoffs.values()
            if h.handoff_id == answer.metadata["handoff_id"]
        }
        self.assertEqual({"worker-session"}, recipients)
        self.assertEqual("review", self.branch("peer").status)

        event = next(
            item
            for item in self.storage.context.state.events
            if item.id == answer.metadata["handoff_id"]
        )
        self.assertEqual("answer", event.kind)

    async def test_peer_result_is_normalized_to_causal_answer(self):
        question = await self.say(
            "worker",
            to="Peer",
            kind="question",
            content="Find available flights",
        )

        answer = await self.say(
            "peer",
            to="Leader",
            kind="result",
            content="Flight VN123 is available",
        )

        self.assertEqual("answer", answer.metadata["kind"])
        recipients = {
            handoff.recipient_session_id
            for handoff in self.storage.handoffs.values()
            if handoff.handoff_id == answer.metadata["handoff_id"]
        }
        self.assertEqual({"worker-session"}, recipients)
        event = next(
            item
            for item in self.storage.context.state.events
            if item.id == answer.metadata["handoff_id"]
        )
        self.assertEqual(question.metadata["handoff_id"], event.in_reply_to)
        self.assertEqual(question.metadata["handoff_id"], event.thread_id)
        self.assertEqual(2, event.hop_count)

    async def test_result_cannot_be_used_to_start_peer_work(self):
        result = await self.tool("worker")(
            to="Peer",
            kind="result",
            content="Inspect the provider and report its status",
        )

        self.assertEqual("error", result.state)
        self.assertIn("send kind='question'", result.content[0].text)
        self.assertNotIn("peer-session", self.storage.context.state.tasks[
            self.task
        ].collaboration)

    async def test_dynamic_nested_answers_return_to_each_requester(self):
        self.storage.agents["specialist"] = self.storage.agents[
            "worker"
        ].model_copy(deep=True, update={"id": "specialist"})
        self.storage.agents["specialist"].data.name = "Specialist"
        self.storage.sessions["specialist-session"] = self.storage.sessions[
            "worker-session"
        ].model_copy(update={"id": "specialist-session", "agent_id": "specialist"})
        self.storage.team.data.members.append(
            TeamMember(
                owner_id="u",
                agent_id="specialist",
                session_id="specialist-session",
                role="created",
            )
        )

        root = await self.say(
            "worker",
            to="Peer",
            kind="question",
            content="Inspect the observed anomaly",
        )
        nested = await self.say(
            "peer",
            to="Specialist",
            kind="question",
            content="Check whether the related change is compatible",
        )

        premature = await self.tool("peer")(
            to="Leader",
            kind="result",
            content="The investigation is complete",
        )
        self.assertEqual("error", premature.state)
        self.assertIn(root.metadata["handoff_id"], premature.content[0].text)

        specialist_answer = await self.say(
            "specialist",
            to="Leader",
            kind="answer",
            content="The change is incompatible",
            in_reply_to=nested.metadata["handoff_id"],
        )
        specialist_recipients = {
            handoff.recipient_session_id
            for handoff in self.storage.handoffs.values()
            if handoff.handoff_id == specialist_answer.metadata["handoff_id"]
        }
        self.assertEqual({"peer-session"}, specialist_recipients)

        peer_answer = await self.say(
            "peer",
            to="Leader",
            kind="answer",
            content="The anomaly started after an incompatible change",
            in_reply_to=root.metadata["handoff_id"],
        )
        peer_recipients = {
            handoff.recipient_session_id
            for handoff in self.storage.handoffs.values()
            if handoff.handoff_id == peer_answer.metadata["handoff_id"]
        }
        self.assertEqual({"worker-session"}, peer_recipients)
        self.assertEqual({}, self.branch("worker").waiting_for)

        synthesis = await self.say(
            "worker",
            to="Leader",
            kind="result",
            content="The incompatible change caused the observed anomaly",
        )
        self.assertEqual("result", synthesis.metadata["kind"])

    async def test_reply_owner_also_sleeps_after_asking_peer(self):
        question = await self.say(
            "leader", to="Worker", kind="question", content="Look up available options",
        )
        self.assertEqual("waiting_peer", await self.service.collaboration_pause(
            "u", "ticket-1", "leader-session",
        ))
        await self.say("worker", to="Leader", kind="answer", content="Options returned",
                       in_reply_to=question.metadata["handoff_id"])
        self.assertFalse(self.branch("leader").waiting_for)

    async def test_terminal_peer_failure_releases_waiting_requester(self):
        await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            task_id=self.task,
            kind="external_event",
            content='{"verified_total":2720000}',
            source_session_id="peer-session",
        )
        await self.say(
            "worker",
            to="Peer",
            kind="question",
            content="Calculate the total from verified values",
        )

        released = await self.service.stop_failed_branch(
            "u",
            "ticket-1",
            "peer-session",
            "provider rate limited",
        )

        self.assertEqual(("worker-session",), released)
        self.assertEqual("stopped", self.branch("peer").status)
        self.assertEqual("running", self.branch("worker").status)
        self.assertEqual({}, self.branch("worker").waiting_for)
        self.assertEqual(
            ('{"verified_total":2720000}',),
            await self.service.current_tool_evidence_for_session(
                "u",
                "ticket-1",
                "peer-session",
            ),
        )

    async def test_outbound_assignment_is_not_semantically_validated(self):
        receipt = await self.service.coordinate_handoff(
            user_id="u",
            team_id="ticket-1",
            task_id=self.task,
            sender="worker-session",
            recipients=("peer-session",),
            owner="leader-session",
            handoff_id="unchecked-constraints",
            kind="question",
            content=(
                "Search flights from Hà Nội for 1 người with a "
                "500.000 VND category budget"
            ),
        )
        self.assertEqual("waiting_peer", receipt["status"])

    async def test_worker_handoff_is_normalized_to_causal_peer_question(self):
        request = await self.say(
            "worker",
            to="Peer",
            kind="handoff",
            content="Handle the remaining specialist lookup",
        )

        self.assertEqual("question", request.metadata["kind"])
        self.assertEqual("waiting_peer", self.branch("worker").status)
        self.assertEqual("running", self.branch("peer").status)
        pending = await self.service.collaboration_review(
            "u", "ticket-1", "leader-session"
        )
        self.assertIn("peer-session", pending)

    async def test_peer_answer_releases_only_its_linked_waiter(self):
        first = await self.say(
            "worker", to="Peer", kind="question", content="Provide the price"
        )
        second = await self.say(
            "leader", to="Peer", kind="question", content="Provide availability"
        )
        self.assertEqual(1, len(self.branch("worker").waiting_for))
        self.assertEqual(1, len(self.branch("leader").waiting_for))

        answer = await self.say(
            "peer",
            to="Worker",
            kind="answer",
            content="The price is 1,500,000 VND",
            in_reply_to=first.metadata["handoff_id"],
        )

        self.assertEqual({}, self.branch("worker").waiting_for)
        self.assertEqual("running", self.branch("worker").status)
        self.assertEqual(
            {second.metadata["handoff_id"]: "peer-session"},
            self.branch("leader").waiting_for,
        )
        self.assertEqual(
            (answer.metadata["handoff_id"],),
            self.branch("worker").evidence_event_ids,
        )

        leader_answer = await self.say(
            "peer",
            to="Leader",
            kind="answer",
            content="The option is available",
            in_reply_to=second.metadata["handoff_id"],
        )
        self.assertEqual({}, self.branch("leader").waiting_for)
        recipients = {
            handoff.recipient_session_id
            for handoff in self.storage.handoffs.values()
            if handoff.handoff_id == leader_answer.metadata["handoff_id"]
        }
        self.assertEqual({"leader-session"}, recipients)

    async def test_ambiguous_peer_result_requires_exact_reply_id(self):
        await self.say(
            "worker", to="Peer", kind="question", content="Provide the price"
        )
        await self.say(
            "leader", to="Peer", kind="question", content="Provide availability"
        )

        result = await self.tool("peer")(
            to="Leader",
            kind="result",
            content="The requested details are ready",
        )

        self.assertEqual("error", result.state)
        self.assertIn("multiple peer questions", result.content[0].text)
        self.assertEqual(1, len(self.branch("worker").waiting_for))
        self.assertEqual(1, len(self.branch("leader").waiting_for))

    async def test_peer_evidence_is_attached_to_coordinator_synthesis(self):
        question = await self.say(
            "worker", to="Peer", kind="question", content="Provide verified data"
        )
        await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            task_id=self.task,
            kind="external_event",
            content="Verified provider data",
            event_id="peer-tool-result",
            source_session_id="peer-session",
        )
        peer = await self.say(
            "peer",
            to="Worker",
            kind="answer",
            content="Provider returned option A",
            in_reply_to=question.metadata["handoff_id"],
        )
        synthesis = await self.say(
            "worker",
            to="Leader",
            kind="result",
            content="Option A is the recommended synthesis",
        )

        event = next(
            item
            for item in self.storage.context.state.events
            if item.id == synthesis.metadata["handoff_id"]
        )
        self.assertEqual((peer.metadata["handoff_id"],), event.reference_event_ids)
        self.assertEqual(
            [],
            await self.service.collaboration_review(
                "u", "ticket-1", "leader-session"
            ),
        )
        self.assertEqual("completed", self.branch("worker").status)

    async def test_worker_question_is_registered_for_the_reply_owner(self):
        await self.say(
            "worker",
            to="Leader",
            kind="requires_user_input",
            question_key="missing:choice",
            content="Which option do you choose?",
        )
        self.assertEqual(
            "Which option do you choose?",
            await self.service.pending_user_question("u", "ticket-1"),
        )
        self.assertEqual("leader", self.storage.turn.mode)
        self.assertEqual("leader-session", self.storage.turn.reply_owner_session_id)
        self.assertEqual(
            "requires_user_input", self.storage.context.state.events[-1].kind
        )
        recipients = {
            handoff.recipient_session_id
            for handoff in self.storage.handoffs.values()
            if handoff.kind == "requires_user_input"
            and not handoff.handoff_id.startswith("intent:")
        }
        self.assertEqual({"leader-session"}, recipients)

        second = await self.tool("worker")(
            to="Leader",
            kind="requires_user_input",
            question_key="missing:date",
            content="Which date?",
        )
        self.assertEqual("error", second.state)
        self.assertEqual(1, len(self.storage.turn.pending_question_ids))

    async def test_internal_specialist_never_takes_customer_reply_ownership(self):
        question = await self.say(
            "worker",
            to="null",
            kind="requires_user_input",
            content="Which account should I inspect?",
        )
        self.assertEqual("requires_user_input", question.metadata["kind"])
        self.assertEqual("leader", self.storage.turn.mode)
        self.assertEqual("leader-session", self.storage.turn.reply_owner_session_id)
        self.assertEqual(
            "Which account should I inspect?",
            await self.service.pending_user_question("u", "ticket-1"),
        )

    async def test_misdirected_customer_question_is_forced_to_reply_owner(self):
        question = await self.say(
            "worker",
            to="Peer",
            kind="requires_user_input",
            content="Which city are you departing from?",
        )

        self.assertTrue(question.metadata["customer_question_registered"])
        self.assertEqual("Leader", question.metadata["effective_to"])
        recipients = {
            handoff.recipient_session_id
            for handoff in self.storage.handoffs.values()
            if handoff.handoff_id == question.metadata["handoff_id"]
        }
        self.assertEqual({"leader-session"}, recipients)

    async def test_nested_customer_input_need_returns_to_requester_then_leader(self):
        request = await self.say(
            "worker",
            to="Peer",
            kind="question",
            content="Find the available flights",
        )
        nested = await self.say(
            "peer",
            to="Leader",
            kind="requires_user_input",
            content="Which travel date should I use?",
        )

        self.assertEqual("answer", nested.metadata["kind"])
        recipients = {
            handoff.recipient_session_id
            for handoff in self.storage.handoffs.values()
            if handoff.handoff_id == nested.metadata["handoff_id"]
        }
        self.assertEqual({"worker-session"}, recipients)
        event = next(
            item
            for item in self.storage.context.state.events
            if item.id == nested.metadata["handoff_id"]
        )
        self.assertEqual(request.metadata["handoff_id"], event.in_reply_to)
        self.assertEqual(
            "CUSTOMER_INPUT_REQUIRED: Which travel date should I use?",
            event.content,
        )
        self.assertIsNone(
            await self.service.pending_user_question("u", "ticket-1"),
        )
        self.assertIsNone(
            await self.service.collaboration_pause(
                "u", "ticket-1", "worker-session"
            ),
        )

        grouped = await self.say(
            "worker",
            to="Leader",
            kind="requires_user_input",
            content="Which travel date should I use?",
        )
        self.assertTrue(grouped.metadata["customer_question_registered"])
        self.assertEqual("Leader", grouped.metadata["effective_to"])
        self.assertEqual(
            "Which travel date should I use?",
            await self.service.pending_user_question("u", "ticket-1"),
        )
        self.assertEqual("leader", self.storage.turn.mode)
        self.assertEqual("leader-session", self.storage.turn.reply_owner_session_id)

    async def test_planner_waits_for_all_peers_before_grouping_customer_input(self):
        self.storage.agents["specialist"] = self.storage.agents[
            "worker"
        ].model_copy(deep=True, update={"id": "specialist"})
        self.storage.agents["specialist"].data.name = "Specialist"
        self.storage.sessions["specialist-session"] = self.storage.sessions[
            "worker-session"
        ].model_copy(update={"id": "specialist-session", "agent_id": "specialist"})
        self.storage.team.data.members.append(
            TeamMember(
                owner_id="u",
                agent_id="specialist",
                session_id="specialist-session",
                role="created",
            )
        )

        await self.say(
            "worker",
            to="Peer",
            kind="question",
            content="Find available flights",
        )
        await self.say(
            "worker",
            to="Specialist",
            kind="question",
            content="Find suitable restaurants",
        )

        flight_need = await self.say(
            "peer",
            to="Leader",
            kind="requires_user_input",
            content="Which cabin class should I search?",
        )
        self.assertEqual("answer", flight_need.metadata["kind"])
        self.assertEqual("Worker", flight_need.metadata["effective_to"])
        self.assertEqual("waiting_peer", self.branch("worker").status)

        premature = await self.tool("worker")(
            to="Leader",
            kind="requires_user_input",
            content="Which cabin class should I search?",
        )
        self.assertEqual("error", premature.state)
        self.assertIn("wait for all direct peer responses", premature.content[0].text)
        self.assertIsNone(
            await self.service.pending_user_question("u", "ticket-1"),
        )

        restaurant_result = await self.say(
            "specialist",
            to="Leader",
            kind="result",
            content="Three suitable restaurants are available",
        )
        self.assertEqual("answer", restaurant_result.metadata["kind"])
        self.assertEqual("Worker", restaurant_result.metadata["effective_to"])
        self.assertIsNone(
            await self.service.collaboration_pause(
                "u", "ticket-1", "worker-session"
            ),
        )

        grouped = await self.say(
            "worker",
            to="Leader",
            kind="requires_user_input",
            content="Which cabin class should I search?",
        )
        self.assertTrue(grouped.metadata["customer_question_registered"])
        self.assertEqual("Leader", grouped.metadata["effective_to"])

    async def test_nested_worker_cannot_question_or_conflict_past_requester(self):
        request = await self.say(
            "worker",
            to="Peer",
            kind="question",
            content="Find available flights",
        )

        ask_back = await self.say(
            "peer",
            to="Leader",
            kind="question",
            content="Which airport should I use?",
        )
        self.assertEqual("Worker", ask_back.metadata["effective_to"])
        ask_recipients = {
            handoff.recipient_session_id
            for handoff in self.storage.handoffs.values()
            if handoff.handoff_id == ask_back.metadata["handoff_id"]
        }
        self.assertEqual({"worker-session"}, ask_recipients)

        await self.say(
            "worker",
            to="Peer",
            kind="answer",
            content="Use Nội Bài airport",
            in_reply_to=ask_back.metadata["handoff_id"],
        )
        conflict = await self.say(
            "peer",
            to="Leader",
            kind="conflict",
            content="Two providers disagree on availability",
            in_reply_to=request.metadata["handoff_id"],
        )
        self.assertEqual("answer", conflict.metadata["kind"])
        self.assertEqual("Worker", conflict.metadata["effective_to"])
        conflict_event = next(
            item
            for item in self.storage.context.state.events
            if item.id == conflict.metadata["handoff_id"]
        )
        self.assertEqual(
            "PEER_CONFLICT: Two providers disagree on availability",
            conflict_event.content,
        )
        conflict_recipients = {
            handoff.recipient_session_id
            for handoff in self.storage.handoffs.values()
            if handoff.handoff_id == conflict.metadata["handoff_id"]
        }
        self.assertEqual({"worker-session"}, conflict_recipients)

    async def test_fixed_workforce_leader_cannot_ask_customer_question(self):
        self.storage.agents["leader"].data.system_role = "leader"
        result = await self.tool("leader")(
            kind="requires_user_input",
            question_key="missing:anything",
            content="What is missing?",
        )
        self.assertEqual("error", result.state)
        self.assertIn("registered by a responsible worker", result.content[0].text)

    async def test_failed_worker_question_preserves_leader_ownership(self):
        with patch.object(
            self.service,
            "append_event",
            side_effect=RuntimeError("write failed"),
        ):
            result = await self.tool("worker")(
                kind="requires_user_input",
                question_key="missing:account",
                content="Which account should I inspect?",
            )

        self.assertEqual("error", result.state)
        self.assertEqual("leader", self.storage.turn.mode)
        self.assertEqual("leader-session", self.storage.turn.reply_owner_session_id)
        self.assertEqual((), self.storage.turn.pending_question_ids)

    async def test_peer_can_ask_back_then_both_dependencies_settle(self):
        first = await self.say(
            "worker", to="Peer", kind="question", content="Need your data"
        )
        back = await self.say(
            "peer", to="Worker", kind="question", content="Which scope applies?"
        )
        self.assertEqual("waiting_peer", self.branch("peer").status)
        self.assertEqual("running", self.branch("worker").status)
        self.assertEqual(1, len(self.branch("worker").waiting_for))

        await self.say(
            "worker",
            to="Peer",
            kind="answer",
            content="Use the current customer scope",
            in_reply_to=back.metadata["handoff_id"],
        )
        self.assertEqual("waiting_peer", self.branch("worker").status)
        self.assertEqual("running", self.branch("peer").status)

        await self.say(
            "peer",
            to="Worker",
            kind="answer",
            content="The requested data is ready",
            in_reply_to=first.metadata["handoff_id"],
        )
        self.assertEqual("review", self.branch("peer").status)
        self.assertEqual("running", self.branch("worker").status)
        self.assertEqual({}, self.branch("worker").waiting_for)

    async def test_exchange_limit_cannot_be_bypassed_with_new_thread_or_key(self):
        self.service.config = replace(
            self.service.config, collaboration_max_exchanges=2
        )
        for n in range(3):
            result = await self.say(
                "worker",
                to="Leader",
                kind="progress",
                content=f"Update {n}",
                idempotency_key=f"key-{n}",
            )
        self.assertEqual("error", result.metadata["kind"])
        self.assertEqual("stopped", self.branch("worker").status)
        self.assertEqual("running", self.storage.context.state.tasks[self.task].status)

    async def test_same_message_is_suppressed_even_with_new_keys(self):
        for _ in range(2):
            await self.say(
                "worker",
                to="Leader",
                kind="progress",
                content="Still checking",
                idempotency_key="same",
            )
        self.assertEqual(1, self.branch("worker").exchanges)
        duplicates = []
        for key in ("another", "third"):
            duplicates.append(await self.say(
                "worker",
                to="Leader",
                kind="progress",
                content="Still checking",
                idempotency_key=key,
            ))
        self.assertEqual(1, self.branch("worker").exchanges)
        self.assertEqual("running", self.branch("worker").status)
        self.assertTrue(all(result.metadata["duplicate"] for result in duplicates))

    async def test_future_promise_is_progress_not_completion_evidence(self):
        report = await self.say(
            "worker",
            to="Leader",
            kind="result",
            content="Đang tra cứu dữ liệu và sẽ cập nhật khi có kết quả.",
        )
        self.assertEqual("progress", report.metadata["kind"])
        completed, errors, verified, waiting = (
            await self.service.team_evidence_status(
                "u",
                "ticket-1",
                leader_session_id="leader-session",
            )
        )
        self.assertEqual((0, 0, 0, False), (completed, errors, verified, waiting))
        self.assertEqual([], await self.bus.dequeue_wakeups(max_count=10))

    async def test_planner_promise_does_not_finish_its_assignment(self):
        report = await self.say(
            "worker", to="Leader", kind="result",
            content="Tôi sẽ lên lịch trình sơ bộ và phối hợp lấy giá từng dịch vụ.",
        )
        self.assertEqual("progress", report.metadata["kind"])
        self.assertEqual("running", self.branch("worker").status)

    async def test_leader_cannot_contact_worker_after_terminal_result(self):
        await self.say("worker", to="Leader", kind="result", content="Option available")
        blocked = await self.tool("leader")(
            to="Worker",
            kind="handoff",
            content="Please confirm this result again",
            resolution="complete",
        )
        self.assertEqual("error", blocked.state)
        self.assertEqual(
            "terminal_report_already_delivered",
            blocked.metadata["reason"],
        )
        self.assertEqual("completed", self.branch("worker").status)
        self.assertEqual("running", self.storage.context.state.tasks[self.task].status)

        # A new customer message starts a new bounded cycle and makes the
        # worker available again.
        await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            kind="customer_message",
            content="Please compare another option",
            event_id="customer-2",
        )
        self.assertIsNone(
            await self.service.collaboration_pause("u", "ticket-1", "worker-session")
        )
        await self.say("worker", to="Leader", kind="progress", content="New comparison")
        self.assertEqual(1, self.branch("worker").exchanges)
        self.assertEqual(self.task, self.storage.context.state.active_task_id)

    async def test_final_answer_seals_one_revision_and_follow_up_reopens_it(self):
        await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            task_id=self.task,
            kind="external_event",
            content="Verified current result",
            event_id="seal-tool-result",
            source_session_id="worker-session",
        )
        await self.say(
            "worker", to="Leader", kind="result", content="Verified current result"
        )
        self.assertEqual(
            [],
            await self.service.collaboration_review(
                "u", "ticket-1", "leader-session"
            ),
        )
        revision = await self.service.latest_event_revision(
            "u", "ticket-1", self.task
        )
        self.assertFalse(
            await self.service.seal_final_answer(
                "u",
                "ticket-1",
                "leader-session",
                expected_event_revision=revision - 1,
            )
        )
        self.assertTrue(
            await self.service.seal_final_answer(
                "u",
                "ticket-1",
                "leader-session",
                expected_event_revision=revision,
            )
        )
        self.assertEqual(
            "completed", self.storage.context.state.tasks[self.task].status
        )
        await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            task_id=self.task,
            kind="customer_reply",
            content="Final synthesized answer",
            event_id="sealed-customer-reply",
            source_session_id="leader-session",
        )

        blocked = await self.tool("worker")(
            to="Peer", kind="question", content="Late extra work"
        )
        self.assertEqual("error", blocked.state)
        await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            kind="customer_message",
            content="Please handle one more requirement",
            event_id="customer-after-seal",
        )
        self.assertEqual("running", self.storage.context.state.tasks[self.task].status)
        await self.say(
            "worker", to="Peer", kind="question", content="Handle the new requirement"
        )

    async def test_customer_answer_returns_to_requester_before_finalization(self):
        question = await self.say(
            "worker",
            to="Leader",
            kind="requires_user_input",
            content="Which account should I inspect?",
            question_key="missing:account",
        )
        answer = await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            task_id=self.task,
            kind="customer_message",
            content="Inspect account A.",
            event_id="customer-account-answer",
            in_reply_to=question.metadata["handoff_id"],
        )
        self.assertEqual(question.metadata["handoff_id"], answer.in_reply_to)
        self.assertFalse(
            await self.service.seal_final_answer(
                "u",
                "ticket-1",
                "leader-session",
                expected_event_revision=answer.revision,
            )
        )

        routed = await self.say(
            "leader",
            to="Peer",
            kind="answer",
            content="The customer selected account A.",
            in_reply_to=question.metadata["handoff_id"],
        )
        recipients = {
            handoff.recipient_session_id
            for handoff in self.storage.handoffs.values()
            if handoff.handoff_id == routed.metadata["handoff_id"]
        }
        self.assertEqual({"worker-session"}, recipients)
        self.assertEqual("running", self.branch("worker").status)
        await self.say(
            "worker",
            to="Leader",
            kind="result",
            content="Account A was inspected and the plan is complete.",
        )
        self.assertEqual(
            [],
            await self.service.collaboration_review(
                "u", "ticket-1", "leader-session"
            ),
        )
        revision = await self.service.latest_event_revision(
            "u", "ticket-1", self.task
        )
        self.assertTrue(
            await self.service.seal_final_answer(
                "u",
                "ticket-1",
                "leader-session",
                expected_event_revision=revision,
            )
        )

    async def test_review_auto_completes_any_delivered_result(self):
        result = await self.say(
            "worker", to="Leader", kind="result", content="Option available"
        )
        self.assertEqual("review", self.branch("worker").status)
        self.assertEqual(
            [],
            await self.service.collaboration_review(
                "u", "ticket-1", "leader-session"
            ),
        )
        self.assertEqual("completed", self.branch("worker").status)
        self.assertIn("accepted", self.branch("worker").reason)
        self.assertEqual(result.metadata["kind"], "result")

    async def test_review_accepts_result_without_tool_source(self):
        await self.say(
            "worker", to="Leader", kind="result", content="Planner proposal"
        )

        self.assertEqual(
            [],
            await self.service.collaboration_review(
                "u", "ticket-1", "leader-session"
            ),
        )
        self.assertEqual("completed", self.branch("worker").status)

    async def test_review_accepts_supported_context_only_planning_result(self):
        self.storage.agents["worker"].data.execution_mode = "context_only"
        await self.say(
            "worker",
            to="Leader",
            kind="result",
            content="Use a two-step plan based on the current customer constraints.",
        )

        self.assertEqual(
            [],
            await self.service.collaboration_review(
                "u", "ticket-1", "leader-session"
            ),
        )
        self.assertEqual("completed", self.branch("worker").status)
        self.assertIn("accepted", self.branch("worker").reason)

    async def test_delivered_worker_error_stops_branch_without_blocking_leader(self):
        report = await self.say(
            "worker",
            to="Leader",
            kind="error",
            content="Required provider data is unavailable",
        )
        self.assertEqual("review", self.branch("worker").status)

        self.assertEqual(
            [],
            await self.service.collaboration_review(
                "u", "ticket-1", "leader-session"
            ),
        )
        self.assertEqual("stopped", self.branch("worker").status)
        completed, errors, _verified, waiting = (
            await self.service.team_evidence_status(
                "u",
                "ticket-1",
                leader_session_id="leader-session",
            )
        )
        self.assertEqual((1, 1, False), (completed, errors, waiting))
        self.assertEqual("error", report.metadata["kind"])

    async def test_verification_is_bounded_and_worker_resolution_is_ignored(self):
        delivered = await self.tool("worker")(
            to="Peer", kind="handoff", content="Done", resolution="stop"
        )
        self.assertNotEqual("error", delivered.state)
        self.assertNotEqual("stopped", self.branch("peer").status)
        for n in range(3):
            await self.say(
                "leader",
                to="Worker",
                kind="handoff",
                content=f"Verify conflicting sources, attempt {n}",
                resolution="verify",
            )
        self.assertEqual("stopped", self.branch("worker").status)
        self.assertEqual(3, self.branch("worker").verifications)

    async def test_stale_reservation_does_not_pause_or_charge_current_assignment(self):
        with self.assertRaises(SharedContextConcurrencyError):
            await self.service.coordinate_handoff(
                user_id="u",
                team_id="ticket-1",
                task_id=self.task,
                sender="worker-session",
                recipients=("peer-session",),
                owner="leader-session",
                handoff_id="stale",
                kind="question",
                content="Old requirement",
                based_on_revision=0,
            )
        self.assertEqual({}, self.storage.context.state.tasks[self.task].collaboration)

    async def test_context_delta_dict_is_validated_and_cannot_close_ticket(self):
        context_delta_schema = TeamSay.input_schema["$defs"]["ContextDelta"]
        self.assertNotIn("status", context_delta_schema["properties"])
        await self.say(
            "worker",
            to="Leader",
            kind="result",
            content="Found options",
            context_delta={"add_outputs": ["Option lookup complete"]},
        )
        delivered = await self.tool("worker")(
            to="Leader", content="Close", context_delta={"status": "completed"}
        )
        self.assertNotEqual("error", delivered.state)
        self.assertEqual("running", self.storage.context.state.tasks[self.task].status)

    async def test_idle_time_is_free_and_measured_budget_survives_restart(self):
        self.service.config = replace(
            self.service.config,
            collaboration_max_active_seconds=2,
            collaboration_max_tokens=100,
            collaboration_max_model_calls=2,
        )
        await self.service.measure_collaboration(
            "u",
            "ticket-1",
            "worker-session",
            tokens=40,
            model_call=1,
            active_seconds=0.5,
        )
        await asyncio.sleep(0.01)
        self.assertEqual(0.5, self.branch("worker").active_seconds)
        restored = SharedContextService(
            self.storage, InMemoryMessageBus(), self.service.config
        )
        with self.assertRaises(CollaborationStoppedError):
            await restored.measure_collaboration(
                "u", "ticket-1", "worker-session", tokens=61
            )
        self.assertEqual("stopped", self.branch("worker").status)
        self.assertEqual(101, self.branch("worker").measured_tokens)

    async def test_model_and_active_time_limits_are_independent(self):
        self.service.config = replace(
            self.service.config,
            collaboration_max_model_calls=1,
            collaboration_max_active_seconds=1,
        )
        await self.service.measure_collaboration(
            "u", "ticket-1", "worker-session", model_call=1
        )
        with self.assertRaisesRegex(CollaborationStoppedError, "model call"):
            await self.service.measure_collaboration(
                "u", "ticket-1", "worker-session", model_call=1
            )
        with self.assertRaisesRegex(CollaborationStoppedError, "active execution"):
            await self.service.measure_collaboration(
                "u", "ticket-1", "peer-session", active_seconds=1
            )

    async def test_private_exchange_does_not_publish_output_to_leader(self):
        question = await self.say(
            "worker",
            to="Peer",
            kind="question",
            content="Private side question",
            context_mode="isolated",
        )
        reply = await self.say(
            "peer",
            to="Worker",
            kind="answer",
            content="Private answer",
            context_mode="isolated",
            in_reply_to=question.metadata["handoff_id"],
        )
        recipients = {
            h.recipient_session_id
            for h in self.storage.handoffs.values()
            if h.handoff_id == reply.metadata["handoff_id"]
        }
        self.assertEqual({"worker-session"}, recipients)
        packet = self.service._packet_value(
            self.storage.context,
            self.storage.context.state.events,
            mode="task",
            task_id=self.task,
        )
        self.assertNotIn("Private answer", str(packet))
        self.assertNotIn("Private side question", str(packet))

    async def test_distinct_groups_do_not_share_waits_or_budgets(self):
        await self.say("worker", to="Peer", kind="question", content="Need data")
        self.assertIsNone(
            await self.service.collaboration_pause(
                "u", "other-ticket", "worker-session"
            )
        )
        inbox = await self.bus.queue_drain(
            MessageBusKeys.inbox("peer-session"), max_count=10
        )
        self.assertEqual(1, len(inbox))

    async def test_crash_after_reservation_before_event_is_recovered_once(self):
        with patch.object(
            self.service,
            "append_event",
            AsyncMock(side_effect=OSError("injected storage outage")),
        ):
            result = await self.tool("worker")(
                to="Peer",
                kind="question",
                content="Look up option",
                idempotency_key="recover-me",
            )
        self.assertEqual("error", result.state)
        self.assertEqual("waiting_peer", self.branch("worker").status)
        self.assertEqual(1, len(self.storage.handoffs))
        dispatcher = HandoffDispatcher(self.bus, self.storage)
        await dispatcher._recover(include_delivered=True)
        await dispatcher._recover(include_delivered=True)
        inbox = await self.bus.queue_drain(
            MessageBusKeys.inbox("peer-session"), max_count=10
        )
        self.assertEqual(1, len(inbox))
        self.assertEqual(1, self.branch("worker").exchanges)
        self.assertEqual(
            1,
            len([e for e in self.storage.context.state.events if e.id == "recover-me"]),
        )
        intent = next(
            h
            for h in self.storage.handoffs.values()
            if "collaboration_intent" in h.payload
        )
        self.assertEqual("consumed", intent.delivery_status)

    async def test_new_user_requirement_cancels_old_undelivered_intent(self):
        with patch.object(
            self.service,
            "append_event",
            AsyncMock(side_effect=OSError("injected storage outage")),
        ):
            await self.tool("worker")(to="Peer", kind="question", content="Old task")
        await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            kind="customer_message",
            content="Changed my requirements",
            event_id="customer-2",
        )
        await HandoffDispatcher(self.bus, self.storage)._recover(include_delivered=True)
        self.assertEqual(
            [],
            await self.bus.queue_drain(
                MessageBusKeys.inbox("peer-session"), max_count=10
            ),
        )
        self.assertTrue(
            all(
                h.delivery_status == "cancelled" for h in self.storage.handoffs.values()
            )
        )

    async def test_redis_restart_does_not_replay_previous_customer_requirement(self):
        await self.say("worker", to="Peer", kind="question", content="Old requirement")
        await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            kind="customer_message",
            content="A different requirement",
            event_id="customer-2",
        )
        bus = InMemoryMessageBus()
        await HandoffDispatcher(bus, self.storage)._recover(include_delivered=True)
        self.assertEqual(
            [],
            await bus.queue_drain(MessageBusKeys.inbox("peer-session"), max_count=10),
        )

    async def test_stop_dependency_wakes_waiter_and_never_closes_ticket(self):
        await self.say(
            "worker", to="Peer", kind="question", content="Need verified result"
        )
        await self.say(
            "leader",
            to="Peer",
            kind="handoff",
            resolution="stop",
            content="Provider unavailable; cannot finish this part",
        )
        self.assertEqual("running", self.branch("worker").status)
        self.assertEqual("stopped", self.branch("peer").status)
        self.assertIsNone(
            self.storage.context.state.tasks[self.task].pending_question_ids or None
        )

    async def test_conflict_does_not_require_source_references(self):
        accepted = await self.tool("worker")(
            to="Leader",
            kind="conflict",
            content="They disagree",
            reference_event_ids=("invented-a", "invented-b"),
        )
        self.assertEqual("running", accepted.state)
        self.assertEqual("review", self.branch("worker").status)
        self.assertIsNone(await self.service.pending_user_question("u", "ticket-1"))

    async def test_invented_task_cannot_reset_worker_budget(self):
        result = await self.tool("worker")(
            to="Leader", content="Reset my budget", task_id="invented-task"
        )
        self.assertEqual("error", result.state)
        self.assertNotIn("invented-task", self.storage.context.state.tasks)

    async def test_direct_mention_agent_is_reply_owner_not_an_internal_proposal(self):
        from agentscope.app._team_turn import start_team_turn

        await start_team_turn(
            self.bus,
            "ticket-1",
            reply_owner_session_id="worker-session",
            reply_owner_agent_id="worker",
            customer_session_id="leader-session",
            mode="direct_mention",
            task_id=self.task,
            storage=self.storage,
            user_id="u",
        )
        await self.say(
            "worker",
            kind="requires_user_input",
            content="Which option should I use?",
            question_key="choose:option",
        )
        self.assertEqual(
            "Which option should I use?",
            await self.service.pending_user_question("u", "ticket-1"),
        )
        self.assertEqual("worker-session", self.storage.turn.reply_owner_session_id)
        self.assertEqual(
            "requires_user_input", self.storage.context.state.events[-1].kind
        )

    async def test_direct_mention_owner_cannot_report_terminal_result_to_leader(self):
        from agentscope.app._team_turn import start_team_turn

        await start_team_turn(
            self.bus,
            "ticket-1",
            reply_owner_session_id="worker-session",
            reply_owner_agent_id="worker",
            customer_session_id="leader-session",
            mode="direct_mention",
            task_id=self.task,
            storage=self.storage,
            user_id="u",
        )

        question = await self.say(
            "worker",
            to="Peer",
            kind="question",
            content="Find verified options",
        )
        await self.bus.queue_drain(MessageBusKeys.wakeup_queue(), max_count=10)
        await self.say(
            "peer",
            to="Worker",
            kind="answer",
            content="Two verified options are available",
            in_reply_to=question.metadata["handoff_id"],
        )
        await self.bus.queue_drain(MessageBusKeys.wakeup_queue(), max_count=10)
        handoffs_before = len(self.storage.handoffs)

        for kind in ("result", "error"):
            result = await self.tool("worker")(
                to="Leader",
                kind=kind,
                content="Completed internal work",
            )

            self.assertEqual("error", result.state)
            self.assertEqual(
                "Bạn đang sở hữu lượt trả lời; hãy trả lời khách hàng trực tiếp.",
                result.content[0].text,
            )
            self.assertEqual(
                "direct_mention_reply_owner",
                result.metadata["reason"],
            )

        self.assertEqual(handoffs_before, len(self.storage.handoffs))
        self.assertEqual(
            [],
            await self.bus.queue_drain(
                MessageBusKeys.wakeup_queue(),
                max_count=10,
            ),
        )
        self.assertEqual("running", self.storage.turn.status)

    async def test_real_agent_sleeps_immediately_after_peer_question(self):
        from agentscope.agent import Agent, InjectionConfig, ReActConfig
        from agentscope.app.middleware import TeamMemberLoopMiddleware
        from agentscope.message import ToolCallBlock, UserMsg
        from agentscope.model import ChatResponse
        from agentscope.tool import Toolkit
        from tests.utils import MockModel

        model = MockModel()
        model.set_responses(
            [
                ChatResponse(
                    content=[
                        ToolCallBlock(
                            id="peer-call",
                            name="TeamSay",
                            input=json.dumps(
                                {
                                    "to": "Peer",
                                    "kind": "question",
                                    "content": "Find verified options",
                                }
                            ),
                        )
                    ],
                    is_last=True,
                )
            ]
        )
        agent = Agent(
            name="Worker",
            system_prompt="Coordinate",
            model=model,
            toolkit=Toolkit(tools=[self.tool("worker")]),
            react_config=ReActConfig(max_iters=4),
            middlewares=[
                TeamMemberLoopMiddleware(
                    leader_name="Leader",
                    pending_question=lambda: self.service.collaboration_pause(
                        "u", "ticket-1", "worker-session"
                    ),
                )
            ],
            injection_config=InjectionConfig(inject_runtime_state=False),
        )
        events = [
            event
            async for event in agent.reply_stream(
                UserMsg("user", "Work on assigned task")
            )
        ]
        self.assertEqual(1, model.cnt)
        self.assertEqual("waiting_peer", self.branch("worker").status)
        self.assertTrue(events)

    async def test_partner_boundary_rejects_excess_usage_before_committing_result(self):
        from agentscope.app.workforce.orchestration import SqlRuntimeContinuation
        from agentscope.app.workforce.orchestration.workflows.phase_a import (
            AgentVersionPin,
            PinnedRuntimeContext,
            UsedBudget,
            WorkflowCheckpoint,
        )
        from tests.workforce.orchestration.test_shared_context_projection import (
            _workflow,
        )

        workflow = _workflow().model_copy(update={"version_pins": ("v1",)})
        checkpoint = WorkflowCheckpoint(
            workflow_id=workflow.workflow_id,
            state_revision=workflow.revision,
            session_refs=("partner-leader",),
            agent_version_pins=(AgentVersionPin(agent_id="leader", version_id="v1"),),
            shared_state_ref=workflow.group_id,
            used_budget=UsedBudget(
                model_turns=0, tool_calls=0, input_tokens=0, output_tokens=0
            ),
        )
        context = PinnedRuntimeContext(workflow=workflow, checkpoint=checkpoint)
        self.storage.context = None  # This fixture stores one group at a time.
        await self.service.append_event(
            user_id=workflow.scope.manager_account_id,
            team_id=workflow.group_id,
            task_id=workflow.workflow_id,
            kind="customer_message",
            content="Generic partner request",
        )
        self.service.config = replace(self.service.config, collaboration_max_tokens=50)
        updated = checkpoint.model_copy(
            update={
                "state_revision": workflow.revision + 1,
                "used_budget": UsedBudget(
                    model_turns=1, tool_calls=0, input_tokens=40, output_tokens=11
                ),
            }
        )
        runner = SimpleNamespace(
            invoke_turn=AsyncMock(
                return_value={
                    "candidate": {
                        "trigger_id": "trigger-1",
                        "expected_state_revision": workflow.revision,
                        "checkpoint": updated,
                        "result": {},
                    },
                    "next_state": "active",
                }
            )
        )
        runtime = SqlRuntimeContinuation(None, None, runner, self.service, object())
        with self.assertRaises(CollaborationStoppedError):
            await runtime.invoke_turn(workflow.scope, {}, context, object())
        passed_context = runner.invoke_turn.call_args.args[2]
        self.assertIn("BOUNDED COLLABORATION", passed_context.leader_system_prompt)
        branch = self.storage.context.state.tasks[workflow.workflow_id].collaboration[
            "workflow-turn:partner-leader"
        ]
        self.assertEqual(51, branch.measured_tokens)
        self.assertEqual("stopped", branch.status)
        self.assertEqual(
            "running", self.storage.context.state.tasks[workflow.workflow_id].status
        )
