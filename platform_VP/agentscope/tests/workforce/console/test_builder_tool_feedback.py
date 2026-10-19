"""Tool selection uses user evidence and supports additive tool corrections."""

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from agentscope.app._router import _workforce_console as console
from agentscope.classifier import BinaryAnswer
from tests.workforce.console import test_builder_resources as resources
from tests.workforce.console.test_builder_resources import (
    KBS, TOOLS, _Model, approved,
)


class TestBuilderToolFeedback(IsolatedAsyncioTestCase):
    async def test_jev_can_select_a_user_requested_tool_missing_from_llm_requirements(self):
        book = TOOLS[0].model_copy(update={
            "id": "travel:book", "tool_name": "book_room",
            "description": "Reserve an available hotel room",
        })
        outline = console.BuilderOutline(agents=[console.PlannedAgent(
            name="Hotel", objective="Help with hotels", tool_requirements=[],
        )])
        calls = []

        async def classify(*, state, questions):
            calls.append((state, questions))
            return SimpleNamespace(content={
                key: BinaryAnswer(0.95 if key == "tool_0_requested_1" else 0.05)
                for key in questions
            })

        selected = await console._jev_resources(
            classify, outline, "Builder suggested only browsing", [TOOLS[0], book], [],
            user_requests=["Tạo agent khách sạn", "Bổ sung khả năng đặt phòng"],
        )
        self.assertEqual(selected.agents[0].suggested_tool_ids, [book.id])
        state, questions = calls[0]
        self.assertEqual(state["latest_user_request"], "Bổ sung khả năng đặt phòng")
        self.assertNotIn("Builder suggested only browsing", str(state))
        self.assertIn("user_requests", questions["tool_0_requested_1"].instructions)

    async def test_tool_correction_keeps_existing_resources_and_other_tool_owners(self):
        previous = approved()
        previous.planned_agents[0].suggested_tools = TOOLS[1:]
        previous.planned_agents[1].tool_requirements = ["Search hotel rooms"]
        previous.planned_agents[1].peer_dependencies = ["Planner: verified itinerary"]
        update = console._BuilderOutlineUpdate(
            operation="add_tools", agents=[console.PlannedAgent(
                name="Hotel", objective="Search and book hotels",
                tool_requirements=["Book hotel rooms"],
            )],
        )
        retained, changed = console._apply_outline_update(update, previous.planned_agents)
        self.assertEqual(retained, previous.planned_agents[:1])
        self.assertEqual(changed[0].suggested_tool_ids, [TOOLS[0].id])
        self.assertEqual(changed[0].suggested_knowledge_base_ids, [KBS[0].id])
        self.assertEqual(changed[0].tool_requirements,
                         ["Search hotel rooms", "Book hotel rooms"])
        self.assertEqual(changed[0].peer_dependencies, ["Planner: verified itinerary"])
        async def classify(*, state, questions):
            return SimpleNamespace(content={key: BinaryAnswer(0.95) for key in questions})

        classifier_call = AsyncMock(side_effect=classify)
        classifier_call.client = SimpleNamespace(aclose=AsyncMock())
        book = TOOLS[0].model_copy(update={
            "id": "travel:book", "tool_name": "book_room",
            "description": "Book an available hotel room",
        })
        with patch.object(console, "_builder_classifier", AsyncMock(return_value=classifier_call)):
            selected, source = await console._select_builder_resources(
                console.BuilderOutline(agents=changed), "Add hotel weather lookup",
                [*TOOLS, book], KBS, _Model({}), object(), "user",
                user_requests=["Add hotel weather lookup"],
                preserved_agents=previous.planned_agents,
            )
        self.assertEqual(source, "jev")
        self.assertEqual(selected.agents[0].suggested_tool_ids, [TOOLS[0].id, book.id])
        self.assertEqual(selected.agents[0].suggested_knowledge_base_ids, [KBS[0].id])
        self.assertEqual(selected.agents[0].peer_dependencies, ["Planner: verified itinerary"])

    async def test_chat_tool_correction_returns_a_new_plan_and_keeps_the_team(self):
        previous = approved()
        previous.status = "ready"
        book = TOOLS[0].model_copy(update={
            "id": "travel:book", "tool_name": "book_room",
        })
        update = console._BuilderOutlineUpdate(operation="add_tools", agents=[
            console.PlannedAgent(name="Hotel", objective="Search and book hotels",
                                 tool_requirements=["Book hotel rooms"]),
        ])
        selected = console.BuilderOutline(agents=[console.PlannedAgent(
            name="Hotel", objective="Search and book hotels",
            tool_requirements=["Book hotel rooms"],
            suggested_tool_ids=[TOOLS[0].id, book.id],
        )])
        with patch.object(resources, "TOOLS", [*TOOLS, book]):
            result = await resources.TestBuilderResources._prepare(
                self, previous, _Model({}), confirm_outline=False, outline=update,
                selection=(selected, "jev"), message="Chọn thêm tool đặt phòng cho Hotel",
            )
        self.assertEqual(result.status, "needs_input")
        self.assertGreater(result.revision, previous.revision)
        self.assertEqual([agent.name for agent in result.planned_agents], ["Planner", "Hotel"])
        self.assertEqual(result.planned_agents[0], previous.planned_agents[0])
        self.assertEqual(result.planned_agents[1].suggested_knowledge_bases, KBS)
        self.assertEqual(result.planned_agents[1].suggested_tools, [TOOLS[0], book])
        self.assertEqual(result.agents, [])

    async def test_catalog_exposes_tool_argument_schema_to_jev(self):
        schema = {"type": "object", "properties": {"room_id": {"type": "string"}}}
        catalog = await console._catalog(SimpleNamespace(list_mcps=AsyncMock(return_value=[
            SimpleNamespace(id="travel", enabled=True, client=SimpleNamespace(name="Travel"),
                            discovered_tools=[{"name": "book", "description": "Book a room",
                                               "inputSchema": schema}]),
        ])), "user")
        self.assertEqual(catalog[0].input_schema, schema)

    def test_tool_correction_cannot_create_an_unknown_agent(self):
        with self.assertRaises(ValueError):
            console._apply_outline_update(console._BuilderOutlineUpdate(
                operation="add_tools", agents=[console.PlannedAgent(
                    name="Unknown", objective="Book hotel rooms",
                )],
            ), approved().planned_agents)

    def test_tool_correction_cannot_silently_omit_requested_operations(self):
        with self.assertRaises(ValueError):
            console._apply_outline_update(console._BuilderOutlineUpdate(
                operation="add_tools", agents=[console.PlannedAgent(
                    name="Hotel", objective="Book hotel rooms", tool_requirements=[],
                )],
            ), approved().planned_agents)
