"""Opt-in real Jev + gpt-6-luna checks; tool definitions are never executed.

Run with BUILDER_LIVE_TEST=1, TYPESAFE_API_KEY, OPENAI_API_KEY and, if needed,
OPENAI_BASE_URL. Normal test runs never make paid provider calls.
"""

import os
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, skipUnless

from agentscope.app._router import _workforce_console as console
from agentscope.app.storage import ChatModelConfig
from agentscope.classifier import JevClassifierModel
from agentscope.credential import TypeSafeCredential


def hotel_tools():
    return [console.BuilderTool(
        id=f"hotel:{name}", mcp_id="hotel", mcp_name="Hotel", tool_name=name,
        description=description,
        input_schema={"type": "object", "properties": {"hotel_id": {"type": "string"}}},
    ) for name, description in [
        ("search_rooms", "Search available hotel rooms without creating a booking"),
        ("book_room", "Book an available hotel room and return a booking confirmation"),
        ("cancel_booking", "Cancel an existing hotel booking"),
        ("weather", "Look up weather forecasts"),
    ]]


@skipUnless(os.getenv("BUILDER_LIVE_TEST") == "1", "Opt-in paid model test")
class TestLiveJevToolEvidence(IsolatedAsyncioTestCase):
    async def test_omitted_requirements_and_user_negations(self):
        self.assertTrue(os.getenv("TYPESAFE_API_KEY"), "Set a valid TYPESAFE_API_KEY")
        jev = JevClassifierModel(TypeSafeCredential(api_key=os.environ["TYPESAFE_API_KEY"]),
                                 max_retries=0)
        requests = []
        try:
            for request, expected in [
                ("Tạo Hotel chỉ tìm phòng còn trống, không đặt phòng hay hủy đặt phòng.",
                 ["hotel:search_rooms"]),
                ("Bổ sung khả năng đặt phòng cho Hotel. Giữ tool tìm phòng, không thêm hủy đặt phòng.",
                 ["hotel:search_rooms", "hotel:book_room"]),
            ]:
                with self.subTest(request=request):
                    requests.append(request)
                    selected = await console._jev_resources(
                        jev, console.BuilderOutline(agents=[console.PlannedAgent(
                            name="Hotel", objective="Hỗ trợ khách sạn", tool_requirements=[],
                        )]), "The LLM omitted booking", hotel_tools(), [],
                        user_requests=requests,
                    )
                    self.assertEqual(selected.agents[0].suggested_tool_ids, expected)
        finally:
            await jev.client.aclose()


