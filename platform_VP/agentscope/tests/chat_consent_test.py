"""Chat decisions stay bound to stored calls, customer, and ticket."""

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from agentscope.app._chat_consent import (
    PendingChatAction,
    confirmation_still_pending,
    parse_chat_consent,
    pending_chat_actions,
    resolve_chat_consent,
)
from agentscope.app._router._chat import chat
from agentscope.app._router._schema._chat import ChatRequest
from agentscope.app.workforce.execution._router import chat_decision_body
from agentscope.app.workforce.execution._utils import ExecutionError
from agentscope.message import AssistantMsg, ToolCallBlock, ToolResultBlock, UserMsg
from agentscope.state import AgentState


class ChatConsentTests(IsolatedAsyncioTestCase):
    def setUp(self):
        self.call = ToolCallBlock(
            id="call-book-12345678",
            name="hotel_book",
            input='{"room":"double","amount":2000000}',
            state="asking",
        )
        self.action = PendingChatAction("worker", "worker-session", "reply", self.call)

    def test_only_unconditional_explicit_consent_is_accepted(self):
        for text in ("Tôi xác nhận", "Đồng ý.", "confirm", "yes"):
            self.assertEqual(parse_chat_consent(text), (True, None))
        for text in ("hủy", "không đồng ý", "cancel"):
            self.assertEqual(parse_chat_consent(text), (False, None))
        for text in (
            "đồng ý nhưng đổi ngày",
            "tôi chọn phương án 1",
            "yes if cheaper",
            "đừng xác nhận",
            "",
        ):
            self.assertIsNone(parse_chat_consent(text))

    def test_confirmation_replay_does_not_repeat_execution(self):
        _, event = resolve_chat_consent(
            UserMsg(name="user", content="xác nhận"), [self.action]
        )
        state = AgentState(
            reply_id="reply",
            context=[AssistantMsg(name="worker", id="reply", content=[self.call])],
        )
        self.assertTrue(confirmation_still_pending(state, event))
        state.context[-1].content.append(
            ToolResultBlock(
                id=self.call.id, name=self.call.name, state="success", output="booked"
            )
        )
        self.assertFalse(confirmation_still_pending(state, event))
        state.reply_id = "another-reply"
        self.assertFalse(confirmation_still_pending(state, event))

    def test_duplicate_actions_need_an_exact_reference(self):
        other = PendingChatAction(
            "other",
            "other-session",
            "reply2",
            self.call.model_copy(update={"id": "call-87654321"}),
        )
        self.assertIsNone(
            resolve_chat_consent(
                UserMsg(name="user", content="xác nhận"), [self.action, other]
            )
        )
        selected, event = resolve_chat_consent(
            UserMsg(name="user", content="xác nhận 12345678"), [self.action, other]
        )
        self.assertEqual(selected, self.action)
        self.assertEqual(event.confirm_results[0].tool_call.input, self.call.input)
        self.assertIsNone(event.confirm_results[0].rules)
        self.assertIsNone(
            resolve_chat_consent(
                UserMsg(name="user", content="xác nhận 00000000"), [self.action]
            )
        )
        self.assertIsNone(
            resolve_chat_consent(
                AssistantMsg(name="agent", content="xác nhận"), [self.action]
            )
        )

    async def test_pending_calls_are_scoped_and_resolved_results_are_excluded(self):
        state = AgentState(
            reply_id="reply",
            context=[AssistantMsg(name="agent", id="reply", content=[self.call])],
        )
        session = SimpleNamespace(id="sid", agent_id="agent", team_id=None, state=state)
        storage = SimpleNamespace(get_session=AsyncMock(return_value=session))
        self.assertEqual(
            len(await pending_chat_actions(storage, "u", "agent", "sid")), 1
        )
        storage.get_session.assert_awaited_once_with("u", "agent", "sid")
        state.context[0].content.append(
            ToolResultBlock(
                id=self.call.id, name=self.call.name, output="done", state="success"
            )
        )
        self.assertEqual(await pending_chat_actions(storage, "u", "agent", "sid"), [])
        storage.get_session.return_value = None
        self.assertEqual(
            await pending_chat_actions(storage, "other-user", "agent", "sid"), []
        )

    async def test_chat_routes_consent_to_worker_and_saves_the_user_message(self):
        storage = SimpleNamespace(upsert_message=AsyncMock(), get_session=AsyncMock(return_value=None))
        message = UserMsg(name="user", content="xác nhận 12345678")
        with (
            patch(
                "agentscope.app._router._chat.pending_chat_actions",
                AsyncMock(return_value=[self.action]),
            ),
            patch(
                "agentscope.app._router._chat.enqueue_run_trigger",
                AsyncMock(),
            ) as enqueue,
        ):
            response = await chat(
                ChatRequest(agent_id="leader", session_id="ticket", input=message),
                "user",
                object(),
                object(),
                object(),
                storage,
                object(),
            )
        self.assertEqual(response.session_id, "worker-session")
        storage.upsert_message.assert_awaited_once_with("user", "ticket", message)
        self.assertEqual(enqueue.await_args.kwargs["session_id"], "worker-session")
        self.assertTrue(
            enqueue.await_args.kwargs["inputs"].confirm_results[0].confirmed
        )

    async def test_ambiguous_chat_returns_a_persisted_question_without_execution(self):
        storage = SimpleNamespace(upsert_message=AsyncMock(), get_session=AsyncMock(return_value=None))
        with (
            patch(
                "agentscope.app._router._chat.pending_chat_actions",
                AsyncMock(return_value=[self.action]),
            ),
            patch(
                "agentscope.app._router._chat.enqueue_run_trigger",
                AsyncMock(),
            ) as enqueue,
        ):
            response = await chat(
                ChatRequest(
                    agent_id="leader",
                    session_id="ticket",
                    input=UserMsg(name="user", content="đổi ngày nhé"),
                ),
                "user",
                object(),
                object(),
                object(),
                storage,
                object(),
            )
        self.assertEqual(response.status, "awaiting_confirmation")
        self.assertIsNotNone(response.message)
        enqueue.assert_not_awaited()
        self.assertEqual(storage.upsert_message.await_count, 2)

    async def test_consent_without_pending_action_never_reaches_an_agent(self):
        storage = SimpleNamespace(upsert_message=AsyncMock(), get_session=AsyncMock(return_value=None))
        with (
            patch(
                "agentscope.app._router._chat.pending_chat_actions",
                AsyncMock(return_value=[]),
            ),
            patch(
                "agentscope.app._router._chat.enqueue_run_trigger",
                AsyncMock(),
            ) as enqueue,
        ):
            response = await chat(
                ChatRequest(
                    agent_id="leader",
                    session_id="ticket",
                    input=UserMsg(name="user", content="Xác nhận"),
                ),
                "user",
                object(),
                object(),
                object(),
                storage,
                object(),
            )

        self.assertEqual(response.status, "no_pending_confirmation")
        self.assertIn("không có thao tác nào", response.message.get_text_content())
        self.assertEqual(storage.upsert_message.await_count, 2)
        enqueue.assert_not_awaited()

    def test_partner_chat_preserves_all_binding_and_hash_fields(self):
        body = {
            "message": "xác nhận 12345678",
            "workflow_id": "w",
            "arguments_hash": "h",
            "expected_revision": 4,
        }
        self.assertEqual(
            chat_decision_body(body, "approval-12345678"),
            {
                "workflow_id": "w",
                "arguments_hash": "h",
                "expected_revision": 4,
                "decision": "approve",
            },
        )
        for message in ("xác nhận 87654321", "đồng ý nếu rẻ hơn"):
            with self.assertRaises(ExecutionError):
                chat_decision_body({**body, "message": message}, "approval-12345678")
        with self.assertRaises(ExecutionError):
            chat_decision_body({**body, "decision": "approve"}, "approval-12345678")
