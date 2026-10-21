"""Runtime coordination tests for the fixed Workforce Leader."""

import json
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from utils import MockModel

from agentscope.agent import Agent, InjectionConfig, ReActConfig
from agentscope.app.middleware import LeaderEvidenceMiddleware
from agentscope.event import (
    ReplyEndEvent,
    TextBlockDeltaEvent,
    TextBlockEndEvent,
    TextBlockStartEvent,
)
from agentscope.message import (
    HintBlock,
    TextBlock,
    ToolCallBlock,
    ToolResultBlock,
    ToolResultState,
    UserMsg,
)
from agentscope.model import ChatResponse
from agentscope.state import AgentState
from agentscope.types import ReplyFinishedReason


class _Storage:
    async def get_session(self, user_id: str, agent_id: str, session_id: str):
        del user_id, agent_id, session_id
        return SimpleNamespace(team_id="team-1", state=AgentState(), id="session-1")

    async def get_team(self, user_id, team_id):
        return None


class _SharedContext:
    def __init__(self, status: tuple[int, int, int, bool]) -> None:
        self.status = status
        self.seen_revision = 1
        self.latest_revision = 1
        self.storage = SimpleNamespace(get_team_shared_context=AsyncMock(return_value=None))

    async def team_evidence_status(self, *args, **kwargs):
        del args, kwargs
        return self.status

    async def pending_user_question(self, *args):
        return None

    async def collaboration_review(self, *args):
        return []

    async def active_task_id(self, *args):
        return "task-1"

    async def session_revision(self, *args, **kwargs):
        return self.seen_revision

    async def latest_event_revision(self, *args, **kwargs):
        return self.latest_revision

    async def seal_final_answer(
        self, *args, expected_event_revision: int, **kwargs
    ):
        del args, kwargs
        return expected_event_revision == self.latest_revision


def _text_round(reply_id: str, block_id: str, text: str):
    yield TextBlockStartEvent(reply_id=reply_id, block_id=block_id)
    yield TextBlockDeltaEvent(
        reply_id=reply_id,
        block_id=block_id,
        delta=text,
    )
    yield TextBlockEndEvent(reply_id=reply_id, block_id=block_id)
    yield ReplyEndEvent(session_id="session-1", reply_id=reply_id)


