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

    async def test_shared_peer_answer_releases_all_waiters_for_that_provider(self):
        first = await self.say(
            "worker", to="Peer", kind="question", content="Provide the price"
        )
        await self.say(
            "worker", to="Peer", kind="question", content="Provide availability"
        )
        self.assertEqual(2, len(self.branch("worker").waiting_for))

        answer = await self.say(
            "peer",
            to="Worker",
            kind="answer",
            content="The shared result contains price and availability",
            in_reply_to=first.metadata["handoff_id"],
        )

        self.assertEqual({}, self.branch("worker").waiting_for)
        self.assertEqual("running", self.branch("worker").status)
        self.assertEqual(
            (answer.metadata["handoff_id"],),
            self.branch("worker").evidence_event_ids,
        )

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

    async def test_worker_question_is_only_a_proposal_owner_approves_one(self):
        await self.say(
            "worker",
            to="Leader",
            kind="requires_user_input",
            question_key="missing:choice",
            content="Which option do you choose?",
        )
        self.assertIsNone(await self.service.pending_user_question("u", "ticket-1"))
        self.assertIsNone(self.storage.turn)
        self.assertEqual(
            "user_input_proposal", self.storage.context.state.events[-1].kind
        )
        await self.say(
            "leader",
            kind="requires_user_input",
            question_key="missing:choice",
            content="Which verified option do you choose?",
        )
        self.assertEqual(
            "Which verified option do you choose?",
            await self.service.pending_user_question("u", "ticket-1"),
        )
        second = await self.tool("leader")(
            kind="requires_user_input",
            question_key="missing:date",
            content="Which date?",
        )
        self.assertEqual("error", second.state)
        self.assertEqual(1, len(self.storage.turn.pending_question_ids))

    async def test_cyclic_dependency_stops_branch_and_notifies_owner_and_waiter(self):
        await self.say("worker", to="Peer", kind="question", content="Need your data")
        result = await self.say(
            "peer", to="Worker", kind="question", content="Need yours first"
        )
        self.assertEqual("error", result.metadata["kind"])
        self.assertEqual("stopped", self.branch("peer").status)
        self.assertEqual("running", self.branch("worker").status)
        self.assertIn("cyclic", self.branch("peer").reason)
        self.assertEqual("running", self.storage.context.state.tasks[self.task].status)

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

    async def test_same_receipt_is_free_but_new_keys_do_not_bypass_no_progress(self):
        for _ in range(2):
            await self.say(
                "worker",
                to="Leader",
                kind="progress",
                content="Still checking",
                idempotency_key="same",
            )
        self.assertEqual(1, self.branch("worker").exchanges)
        for key in ("another", "third"):
            await self.say(
                "worker",
                to="Leader",
                kind="progress",
                content="Still checking",
                idempotency_key=key,
            )
        self.assertEqual("stopped", self.branch("worker").status)
        self.assertIn("repeated", self.branch("worker").reason)

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

    async def test_complete_needs_current_evidence_does_not_close_ticket(self):
        result = await self.say(
            "worker", to="Leader", kind="result", content="Option available"
        )
        refused = await self.tool("leader")(
            to="Worker",
            kind="handoff",
            content="Enough",
            resolution="complete",
            reference_event_ids=(result.metadata["handoff_id"],),
        )
        self.assertEqual("error", refused.state)
        await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            kind="external_event",
            content="Verified option",
            event_id="tool-1",
            source_session_id="worker-session",
        )
        await self.say(
            "leader",
            to="Worker",
            kind="handoff",
            content="Enough verified information",
            resolution="complete",
            reference_event_ids=(result.metadata["handoff_id"], "tool-1"),
        )
        self.assertEqual("completed", self.branch("worker").status)
        self.assertEqual("running", self.storage.context.state.tasks[self.task].status)
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

    async def test_review_auto_completes_only_current_tool_backed_result(self):
        result = await self.say(
            "worker", to="Leader", kind="result", content="Option available"
        )
        self.assertEqual("review", self.branch("worker").status)
        self.assertEqual(
            ["worker-session"],
            await self.service.collaboration_review(
                "u", "ticket-1", "leader-session"
            ),
        )

        await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            task_id=self.task,
            kind="external_event",
            content="Verified option",
            event_id="tool-result",
            source_session_id="worker-session",
        )

        self.assertEqual(
            [],
            await self.service.collaboration_review(
                "u", "ticket-1", "leader-session"
            ),
        )
        self.assertEqual("completed", self.branch("worker").status)
        self.assertIn("evidence-backed", self.branch("worker").reason)
        self.assertEqual(result.metadata["kind"], "result")

    async def test_review_keeps_unverified_report_for_leader(self):
        await self.say(
            "worker", to="Leader", kind="result", content="Unverified proposal"
        )

        self.assertEqual(
            ["worker-session"],
            await self.service.collaboration_review(
                "u", "ticket-1", "leader-session"
            ),
        )
        self.assertEqual("review", self.branch("worker").status)

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

    async def test_verification_is_bounded_and_worker_cannot_resolve_others(self):
        refused = await self.tool("worker")(
            to="Peer", kind="handoff", content="Done", resolution="stop"
        )
        self.assertEqual("error", refused.state)
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

    async def test_conflict_requires_two_real_sources(self):
        failed = await self.tool("worker")(
            to="Leader",
            kind="conflict",
            content="They disagree",
            reference_event_ids=("invented-a", "invented-b"),
        )
        self.assertEqual("error", failed.state)
        for n in (1, 2):
            await self.service.append_event(
                user_id="u",
                team_id="ticket-1",
                kind="external_event",
                content=f"Provider value {n}",
                event_id=f"source-{n}",
            )
        await self.say(
            "worker",
            to="Leader",
            kind="conflict",
            content="Values disagree",
            reference_event_ids=("source-1", "source-2"),
        )
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
