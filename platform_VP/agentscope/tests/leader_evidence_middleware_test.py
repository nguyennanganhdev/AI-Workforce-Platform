"""Runtime evidence-gate tests for the fixed Workforce Leader."""

import json
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from agentscope.agent import ReActConfig
from agentscope.app.middleware import LeaderEvidenceMiddleware
from agentscope.app._evidence_claims import ClaimValidation, validate_claims
from agentscope.event import (
    ReplyEndEvent,
    TextBlockDeltaEvent,
    TextBlockEndEvent,
    TextBlockStartEvent,
)
from agentscope.message import TextBlock, ToolCallBlock, ToolResultBlock, ToolResultState
from agentscope.state import AgentState


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

    async def team_evidence_status(self, *args, **kwargs):
        del args, kwargs
        return self.status

    async def pending_user_question(self, *args):
        return None

    async def collaboration_review(self, *args, **_kwargs):
        return []

    async def validate_customer_reply_claims(self, *args):
        return ClaimValidation((), args[-1], (), bool(args[-1]))

    async def active_task_id(self, *args):
        return "task-1"

    async def session_revision(self, *args, **kwargs):
        return self.seen_revision

    async def latest_event_revision(self, *args, **kwargs):
        return self.latest_revision


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
    def test_multi_question_clarification_may_end_with_polite_sentence(self):
        text = (
            "Where will you depart from? How many people are travelling? "
            "Please provide those details so I can continue."
        )
        self.assertTrue(LeaderEvidenceMiddleware._safe_without_evidence(text))

    def test_question_with_unverified_price_is_not_safe(self):
        self.assertFalse(
            LeaderEvidenceMiddleware._safe_without_evidence(
                "Hotel A costs 2,000,000 VND. Would you like it?"
            )
        )

    def test_optional_preference_deferral_is_not_safe_clarification(self):
        self.assertFalse(
            LeaderEvidenceMiddleware._safe_without_evidence(
                "Bạn có muốn ưu tiên loại khách sạn nào không? "
                "Nếu không có yêu cầu thêm, tôi sẽ bắt đầu tìm phương án."
            )
        )

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

    def test_batch_counts_actual_dispatches_even_when_one_invite_fails(self):
        agent = self._agent(dispatched=True)
        for block in agent.state.context[-1].get_content_blocks("tool_result"):
            block.state = ToolResultState.ERROR
            block.metadata = {
                "invited_targets": ["Planner@1", "Search@2", "Resource@3"],
                "failed_targets": ["Calculator@4"],
            }
        self.assertEqual(LeaderEvidenceMiddleware._expected_reports(agent), 3)

    async def test_registered_question_is_presented_not_internal_error(self):
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
        self.assertEqual(text, "Bạn cho mình mã yêu cầu được không?")
        self.assertIsNone(output[-1].error)

    async def test_worker_wait_timeout_does_not_invent_or_promise_future_result(self):
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
        self.assertIn("did not finish", text)
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

    async def test_delegation_placeholder_is_replaced_after_worker_result(
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
        self.assertIn("Khách sạn A", streamed)

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

    async def test_unsupported_factual_answer_is_replaced_by_clarification(
        self,
    ) -> None:
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
            for event in _text_round(
                "reply-1",
                "clarify",
                "Bạn muốn ở khu vực nào?",
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

        self.assertNotIn("2.000.000", streamed)
        self.assertEqual(streamed, "Bạn muốn ở khu vực nào?")
        private_text = "\n".join(
            message.get_text_content() or "" for message in agent.state.context
        )
        self.assertNotIn("2.000.000", private_text)

    async def test_current_evidence_does_not_allow_unrelated_named_claim(self) -> None:
        shared = _SharedContext((1, 0, 1, False))
        shared.validate_customer_reply_claims = AsyncMock(
            side_effect=[
                ClaimValidation(("name:invented hotel",), "", (), True),
                ClaimValidation((), "Verified Hotel costs 1,500,000 VND.", (), True),
            ],
        )
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
            for event in _text_round(
                "reply-1", "grounded", "Verified Hotel costs 1,500,000 VND."
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
        self.assertNotIn("Invented Hotel", streamed)
        self.assertIn("Verified Hotel", streamed)

    async def test_factual_answer_ending_in_question_still_runs_evidence_gate(
        self,
    ) -> None:
        shared = _SharedContext((1, 0, 1, False))
        shared.validate_customer_reply_claims = AsyncMock(
            side_effect=[
                ClaimValidation(("date:16/10",), "", (), True),
                ClaimValidation((), "Xe khởi hành 17/10. Bạn muốn chọn phương án nào?", (), True),
            ],
        )
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
                "Xe khởi hành 16/10. Bạn muốn chọn phương án nào?",
            ):
                yield event
            for event in _text_round(
                "reply-1",
                "grounded-date",
                "Xe khởi hành 17/10. Bạn muốn chọn phương án nào?",
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
        self.assertIn("17/10", streamed)

    async def test_review_refresh_and_claim_repair_have_independent_budgets(self):
        shared = _SharedContext((1, 0, 1, False))
        source = '{"name":"Verified Hotel","price_vnd":1500000}'

        async def validate(*args):
            return validate_claims(args[-1], [source])

        shared.validate_customer_reply_claims = validate
        middleware = LeaderEvidenceMiddleware(
            _Storage(), shared, "u", "leader", "session-1", wait_seconds=0,
            max_nudges=1, max_repairs=1, max_rounds=0,
        )
        # Each round reads pending review twice. The first round needs one
        # explicit review; subsequent rounds need a refresh and then a repair.
        middleware._review = AsyncMock(side_effect=[
            ["worker-session"], ["worker-session"], [], [], [], [], [], [],
        ])
        middleware._has_unseen_evidence = AsyncMock(side_effect=[True, False, False])
        agent = self._agent(dispatched=False)
        valid = "Verified Hotel costs 1500000 VND."

        async def next_handler(**kwargs):
            del kwargs
            for index, text in enumerate((
                valid, valid, valid + "\nImaginary Resort costs 900000 VND.", valid,
            )):
                for event in _text_round("reply-1", f"budget-{index}", text):
                    yield event

        output = [event async for event in middleware.on_reply(agent, {}, next_handler)]
        text = "".join(event.delta for event in output if isinstance(event, TextBlockDeltaEvent))
        self.assertEqual(valid, text)
        hints = "\n".join(
            block.hint for message in agent.state.context
            for block in message.get_content_blocks("hint")
        )
        self.assertIn("Review incoming", hints)
        self.assertIn("New verified team evidence", hints)
        self.assertIn("Repair only", hints)
        self.assertEqual(1, hints.count("Repair only"))
        self.assertNotIn("Imaginary Resort", text)

    async def test_repair_exhaustion_returns_valid_partial_without_learning(self):
        shared = _SharedContext((1, 0, 1, False))

        async def validate(*args):
            return validate_claims(args[-1], ['{"name":"Verified Hotel","price_vnd":1500000}'])

        shared.validate_customer_reply_claims = validate
        learned = []
        middleware = LeaderEvidenceMiddleware(
            _Storage(), shared, "u", "leader", "session-1", wait_seconds=0,
            max_repairs=1, on_verified_answer=learned.append,
        )
        agent = self._agent(dispatched=False)
        valid = "Verified Hotel costs 1500000 VND."
        mixed = valid + "\nImaginary Resort costs 900000 VND."

        async def next_handler(**kwargs):
            del kwargs
            for index in range(2):
                agent.state.append_context("Leader", [TextBlock(id=f"draft-{index}", text=mixed)])
                for event in _text_round("reply-1", f"repair-{index}", mixed):
                    yield event

        output = [event async for event in middleware.on_reply(agent, {}, next_handler)]
        text = "".join(event.delta for event in output if isinstance(event, TextBlockDeltaEvent))
        self.assertIn(valid, text)
        self.assertIn("partial verified results", text)
        self.assertNotIn("Imaginary Resort", text)
        self.assertNotIn("900000", text)
        self.assertEqual([], learned)
        private_text = "\n".join(message.get_text_content() or "" for message in agent.state.context)
        self.assertNotIn("Imaginary Resort", private_text)
        self.assertNotIn("900000", private_text)
        self.assertIsNone(output[-1].error)

    async def test_refresh_does_not_restore_partial_from_an_old_source_revision(self):
        shared = _SharedContext((1, 0, 1, False))
        current_price = [1500000]

        async def validate(*args):
            source = json.dumps({"name": "Verified Hotel", "price_vnd": current_price[0]})
            return validate_claims(args[-1], [source])

        shared.validate_customer_reply_claims = validate
        middleware = LeaderEvidenceMiddleware(
            _Storage(), shared, "u", "leader", "session-1", wait_seconds=0,
            max_repairs=1,
        )
        agent = self._agent(dispatched=False)

        async def next_handler(**kwargs):
            del kwargs
            for event in _text_round(
                "reply-1", "before-update",
                "Verified Hotel costs 1500000 VND.\nImaginary Resort costs 900000 VND.",
            ):
                yield event
            current_price[0] = 1600000
            shared.latest_revision = 2
            for event in _text_round("reply-1", "old-snapshot", "Verified Hotel costs 1500000 VND."):
                yield event
            shared.seen_revision = 2
            for event in _text_round("reply-1", "failed-repair", "Imaginary Resort costs 900000 VND."):
                yield event

        output = [event async for event in middleware.on_reply(agent, {}, next_handler)]
        text = "".join(event.delta for event in output if isinstance(event, TextBlockDeltaEvent))
        self.assertNotIn("1500000", text)
        self.assertNotIn("900000", text)
        self.assertNotIn("Imaginary Resort", text)
        self.assertIn("did not finish", text)
        self.assertIsNone(output[-1].error)


class TestLeaderLearningHook(IsolatedAsyncioTestCase):
    async def test_verified_answer_triggers_learning_once_per_reply(self) -> None:
        learned: list[str] = []
        middleware = LeaderEvidenceMiddleware(
            _Storage(),  # type: ignore[arg-type]
            _SharedContext((1, 0, 1, False)),  # type: ignore[arg-type]
            "user-1",
            "leader-agent",
            "session-1",
            wait_seconds=0,
            on_verified_answer=learned.append,
        )
        agent = TestLeaderEvidenceMiddleware._agent(None, dispatched=True)  # type: ignore[arg-type]

        async def next_handler(**kwargs):
            del kwargs
            for event in _text_round("reply-1", "draft", "Đang chờ."):
                yield event
            for event in _text_round("reply-1", "final", "Khách sạn A còn phòng theo kết quả agent."):
                yield event

        async for _ in middleware.on_reply(agent, {}, next_handler):  # type: ignore[arg-type]
            pass

        self.assertEqual(["team-1"], learned)
