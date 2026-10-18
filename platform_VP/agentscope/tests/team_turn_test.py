"""Regression tests for team reply ownership and user-input gating."""

from unittest import IsolatedAsyncioTestCase

from agentscope.app._router._chat import (
    _match_leading_mention,
    _strip_leading_mention,
)
from agentscope.app._team_turn import (
    build_customer_ticket_context,
    finish_team_turn,
    get_team_turn,
    register_user_input_request,
    start_team_turn,
    team_is_awaiting_user,
    team_is_paused,
)
from agentscope.app.message_bus import InMemoryMessageBus
from agentscope.message import AssistantMsg, UserMsg


class TeamTurnTest(IsolatedAsyncioTestCase):
    """One group has one reply owner and one pending customer question."""

    async def asyncSetUp(self) -> None:
        self.bus = InMemoryMessageBus()

    async def test_similar_questions_are_deduplicated(self) -> None:
        await start_team_turn(
            self.bus,
            "team",
            reply_owner_session_id="leader-session",
            reply_owner_agent_id="leader-agent",
            customer_session_id="leader-session",
            mode="leader",
        )

        _state, duplicate, first = await register_user_input_request(
            self.bus,
            "team",
            "Bạn muốn ưu tiên chi phí khách sạn hay ăn uống?",
            default_reply_owner_session_id="leader-session",
            default_reply_owner_agent_id="leader-agent",
            customer_session_id="leader-session",
        )
        self.assertFalse(duplicate)
        self.assertTrue(first)

        state, duplicate, first = await register_user_input_request(
            self.bus,
            "team",
            "Bạn muốn ưu tiên chi phí khách sạn, hay ăn uống?",
            default_reply_owner_session_id="leader-session",
            default_reply_owner_agent_id="leader-agent",
            customer_session_id="leader-session",
        )
        self.assertTrue(duplicate)
        self.assertFalse(first)
        self.assertEqual(len(state.pending_questions), 1)

    async def test_only_owner_can_pause_and_next_turn_resumes(self) -> None:
        await start_team_turn(
            self.bus,
            "team",
            reply_owner_session_id="hotel-session",
            reply_owner_agent_id="hotel-agent",
            customer_session_id="leader-session",
            mode="direct_mention",
            task_id="hotel-task",
        )
        await register_user_input_request(
            self.bus,
            "team",
            "Bạn muốn nhận phòng lúc mấy giờ?",
            default_reply_owner_session_id="hotel-session",
            default_reply_owner_agent_id="hotel-agent",
            customer_session_id="leader-session",
        )

        self.assertFalse(
            await finish_team_turn(
                self.bus,
                "team",
                session_id="other-session",
            ),
        )
        self.assertTrue(
            await finish_team_turn(
                self.bus,
                "team",
                session_id="hotel-session",
            ),
        )
        self.assertTrue(await team_is_awaiting_user(self.bus, "team"))

        await start_team_turn(
            self.bus,
            "team",
            reply_owner_session_id="hotel-session",
            reply_owner_agent_id="hotel-agent",
            customer_session_id="leader-session",
            mode="direct_mention",
            task_id="hotel-task",
        )
        state = await get_team_turn(self.bus, "team")
        self.assertIsNotNone(state)
        self.assertEqual(state.status, "running")
        self.assertEqual(state.pending_questions, [])
        self.assertEqual(state.task_id, "hotel-task")

    async def test_completed_reply_without_question_does_not_pause_team(self) -> None:
        await start_team_turn(
            self.bus,
            "team",
            reply_owner_session_id="leader-session",
            reply_owner_agent_id="leader-agent",
            customer_session_id="leader-session",
            mode="leader",
        )
        self.assertTrue(
            await finish_team_turn(
                self.bus,
                "team",
                session_id="leader-session",
            ),
        )
        self.assertFalse(await team_is_awaiting_user(self.bus, "team"))
        self.assertTrue(await team_is_paused(self.bus, "team"))
        state = await get_team_turn(self.bus, "team")
        self.assertEqual(state.status, "completed")

    async def test_pending_question_binds_followup_to_its_task(self) -> None:
        await start_team_turn(
            self.bus,
            "team",
            reply_owner_session_id="leader-session",
            reply_owner_agent_id="leader-agent",
            customer_session_id="leader-session",
            mode="leader",
        )
        state, duplicate, first = await register_user_input_request(
            self.bus,
            "team",
            "Which hotel option do you choose?",
            default_reply_owner_session_id="leader-session",
            default_reply_owner_agent_id="leader-agent",
            customer_session_id="leader-session",
            task_id="hotel-task",
        )

        self.assertFalse(duplicate)
        self.assertTrue(first)
        self.assertEqual(state.task_id, "hotel-task")

    async def test_worker_question_keeps_leader_reply_ownership(self) -> None:
        await start_team_turn(
            self.bus,
            "team",
            reply_owner_session_id="leader-session",
            reply_owner_agent_id="leader-agent",
            customer_session_id="leader-session",
            mode="leader",
        )
        state, duplicate, first = await register_user_input_request(
            self.bus,
            "team",
            "Which account should I inspect?",
            default_reply_owner_session_id="leader-session",
            default_reply_owner_agent_id="leader-agent",
            customer_session_id="leader-session",
            question_key="missing:account",
        )

        self.assertFalse(duplicate)
        self.assertTrue(first)
        self.assertEqual(state.mode, "leader")
        self.assertEqual(state.reply_owner_session_id, "leader-session")