class TestLeaderEvidenceMiddleware(IsolatedAsyncioTestCase):
    def test_leader_cannot_ask_task_specific_clarification(self):
        text = (
            "Where will you depart from? How many people are travelling? "
            "Please provide those details so I can continue."
        )
        self.assertTrue(LeaderEvidenceMiddleware._is_customer_intake(text))
        self.assertTrue(
            LeaderEvidenceMiddleware._is_customer_intake(
                "Vui lòng cung cấp thành phố xuất phát."
            )
        )

    async def test_leader_question_is_blocked_even_with_worker_evidence(self):
        middleware = LeaderEvidenceMiddleware(
            _Storage(),
            _SharedContext((1, 0, 1, False)),
            "u",
            "leader",
            "session-1",
            wait_seconds=0,
        )
        agent = self._agent(dispatched=False)

        async def next_handler(**kwargs):
            del kwargs
            for event in _text_round(
                "reply-1", "question", "Bạn xuất phát từ đâu?"
            ):
                yield event
            for event in _text_round(
                "reply-1", "answer", "Verified worker result is complete."
            ):
                yield event

        output = [
            event async for event in middleware.on_reply(agent, {}, next_handler)
        ]
        streamed = "".join(
            event.delta
            for event in output
            if isinstance(event, TextBlockDeltaEvent)
        )

        self.assertEqual("Verified worker result is complete.", streamed)
        private_text = "\n".join(
            message.get_text_content() or "" for message in agent.state.context
        )
        self.assertNotIn("Bạn xuất phát từ đâu?", private_text)

    def test_resolution_does_not_start_another_wait_for_worker(self):
        agent = self._agent(dispatched=True)
        for call in agent.state.context[-1].get_content_blocks("tool_call"):
            call.name = "TeamSay"
            call.input = json.dumps(
                {
                    "to": "Worker",
                    "kind": "handoff",
                    "content": "Incomplete; stop",
                    "resolution": "stop",
                }
            )
        self.assertEqual(0, LeaderEvidenceMiddleware._expected_reports(agent))

    async def test_internal_stop_after_resolution_requires_synthesis_before_sealing(self):
        bad = "(This is prohibited because after successful team message must end run.)"
        answer = "Vé máy bay 8.100.000 VND; phòng 2.800.000 VND. Chưa đặt dịch vụ."
        for resolution in ("complete", "stop"):
            with self.subTest(resolution=resolution):
                shared = _SharedContext((4, 0, 4, False))
                shared.seal_final_answer = AsyncMock(return_value=True)
                middleware = LeaderEvidenceMiddleware(
                    _Storage(), shared, "u", "leader", "session-1"
                )
                agent = self._agent(dispatched=False)
                agent.state.append_context("Leader", [
                    ToolCallBlock(
                        id="close", name="TeamSay",
                        input=json.dumps({
                            "to": "Restaurant", "kind": "handoff", "resolution": resolution,
                        }),
                    ),
                    ToolResultBlock(
                        id="close", name="TeamSay", output="Delivered",
                        state=ToolResultState.SUCCESS,
                    ),
                ])

                async def next_handler(**kwargs):
                    agent.state.append_context("Leader", [TextBlock(text=bad)])
                    for event in _text_round("reply-1", "internal-stop", bad):
                        yield event
                    shared.seal_final_answer.assert_not_awaited()
                    for event in _text_round("reply-1", "synthesis", answer):
                        yield event

                output = [
                    event async for event in middleware.on_reply(agent, {}, next_handler)
                ]
                text = "".join(
                    e.delta for e in output if isinstance(e, TextBlockDeltaEvent)
                )
                self.assertEqual(text, answer)
                self.assertNotIn(
                    bad, "\n".join(m.get_text_content() or "" for m in agent.state.context)
                )
                shared.seal_final_answer.assert_awaited_once()

    async def test_repeated_internal_stop_or_empty_answer_fails_without_sealing(self):
        for text in ("", "End this run after successful team message."):
            with self.subTest(text=text):
                shared = _SharedContext((1, 0, 1, False))
                shared.seal_final_answer = AsyncMock(return_value=True)
                middleware = LeaderEvidenceMiddleware(
                    _Storage(), shared, "u", "leader", "session-1", max_nudges=1,
                )

                async def next_handler(**kwargs):
                    for index in range(2):
                        for event in _text_round("reply-1", f"bad-{index}", text):
                            yield event

                output = [event async for event in middleware.on_reply(
                    self._agent(dispatched=False), {}, next_handler,
                )]
                self.assertEqual(output[-1].finished_reason, ReplyFinishedReason.ERROR)
                shared.seal_final_answer.assert_not_awaited()
                self.assertFalse(any(isinstance(e, TextBlockDeltaEvent) for e in output))

    async def test_plain_leader_chat_keeps_answer_with_future_phrase(self):
        answer = "Tôi sẽ hỗ trợ bạn đặt phòng khách sạn."

        class _NoTeamStorage(_Storage):
            async def get_session(self, user_id, agent_id, session_id):
                del user_id, agent_id, session_id
                return SimpleNamespace(team_id=None, state=AgentState(), id="session-1")

        middleware = LeaderEvidenceMiddleware(
            _NoTeamStorage(), _SharedContext((0, 0, 0, False)), "u", "leader", "session-1",
        )

        async def next_handler(**kwargs):
            for event in _text_round("reply-1", "answer", answer):
                yield event

        output = [event async for event in middleware.on_reply(
            self._agent(dispatched=False), {}, next_handler,
        )]
        self.assertEqual(
            "".join(e.delta for e in output if isinstance(e, TextBlockDeltaEvent)), answer,
        )
        self.assertEqual(output[-1].finished_reason, ReplyFinishedReason.COMPLETED)

    async def test_plain_chat_still_rejects_empty_or_leaked_instruction(self):
        for text in ("", "End this run after successful team message."):
            with self.subTest(text=text):
                class _NoTeamStorage(_Storage):
                    async def get_session(self, user_id, agent_id, session_id):
                        return SimpleNamespace(team_id=None, state=AgentState(), id="session-1")

                middleware = LeaderEvidenceMiddleware(
                    _NoTeamStorage(), _SharedContext((0, 0, 0, False)), "u", "leader",
                    "session-1", max_nudges=1,
                )

                async def next_handler(**kwargs):
                    for index in range(2):
                        for event in _text_round("reply-1", f"bad-{index}", text):
                            yield event

                output = [event async for event in middleware.on_reply(
                    self._agent(dispatched=False), {}, next_handler,
                )]
                self.assertEqual(output[-1].finished_reason, ReplyFinishedReason.ERROR)

    async def test_former_team_session_keeps_a_plain_answer_for_a_new_request(self):
        answer = "Tôi sẽ hỗ trợ bạn đặt phòng khách sạn."
        middleware = LeaderEvidenceMiddleware(
            _Storage(), _SharedContext((0, 0, 0, False)), "u", "leader", "session-1",
        )

        async def next_handler(**kwargs):
            for event in _text_round("reply-1", "answer", answer):
                yield event

        output = [event async for event in middleware.on_reply(
            self._agent(dispatched=False), {}, next_handler,
        )]
        self.assertEqual(
            "".join(e.delta for e in output if isinstance(e, TextBlockDeltaEvent)), answer,
        )

    async def test_internal_stop_retries_the_real_agent_loop_at_iteration_limit(self):
        bad = "(This is prohibited because after successful team message must end run.)"
        answer = "Kết quả đã xác minh; chưa đặt dịch vụ."
        model = MockModel()
        model.set_responses([
            ChatResponse(content=[TextBlock(text=bad)], is_last=True),
            ChatResponse(content=[TextBlock(text=answer)], is_last=True),
        ])
        shared = _SharedContext((1, 0, 1, False))
        shared.seal_final_answer = AsyncMock(return_value=True)
        agent = Agent(
            name="Leader", system_prompt="Synthesize the verified results.", model=model,
            react_config=ReActConfig(max_iters=1),
            injection_config=InjectionConfig(inject_runtime_state=False),
            middlewares=[LeaderEvidenceMiddleware(_Storage(), shared, "u", "leader", "session-1")],
        )
        output = [
            event async for event in agent.reply_stream(UserMsg("user", "Tổng hợp kết quả."))
        ]
        self.assertEqual(model.cnt, 2)
        self.assertEqual(
            "".join(e.delta for e in output if isinstance(e, TextBlockDeltaEvent)), answer,
        )
        self.assertEqual(
            [e.finished_reason for e in output if isinstance(e, ReplyEndEvent)],
            [ReplyFinishedReason.COMPLETED],
        )
        shared.seal_final_answer.assert_awaited_once()

    def test_batch_counts_actual_dispatches_even_when_one_invite_fails(self):
        agent = self._agent(dispatched=True)
        for block in agent.state.context[-1].get_content_blocks("tool_result"):
            block.state = ToolResultState.ERROR
            block.metadata = {
                "invited_targets": ["Planner@1", "Search@2", "Resource@3"],
                "failed_targets": ["Calculator@4"],
            }
        self.assertEqual(LeaderEvidenceMiddleware._expected_reports(agent), 3)

    def test_batch_counts_all_started_subagents_and_preserves_legacy_metadata(self):
        targets = ["Search@1", "Reviewer@2", "Calculator@3"]
        for started in (targets[:1], targets):
            with self.subTest(started=started):
                agent = self._agent(dispatched=True)
                for block in agent.state.context[-1].get_content_blocks("tool_result"):
                    block.metadata = {
                        "invited_targets": targets,
                        "started_targets": started,
                        "failed_targets": [],
                    }
                self.assertEqual(len(started), LeaderEvidenceMiddleware._expected_reports(agent))

    async def test_registered_specialist_question_ends_leader_silently(self):
        shared = _SharedContext((0, 0, 0, False))
        shared.pending_user_question = AsyncMock(
            return_value="Bạn cho mình mã yêu cầu được không?"
        )
        middleware = LeaderEvidenceMiddleware(
            _Storage(), shared, "u", "leader", "session-1", wait_seconds=0
        )

        async def next_handler(**kwargs):
            for event in _text_round(
                "reply-1", "bad", "Technician arrives in 30 minutes."
            ):
                yield event

        output = [
            event
            async for event in middleware.on_reply(
                self._agent(dispatched=True), {}, next_handler
            )
        ]
        text = "".join(e.delta for e in output if isinstance(e, TextBlockDeltaEvent))
        self.assertEqual(text, "")
        self.assertEqual(len(output), 1)
        self.assertIsInstance(output[0], ReplyEndEvent)
        self.assertIsNone(output[-1].error)

    async def test_pending_specialist_question_skips_another_leader_model_call(self):
        shared = _SharedContext((0, 0, 0, True))
        shared.pending_user_question = AsyncMock(
            return_value="Bạn đi mấy người và xuất phát từ đâu?",
        )
        middleware = LeaderEvidenceMiddleware(
            _Storage(), shared, "u", "leader", "session-1", wait_seconds=0
        )
        agent = self._agent(dispatched=True)
        called = False

        async def next_handler(**kwargs):
            nonlocal called
            del kwargs
            called = True
            if False:
                yield None

        output = [
            event
            async for event in middleware.on_reasoning(agent, {}, next_handler)
        ]

        self.assertFalse(called)
        self.assertEqual(len(output), 1)
        self.assertIsInstance(output[0].content[-1], HintBlock)

    async def test_dispatched_planner_ends_before_next_model_call(self):
        shared = _SharedContext((0, 0, 0, True))
        shared.pending_user_question = AsyncMock(
            side_effect=[None, "Bạn đi mấy người và xuất phát từ đâu?"],
        )
        middleware = LeaderEvidenceMiddleware(
            _Storage(), shared, "u", "leader", "session-1", wait_seconds=0
        )
        agent = self._agent(dispatched=True)
        called = False

        async def next_handler(**kwargs):
            nonlocal called
            del kwargs
            called = True
            if False:
                yield None

        output = [
            event
            async for event in middleware.on_reasoning(agent, {}, next_handler)
        ]

        self.assertFalse(called)
        self.assertEqual(len(output), 1)
        self.assertIsInstance(output[0].content[-1], HintBlock)

    async def test_report_review_can_wake_leader_but_active_work_cannot(self):
        for status, should_reason in (("review", True), ("running", False), ("waiting_peer", False)):
            with self.subTest(status=status):
                shared = _SharedContext((1, 0, 1, False))
                shared.collaboration_review = AsyncMock(return_value=["worker-session"])
                task = SimpleNamespace(latest_customer_revision=1, collaboration={
                    "worker-session": SimpleNamespace(customer_revision=1, status=status),
                })
                shared.storage.get_team_shared_context.return_value = SimpleNamespace(
                    state=SimpleNamespace(active_task_id="task", tasks={"task": task}),
                )
                middleware = LeaderEvidenceMiddleware(_Storage(), shared, "u", "leader", "session-1")
                called = False

                async def next_handler(**kwargs):
                    nonlocal called
                    called = True
                    if False:
                        yield None

                _ = [event async for event in middleware.on_reasoning(
                    self._agent(dispatched=False), {}, next_handler,
                )]
                self.assertEqual(called, should_reason)

    async def test_delegation_ends_without_wait_timeout_placeholder(self):
        middleware = LeaderEvidenceMiddleware(
            _Storage(),
            _SharedContext((0, 0, 0, False)),
            "u",
            "leader",
            "session-1",
            wait_seconds=0,
        )

        async def next_handler(**kwargs):
            for event in _text_round(
                "reply-1", "bad", "Technician arrives in 30 minutes."
            ):
                yield event

        output = [
            event
            async for event in middleware.on_reply(
                self._agent(dispatched=True), {}, next_handler
            )
        ]
        text = "".join(e.delta for e in output if isinstance(e, TextBlockDeltaEvent))
        self.assertNotIn("30 minutes", text)
        self.assertEqual("", text)
        self.assertNotIn("will update", text)
        self.assertIsNone(output[-1].error)

    async def test_pending_consent_parks_without_evidence_failure(self) -> None:
        middleware = LeaderEvidenceMiddleware(
            _Storage(),
            _SharedContext((0, 0, 0, False)),
            "user-1",
            "leader-agent",
            "session-1",
            wait_seconds=0,
        )
        agent = self._agent(dispatched=True)

        async def next_handler(**kwargs):
            for event in _text_round("reply-1", "placeholder", "Waiting for booking"):
                yield event

        with patch.object(middleware, "_pending_consent", AsyncMock(return_value=True)):
            output = [
                event async for event in middleware.on_reply(agent, {}, next_handler)
            ]

        self.assertEqual(len(output), 1)
        self.assertIsInstance(output[0], ReplyEndEvent)
        self.assertIsNone(output[0].error)
        self.assertFalse(
            any(message.get_content_blocks("hint") for message in agent.state.context)
        )

    def _agent(self, *, dispatched: bool) -> SimpleNamespace:
        state = AgentState(session_id="session-1")
        state.reply_id = "reply-1"
        if dispatched:
            state.append_context(
                "Leader",
                [
                    ToolCallBlock(
                        id="invite-1",
                        name="AgentInvite",
                        input=json.dumps(
                            {"target": "Hotel Agent@12345678", "prompt": "find"},
                        ),
                    ),
                    ToolResultBlock(
                        id="invite-1",
                        name="AgentInvite",
                        output="invited",
                        state=ToolResultState.SUCCESS,
                    ),
                ],
            )
        return SimpleNamespace(
            name="Leader",
            state=state,
            react_config=ReActConfig(max_iters=5),
        )

    async def test_delegation_placeholder_is_discarded_and_run_ends(
        self,
    ) -> None:
        middleware = LeaderEvidenceMiddleware(
            _Storage(),  # type: ignore[arg-type]
            _SharedContext((1, 0, 1, False)),  # type: ignore[arg-type]
            "user-1",
            "leader-agent",
            "session-1",
            wait_seconds=0,
        )
        agent = self._agent(dispatched=True)

        async def next_handler(**kwargs):
            del kwargs
            for event in _text_round(
                "reply-1",
                "before-evidence",
                "Tôi đã gửi yêu cầu và đang chờ.",
            ):
                yield event
            for event in _text_round(
                "reply-1",
                "after-evidence",
                "Khách sạn A còn phòng theo kết quả agent.",
            ):
                yield event

        output = [
            event
            async for event in middleware.on_reply(
                agent,  # type: ignore[arg-type]
                {},
                next_handler,
            )
        ]
        streamed = "".join(
            event.delta for event in output if isinstance(event, TextBlockDeltaEvent)
        )

        self.assertNotIn("đang chờ", streamed)
        self.assertNotIn("Khách sạn A", streamed)
        self.assertEqual(len(output), 1)
        self.assertIsInstance(output[0], ReplyEndEvent)

    async def test_evidence_arriving_during_synthesis_forces_fresh_answer(self):
        shared = _SharedContext((1, 0, 1, False))
        shared.seen_revision = 5
        shared.latest_revision = 6
        middleware = LeaderEvidenceMiddleware(
            _Storage(),  # type: ignore[arg-type]
            shared,  # type: ignore[arg-type]
            "user-1",
            "leader-agent",
            "session-1",
            wait_seconds=0,
        )
        agent = self._agent(dispatched=False)

        async def next_handler(**kwargs):
            del kwargs
            for event in _text_round(
                "reply-1",
                "stale",
                "Only the bus option is ready.",
            ):
                yield event
            shared.seen_revision = 6
            for event in _text_round(
                "reply-1",
                "fresh",
                "The verified bus, hotel and meal plan is complete.",
            ):
                yield event

        output = [
            event
            async for event in middleware.on_reply(agent, {}, next_handler)
        ]
        streamed = "".join(
            event.delta for event in output if isinstance(event, TextBlockDeltaEvent)
        )
        self.assertNotIn("Only the bus", streamed)
        self.assertEqual(
            streamed,
            "The verified bus, hotel and meal plan is complete.",
        )

    async def test_business_claim_is_not_semantically_validated(self) -> None:
        middleware = LeaderEvidenceMiddleware(
            _Storage(),  # type: ignore[arg-type]
            _SharedContext((0, 0, 0, False)),  # type: ignore[arg-type]
            "user-1",
            "leader-agent",
            "session-1",
            wait_seconds=0,
        )
        agent = self._agent(dispatched=False)

        async def next_handler(**kwargs):
            del kwargs
            for event in _text_round(
                "reply-1",
                "invented",
                "Khách sạn A giá 2.000.000 VNĐ và còn phòng.",
            ):
                yield event

        output = [
            event
            async for event in middleware.on_reply(
                agent,  # type: ignore[arg-type]
                {},
                next_handler,
            )
        ]
        streamed = "".join(
            event.delta for event in output if isinstance(event, TextBlockDeltaEvent)
        )

        self.assertEqual(
            "Khách sạn A giá 2.000.000 VNĐ và còn phòng.",
            streamed,
        )

    async def test_named_claim_is_not_semantically_validated(self) -> None:
        shared = _SharedContext((1, 0, 1, False))
        middleware = LeaderEvidenceMiddleware(
            _Storage(),  # type: ignore[arg-type]
            shared,  # type: ignore[arg-type]
            "user-1",
            "leader-agent",
            "session-1",
            wait_seconds=0,
        )
        agent = self._agent(dispatched=False)

        async def next_handler(**kwargs):
            del kwargs
            for event in _text_round(
                "reply-1", "invented", "Invented Hotel costs 2,000,000 VND."
            ):
                yield event

        output = [
            event
            async for event in middleware.on_reply(
                agent,  # type: ignore[arg-type]
                {},
                next_handler,
            )
        ]
        streamed = "".join(
            event.delta for event in output if isinstance(event, TextBlockDeltaEvent)
        )
        self.assertEqual("Invented Hotel costs 2,000,000 VND.", streamed)

    async def test_leader_customer_intake_is_blocked_before_factual_answer(
        self,
    ) -> None:
        shared = _SharedContext((1, 0, 1, False))
        middleware = LeaderEvidenceMiddleware(
            _Storage(),  # type: ignore[arg-type]
            shared,  # type: ignore[arg-type]
            "user-1",
            "leader-agent",
            "session-1",
            wait_seconds=0,
        )
        agent = self._agent(dispatched=False)

        async def next_handler(**kwargs):
            del kwargs
            for event in _text_round(
                "reply-1",
                "bad-date",
                "Xe khởi hành 16/10. Vui lòng cung cấp nơi xuất phát.",
            ):
                yield event
            for event in _text_round(
                "reply-1",
                "grounded-date",
                "Xe khởi hành 17/10. Vui lòng cung cấp nơi xuất phát.",
            ):
                yield event
            for event in _text_round(
                "reply-1",
                "final-date",
                "Xe khởi hành 17/10 theo kết quả đã xác minh.",
            ):
                yield event

        output = [
            event
            async for event in middleware.on_reply(
                agent,  # type: ignore[arg-type]
                {},
                next_handler,
            )
        ]
        streamed = "".join(
            event.delta for event in output if isinstance(event, TextBlockDeltaEvent)
        )
        self.assertNotIn("16/10", streamed)
        self.assertEqual("Xe khởi hành 17/10 theo kết quả đã xác minh.", streamed)

    async def test_useful_leader_answer_is_not_removed_only_for_question_mark(
        self,
    ) -> None:
        middleware = LeaderEvidenceMiddleware(
            _Storage(),  # type: ignore[arg-type]
            _SharedContext((1, 0, 1, False)),  # type: ignore[arg-type]
            "user-1",
            "leader-agent",
            "session-1",
            wait_seconds=0,
        )
        agent = self._agent(dispatched=False)
        answer = (
            "Xe khởi hành 17/10 đã được xác minh và phù hợp ngân sách. "
            "Bạn muốn chọn phương án này?"
        )

        async def next_handler(**kwargs):
            del kwargs
            for event in _text_round("reply-1", "useful-question", answer):
                yield event

        output = [
            event
            async for event in middleware.on_reply(
                agent,  # type: ignore[arg-type]
                {},
                next_handler,
            )
        ]
        streamed = "".join(
            event.delta for event in output if isinstance(event, TextBlockDeltaEvent)
        )

        self.assertEqual(answer, streamed)

    def test_incomplete_fallback_keeps_partial_without_future_promise(self) -> None:
        text = LeaderEvidenceMiddleware._incomplete_text(
            SimpleNamespace(),
            (
                "Đã xác minh được chuyến bay A phù hợp ngân sách. "
                "Xin Leader cho hướng xử lý."
            ),
        )

        self.assertIn("chuyến bay A", text)
        self.assertIn("chưa có đủ bằng chứng", text)
        self.assertNotIn("xin leader", text.casefold())
        self.assertNotIn("thử lại", text.casefold())
        self.assertNotIn("sẽ tiếp tục", text.casefold())