@skipUnless(os.getenv("BUILDER_LIVE_TEST") == "1", "Opt-in paid model test")
class TestLiveLunaToolFeedback(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.assertTrue(os.getenv("OPENAI_API_KEY"), "Set a Luna-capable OPENAI_API_KEY")
        credentials = {
            "luna": {"type": "openai_credential", "api_key": os.environ["OPENAI_API_KEY"],
                     "base_url": os.getenv("OPENAI_BASE_URL")},
            "jev": {"type": "typesafe_credential", "api_key": os.getenv("TYPESAFE_API_KEY", "")},
        }

        async def resolve(_user, credential_id):
            return SimpleNamespace(id=credential_id, data=credentials[credential_id])

        async def list_resources(_user, _kind):
            return [SimpleNamespace(id="jev", data=credentials["jev"])]

        self.access = SimpleNamespace(resolve_credential=resolve, list_resource=list_resources)
        self.config = ChatModelConfig(type="openai_credential", credential_id="luna",
                                      model="gpt-6-luna", parameters={"reasoning_effort": "low"})
        self.luna = await console.get_model("test", self.config, self.access)
        self.tools = hotel_tools()

    async def asyncTearDown(self):
        await self.luna.client.close()

    async def test_conversation_intents_do_not_guess_from_the_tool_catalog(self):
        previous = [console.PlannedAgentView(name="Hotel", objective="Tìm phòng khách sạn")]
        for message, history, current, intent in [
            ("tạo cho tôi 1 agent", "", [], "clarify"),
            ("Xin chào", "", [], "chat"),
            ("Giải thích sự khác nhau giữa tool và skill", "", previous, "chat"),
            ("Agent Hotel trong kế hoạch làm gì?", "", previous, "chat"),
            ("Tạo một agent tóm tắt văn bản tôi cung cấp", "", [], "plan"),
            ("Tóm tắt văn bản tôi cung cấp",
             "Customer: tạo cho tôi 1 agent\n\nBuilder: Bạn muốn agent hỗ trợ công việc gì?",
             [], "plan"),
        ]:
            with self.subTest(message=message):
                update, _, _ = await console._outline(
                    f"{history}\n\nCustomer: {message}", self.tools, self.luna, self.config,
                    current_plan=current, latest_message=message,
                )
                self.assertEqual(update.intent, intent)
                if intent == "plan":
                    self.assertEqual(len(update.agents), 1)
                    self.assertEqual(update.agents[0].tool_requirements, [])
                else:
                    self.assertTrue(update.assistant_message.strip())
                    self.assertEqual(update.agents, [])
                    self.assertEqual(update.removed_agent_names, [])

    async def test_correction_adds_booking_keeps_team_and_generates_the_approved_tools(self):
        self.assertTrue(os.getenv("TYPESAFE_API_KEY"), "Set a valid TYPESAFE_API_KEY")
        previous = [
            console.PlannedAgentView(name="Hotel", objective="Tìm phòng khách sạn còn trống",
                                     tool_requirements=["Search available hotel rooms"],
                                     suggested_tools=self.tools[:1]),
            console.PlannedAgentView(name="Planner", objective="Lập lịch trình từ kết quả của Hotel"),
        ]
        requests = [
            "Tạo Hotel để tìm phòng khách sạn và Planner để lập lịch trình từ kết quả của Hotel.",
            "Chọn thêm tool book_room cho Hotel. Giữ search_rooms và Planner; không thêm tool hủy phòng.",
        ]
        update, _, _ = await console._outline(
            "\n\n".join(requests), self.tools, self.luna, self.config,
            current_plan=previous, latest_message=requests[-1],
        )
        self.assertEqual(update.operation, "add_tools")
        retained, changed = console._apply_outline_update(update, previous)
        self.assertEqual(retained, previous[1:])
        selected, source = await console._select_builder_resources(
            console.BuilderOutline(agents=changed), "\n\n".join(requests), self.tools, [],
            self.luna, self.access, "test", user_requests=requests, preserved_agents=previous,
        )
        self.assertEqual(source, "jev", "This check must exercise Jev, not its LLM fallback")
        self.assertEqual(selected.agents[0].suggested_tool_ids,
                         ["hotel:search_rooms", "hotel:book_room"])
        plans = retained + [console.PlannedAgentView(
            name=agent.name, objective=agent.objective, tool_requirements=agent.tool_requirements,
            suggested_tools=[tool for tool in self.tools if tool.id in agent.suggested_tool_ids],
        ) for agent in selected.agents]
        generated, _, _ = await console._generate(
            "\n\n".join(requests), plans, self.luna, self.config, "vi",
        )
        self.assertEqual({agent.name for agent in generated.agents}, {"Hotel", "Planner"})
        hotel = next(agent for agent in generated.agents if agent.name == "Hotel")
        self.assertEqual(hotel.selected_tool_ids, ["hotel:search_rooms", "hotel:book_room"])

    async def test_four_existing_agents_plus_three_new_agents(self):
        previous = [console.PlannedAgentView(name=name, objective=objective)
                    for name, objective in [
                        ("Flights", "Tìm và đặt vé máy bay"),
                        ("Restaurants", "Tìm nhà hàng và đặt bàn"),
                        ("Hotel", "Tìm và đặt phòng khách sạn"),
                        ("Attractions", "Tìm địa điểm vui chơi"),
                    ]]
        latest = "Tạo thêm 3 agent nữa: quản lý ngân sách, lập lịch trình, tìm xe buýt. Giữ 4 agent cũ."
        update, _, _ = await console._outline(
            latest, self.tools, self.luna, self.config,
            current_plan=previous, latest_message=latest,
        )
        self.assertEqual(update.operation, "add")
        retained, changed = console._apply_outline_update(update, previous)
        self.assertEqual(retained, previous)
        self.assertEqual(len(retained) + len(changed), 7)