class TeamMentionTest(IsolatedAsyncioTestCase):
    """Direct mentions route deterministically without an LLM decision."""

    async def test_longest_exact_leading_name_wins(self) -> None:
        message = UserMsg(
            name="user",
            content="@Hotel Booking Agent khách sạn này có bể bơi không?",
        )
        candidates = [
            ("short", "short-session", "Hotel"),
            ("hotel", "hotel-session", "Hotel Booking Agent"),
        ]
        self.assertEqual(
            _match_leading_mention(message, candidates),
            ("hotel", "hotel-session", "Hotel Booking Agent"),
        )
        stripped = _strip_leading_mention(message, "Hotel Booking Agent")
        self.assertEqual(
            stripped.get_text_content(),
            "khách sạn này có bể bơi không?",
        )
        self.assertTrue((message.get_text_content() or "").startswith("@"))

    async def test_invited_agent_accepts_plain_or_scoped_name(self) -> None:
        candidates = [
            ("hotel", "hotel-session", "Hotel Agent"),
            ("hotel", "hotel-session", "Hotel Agent@hotel"),
        ]

        plain = UserMsg(name="user", content="@Hotel Agent find a room")
        scoped = UserMsg(
            name="user",
            content="@Hotel Agent@hotel find a room",
        )

        self.assertEqual(_match_leading_mention(plain, candidates), candidates[0])
        self.assertEqual(_match_leading_mention(scoped, candidates), candidates[1])

    async def test_direct_mention_receives_prior_customer_ticket_context(
        self,
    ) -> None:
        current = UserMsg(
            name="user",
            content="@Hotel Booking Agent Tôi muốn ở khách sạn hơn 2 triệu",
        )
        context = build_customer_ticket_context(
            [
                UserMsg(
                    name="user",
                    content=(
                        "Tôi đi 17/10–18/10, một phòng đôi cho 2 người lớn, "
                        "ngân sách 10 triệu."
                    ),
                ),
                AssistantMsg(
                    name="Workforce Leader",
                    content="Mình sẽ tìm phương án phù hợp cho chuyến đi.",
                ),
                current,
            ],
            exclude_message_id=current.id,
        )

        self.assertIn("17/10–18/10", context)
        self.assertIn("2 người lớn", context)
        self.assertIn("10 triệu", context)
        self.assertNotIn("hơn 2 triệu", context)
