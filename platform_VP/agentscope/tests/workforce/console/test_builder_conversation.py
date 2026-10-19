"""Builder conversation turns do not invent or overwrite agent proposals."""

import json
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from agentscope.app._router import _workforce_console as console
from agentscope.app.storage import SessionConfig, SessionRecord
from agentscope.message import AssistantMsg
from tests.workforce.console.test_builder_resources import CONFIG, TOOLS, _Model, approved


class TestBuilderConversation(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.messages = []
        self.model = _Model({})
        self.session = SessionRecord(
            id="builder", user_id="user", agent_id="workforce-builder",
            config=SessionConfig(workspace_id="builder", chat_model_config=CONFIG),
        )
        self.storage = SimpleNamespace(
            get_session=AsyncMock(return_value=self.session),
            list_messages=AsyncMock(side_effect=lambda *args, **kwargs: (list(self.messages), False)),
            upsert_message=AsyncMock(side_effect=lambda user, session, message: self.messages.append(message)),
            update_session_state=AsyncMock(),
            list_agents=AsyncMock(return_value=[]),
        )
        for name, result in [
            ("_builder_session", self.session), ("get_model", self.model),
            ("_catalog", TOOLS), ("_knowledge_catalog", []),
        ]:
            self.enterContext(patch.object(console, name, AsyncMock(return_value=result)))
        self.select = self.enterContext(patch.object(console, "_select_builder_resources", AsyncMock()))
        self.generate = self.enterContext(patch.object(console, "_generate", AsyncMock()))

    async def prepare(self, message, payload):
        self.model.payload = payload
        return await console.prepare_builder(
            console.PrepareRequest(message=message, chat_model_config=CONFIG),
            user_id="user", storage=self.storage, access=object(),
        )

    async def test_vague_creation_asks_without_selecting_tools_or_creating_a_plan(self):
        question = "Bạn muốn agent hỗ trợ công việc gì?"
        reply = await self.prepare("tạo cho tôi 1 agent", {
            "intent": "clarify", "assistant_message": question,
        })
        self.assertIsInstance(reply, console.BuilderConversationView)
        self.assertIsNone(reply.proposal)
        self.assertEqual([item.text for item in reply.messages], ["tạo cho tôi 1 agent", question])
        self.select.assert_not_awaited()
        self.generate.assert_not_awaited()
        self.storage.list_agents.assert_not_awaited()
        self.assertIsNone(console._stored_proposal(self.messages))

    async def test_chat_preserves_existing_proposals_and_survives_reload(self):
        for status in ["needs_input", "ready", "published"]:
            with self.subTest(status=status):
                proposal = approved().model_copy(update={"status": status})
                self.messages[:] = [AssistantMsg("builder", "Review plan", structured_output={
                    "workforce_builder_proposal": proposal.model_dump(),
                })]
                reply = await self.prepare("Giải thích sự khác nhau giữa tool và skill", {
                    "intent": "chat", "assistant_message": "Tool thực hiện thao tác; skill hướng dẫn cách làm.",
                })
                self.assertEqual(reply.proposal, proposal)
                restored = await console.get_builder_conversation("builder", "user", self.storage)
                self.assertEqual(restored, reply)
        self.select.assert_not_awaited()
        self.generate.assert_not_awaited()

    async def test_clarification_answer_continues_into_the_existing_planning_flow(self):
        await self.prepare("tạo cho tôi 1 agent", {
            "intent": "clarify", "assistant_message": "Bạn muốn agent hỗ trợ công việc gì?",
        })
        plan = console.BuilderOutline(agents=[console.PlannedAgent(
            name="Tóm tắt", objective="Tóm tắt văn bản người dùng cung cấp",
        )])
        self.select.return_value = (plan, "jev")
        result = await self.prepare("Tóm tắt văn bản tôi cung cấp", {
            "intent": "plan", **plan.model_dump(),
        })
        self.assertEqual(result.status, "needs_input")
        self.assertEqual([agent.name for agent in result.planned_agents], ["Tóm tắt"])
        self.select.assert_awaited_once()
        self.generate.assert_not_awaited()
        request = json.loads(self.model.calls[-1][0][-1].get_text_content())["request"]
        self.assertIn("tạo cho tôi 1 agent", request)
        self.assertIn("Bạn muốn agent hỗ trợ công việc gì?", request)
        self.assertEqual(console._stored_proposal(self.messages), result)

    async def test_greeting_is_a_persisted_conversation_without_a_proposal(self):
        reply = await self.prepare("Xin chào", {
            "intent": "chat", "assistant_message": "Chào bạn!",
        })
        self.assertIsNone(reply.proposal)
        self.assertEqual(reply.messages[-1].text, "Chào bạn!")
        self.select.assert_not_awaited()

    async def test_http_chat_reply_and_history_use_the_existing_conversation_contract(self):
        self.model.payload = {"intent": "clarify", "assistant_message": "Bạn muốn agent làm gì?"}
        app = FastAPI()
        app.include_router(console.workforce_console_router)

        async def user():
            return "user"

        async def storage():
            return self.storage

        async def access():
            return object()

        app.dependency_overrides.update({
            console.get_current_user_id: user,
            console.get_storage: storage,
            console.get_resource_access_service: access,
        })
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/workforce/console/builder/prepare", json={
                "message": "tạo cho tôi 1 agent", "chat_model_config": CONFIG.model_dump(),
            })
            self.assertEqual(response.status_code, 200)
            self.assertIsNone(response.json()["proposal"])
            self.assertEqual(response.json()["chat_model_config"], CONFIG.model_dump(mode="json"))
            self.assertEqual(response.json()["messages"][-1]["text"], "Bạn muốn agent làm gì?")
            restored = await client.get("/workforce/console/builder/conversations/builder")
            self.assertEqual(restored.status_code, 200)
            self.assertEqual(restored.json(), response.json())

    async def test_reload_keeps_a_proposal_older_than_the_visible_chat_page(self):
        proposal = approved()
        first = AssistantMsg("builder", "Review plan", structured_output={
            "workforce_builder_proposal": proposal.model_dump(),
        })
        recent = [AssistantMsg("builder", "Conversation") for _ in range(200)]
        self.storage.list_messages.side_effect = [(recent, True), ([first], False)]
        reply = await console.get_builder_conversation("builder", "user", self.storage)
        self.assertEqual(reply.proposal, proposal)
        self.assertEqual(len(reply.messages), 200)
        self.assertEqual(self.storage.list_messages.await_args.kwargs["before"], recent[0].id)

    def test_conversation_output_requires_text_and_cannot_mutate_agents(self):
        for payload in [
            {"intent": "chat"},
            {"intent": "clarify", "assistant_message": "  "},
            {"intent": "chat", "assistant_message": "Hello", "agents": [{"name": "Guessed", "objective": "Travel"}]},
            {"intent": "clarify", "assistant_message": "Which one?", "removed_agent_names": ["Hotel"]},
        ]:
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                console._BuilderOutlineUpdate.model_validate(payload)


class TestRecentUserRequests(IsolatedAsyncioTestCase):
    def test_selection_requests_are_bounded_and_keep_the_latest(self):
        from agentscope.message import UserMsg

        history = [UserMsg("user", f"yêu cầu {index} " + "x" * 2000) for index in range(20)]
        history.insert(3, AssistantMsg(name="agent_builder", content="trả lời"))
        requests = console._recent_user_requests(history, "yêu cầu mới nhất")
        self.assertEqual(requests[-1], "yêu cầu mới nhất")
        self.assertLessEqual(len(requests), console._SELECTION_REQUEST_LIMIT)
        self.assertLessEqual(sum(map(len, requests)), console._SELECTION_REQUEST_MAX_CHARS)
        self.assertNotIn("trả lời", requests)

    def test_one_long_latest_request_is_truncated_not_dropped(self):
        requests = console._recent_user_requests([], "y" * 9000)
        self.assertEqual(len(requests), 1)
        self.assertEqual(len(requests[0]), console._SELECTION_REQUEST_MAX_CHARS)
