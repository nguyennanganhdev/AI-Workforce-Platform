"""Builder selects resources once, then generates only approved instructions."""

import json
from copy import deepcopy
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from pydantic import ValidationError

from agentscope.app._router import _workforce_console as console
from agentscope.app.storage import (
    ChatModelConfig,
    SessionConfig,
    SessionRecord,
)
from agentscope.classifier import BinaryAnswer, BinaryQuestion
from agentscope.credential import CredentialFactory, TypeSafeCredential
from agentscope.mcp import HttpMCPConfig, MCPClient
from agentscope.message import AssistantMsg

TOOLS = [
    console.BuilderTool(
        id="travel:search",
        mcp_id="travel",
        mcp_name="travel",
        tool_name="search",
        description="Search available hotel rooms",
    ),
    console.BuilderTool(
        id="travel:unused",
        mcp_id="travel",
        mcp_name="travel",
        tool_name="unused",
        description="Weather forecast",
    ),
]
KBS = [
    console.BuilderKnowledgeBase(
        id="policy",
        name="Hotel policy",
        description="Hotel cancellation policies",
    )
]
CONFIG = ChatModelConfig(
    type="openai_credential", credential_id="chat", model="chat", parameters={}
)
OUTLINE = console.BuilderOutline(
    agents=[
        console.PlannedAgent(
            name="Planner",
            objective="Summarize verified results",
            knowledge_requirements=["Hotel policy"],
        ),
        console.PlannedAgent(
            name="Hotel",
            objective="Search hotel rooms",
            tool_requirements=["Search hotel rooms"],
            knowledge_requirements=["Hotel policy"],
        ),
    ]
)


def approved():
    return console.ProposalView(
        conversation_id="builder",
        revision=2,
        status="needs_input",
        assistant_message="Review plan",
        resources_locked=True,
        resource_selection="jev",
        chat_model_config=CONFIG,
        fixed_config={},
        planned_agents=[
            console.PlannedAgentView(
                name="Planner",
                objective=OUTLINE.agents[0].objective,
                suggested_knowledge_bases=KBS,
            ),
            console.PlannedAgentView(
                name="Hotel",
                objective=OUTLINE.agents[1].objective,
                suggested_tools=TOOLS[:1],
                suggested_knowledge_bases=KBS,
            ),
        ],
    )


class _Classifier:
    def __init__(self, *, probabilities=None, missing=False):
        self.calls = []
        self.client = SimpleNamespace(aclose=AsyncMock())
        self.missing = missing
        self.probabilities = probabilities or {}

    async def __call__(self, *, state, questions):
        self.calls.append((deepcopy(state), questions))
        answers = {}
        for key in questions:
            probability = 0.95
            if key.startswith("tool_"):
                probability = 0.95 if key == "tool_1_0_0" else 0.05
            if self.missing and key.startswith("tool_"):
                probability = 0.05
            answers[key] = BinaryAnswer(self.probabilities.get(key, probability))
        return SimpleNamespace(content=answers)


class _Model:
    context_size = 100_000

    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    async def count_tokens(self, *_):
        return 10

    async def generate_structured_output(self, messages, schema):
        self.calls.append((messages, schema))
        return SimpleNamespace(content=self.payload)


def generated():
    return {
        "agents": [
            {
                "name": agent.name,
                "system_prompt": "Use only equipped resources and verified peer results for the approved objective.",
                "skill_name": agent.name.lower(),
                "skill_markdown": "# Workflow\n\nFollow the approved objective and report verified results from equipped resources.",
            }
            for agent in approved().planned_agents
        ]
    }


class TestBuilderResources(IsolatedAsyncioTestCase):
    async def _select(self, outline, classifier, model, tools=TOOLS):
        with patch.object(
            console, "_builder_classifier", AsyncMock(return_value=classifier)
        ):
            return await console._select_builder_resources(
                outline, "Plan trip", tools, KBS, model, object(), "user"
            )

    async def test_jev_assigns_one_tool_owner_and_shares_kb(self):
        classifier = _Classifier()
        selected = await console._jev_resources(
            classifier, OUTLINE, "Plan trip", TOOLS, KBS
        )
        console._validate_resource_selection(selected, TOOLS, KBS)
        self.assertEqual(selected.agents[0].suggested_tool_ids, [])
        self.assertEqual(selected.agents[1].suggested_tool_ids, [TOOLS[0].id])
        self.assertEqual(
            [agent.suggested_knowledge_base_ids for agent in selected.agents],
            [["policy"], ["policy"]],
        )
        self.assertEqual(
            [agent.missing_resources for agent in selected.agents], [[], []]
        )
        self.assertEqual(len(classifier.calls), 1)
        self.assertEqual(OUTLINE.agents[1].suggested_tool_ids, [])
        questions = classifier.calls[0][1]
        self.assertIsInstance(questions["tool_1_0_0"], BinaryQuestion)
        self.assertNotIn("tool_0_0_0", questions)
        self.assertIn("Search hotel rooms", questions["tool_1_0_0"].instructions)

    async def test_jev_records_missing_capability(self):
        selected = await console._jev_resources(
            _Classifier(missing=True), OUTLINE, "Plan trip", TOOLS, KBS
        )
        self.assertEqual(
            selected.agents[1].missing_resources, ["tool: Search hotel rooms"]
        )

    async def test_shared_dispatch_is_a_peer_dependency_not_a_missing_tool(self):
        tools = [TOOLS[0].model_copy(update={
            "id": "building:dispatch", "tool_name": "dispatch_assign_staff",
            "description": "Dispatch staff to a dry meeting point",
        })]
        outline = console.BuilderOutline(agents=[
            console.PlannedAgent(
                name=name, objective=objective,
                tool_requirements=["Dispatch staff"],
            )
            for name, objective in (
                ("Security", "Dispatch staff for the building team"),
                ("Water", "Repair leaks using verified staff arrival receipts"),
                ("Electrical", "Test circuits using verified staff arrival receipts"),
            )
        ])
        selected, source = await self._select(
            outline,
            _Classifier(probabilities={
                "tool_0_0_0": 0.95, "tool_1_0_0": 0.9, "tool_2_0_0": 0.9,
            }),
            _Model({}), tools,
        )
        self.assertEqual(source, "jev")
        self.assertEqual(selected.agents[0].suggested_tool_ids, [tools[0].id])
        for agent in selected.agents[1:]:
            self.assertEqual(agent.suggested_tool_ids, [])
            self.assertEqual(agent.tool_requirements, [])
            self.assertEqual(agent.missing_resources, [])
            self.assertEqual(agent.peer_dependencies, ["Security: Dispatch staff"])
        self.assertEqual(outline.agents[1].tool_requirements, ["Dispatch staff"])

    async def test_large_catalog_batches_all_judgments_before_assigning_owners(self):
        tools = [TOOLS[0].model_copy(update={"id": f"building:{index}"}) for index in range(32)]
        outline = console.BuilderOutline(agents=[console.PlannedAgent(
            name=f"Specialist {index}", objective="Handle building incidents",
            tool_requirements=[f"Operation {requirement}" for requirement in range(8)],
        ) for index in range(4)])
        classifier = _Classifier(probabilities={
            "tool_0_0_0": 0.8, "tool_1_0_0": 0.05, "tool_3_7_0": 0.95,
        })

        async def classify(*, state, questions):
            if len(questions) > 64:
                raise ValueError("max_tokens_exceeded")
            return await classifier(state=state, questions=questions)

        selected = await console._jev_resources(classify, outline, "Building incidents", tools, [])
        console._validate_resource_selection(selected, tools, [])
        keys = [key for _, questions in classifier.calls for key in questions]
        self.assertEqual(len(keys), 1024)
        self.assertEqual(len(set(keys)), 1024)
        self.assertEqual(selected.agents[0].suggested_tool_ids, [])
        self.assertEqual(selected.agents[3].suggested_tool_ids, [tools[0].id])
        self.assertNotIn("tool: Operation 7", selected.agents[3].missing_resources)
        self.assertNotIn("tool: Operation 0", selected.agents[0].missing_resources)
        self.assertEqual(selected.agents[0].peer_dependencies, ["Specialist 3: Operation 0"])
        self.assertIn("tool: Operation 1", selected.agents[0].missing_resources)

    async def test_one_pass_matches_each_requirement_without_reverification(self):
        outline = OUTLINE.model_copy(deep=True)
        outline.agents[1].tool_requirements.append("Inspect room prices")
        classifier = _Classifier(probabilities={"tool_1_1_0": 0.65})
        selected = await console._jev_resources(
            classifier, outline, "Find rooms and prices", TOOLS, KBS
        )
        self.assertEqual(len(classifier.calls), 1)
        self.assertEqual(selected.agents[1].suggested_tool_ids, [TOOLS[0].id])
        self.assertEqual(selected.agents[1].missing_resources, [])
        state, questions = classifier.calls[0]
        self.assertEqual(state["tools"], [tool.model_dump() for tool in TOOLS])
        self.assertIn("Inspect room prices", questions["tool_1_1_0"].instructions)
        self.assertIn("'search'", questions["tool_1_1_0"].instructions)
        self.assertIn("another service/subject", questions["tool_1_1_0"].criteria.false)

    async def test_partial_selection_falls_back_and_keeps_accepted_tools(self):
        outline = OUTLINE.model_copy(deep=True)
        outline.agents[1].tool_requirements.append("Weather forecast")
        fallback = console.BuilderOutline(agents=[outline.agents[1].model_copy(deep=True)])
        fallback.agents[0].suggested_tool_ids = [tool.id for tool in TOOLS]
        model = _Model(fallback.model_dump())
        classifier = _Classifier()
        selected, source = await self._select(outline, classifier, model)
        self.assertEqual(source, "hybrid")
        self.assertEqual(selected.agents[1].suggested_tool_ids, [tool.id for tool in TOOLS])
        self.assertEqual(selected.agents[1].missing_resources, [])
        payload = json.loads(model.calls[0][0][-1].get_text_content())
        self.assertEqual(payload["outline"]["agents"][0]["suggested_tool_ids"], [TOOLS[0].id])
        self.assertIn("tool: Weather forecast", payload["outline"]["agents"][0]["missing_resources"])
        self.assertEqual(len(classifier.calls), 1)

    async def test_hotel_availability_does_not_cover_booking_requirement(self):
        tools = [
            console.BuilderTool(
                id="travel:check_hotel_availability", mcp_id="travel", mcp_name="travel",
                tool_name="check_hotel_availability", description="Check room inventory; does not reserve rooms.",
            ),
            console.BuilderTool(
                id="travel:book_hotel", mcp_id="travel", mcp_name="travel",
                tool_name="book_hotel", description="Create a confirmed hotel reservation.",
            ),
        ]
        outline = console.BuilderOutline(agents=[console.PlannedAgent(
            name="Hotel", objective="Check and book a hotel",
            tool_requirements=["Check room availability", "Create a hotel booking"],
        )])
        classifier = _Classifier(probabilities={"tool_0_0_0": 0.95})
        selected = await console._jev_resources(classifier, outline, "Book hotel", tools, [])
        self.assertEqual(selected.agents[0].suggested_tool_ids, [tools[0].id])
        self.assertEqual(selected.agents[0].missing_resources, ["tool: Create a hotel booking"])
        fallback = outline.model_copy(deep=True)
        fallback.agents[0].suggested_tool_ids = [tool.id for tool in tools]
        selected, source = await self._select(outline, classifier, _Model(fallback.model_dump()), tools)
        self.assertEqual(source, "hybrid")
        self.assertEqual(selected.agents[0].suggested_tool_ids, [tool.id for tool in tools])
        self.assertEqual(selected.agents[0].missing_resources, [])

    async def test_partial_fallback_cannot_drop_or_transfer_accepted_tools(self):
        outline = OUTLINE.model_copy(deep=True)
        outline.agents[0].tool_requirements = ["Weather forecast"]
        outline.agents[1].tool_requirements.append("Weather forecast")
        for ids in ([], [TOOLS[1].id]):
            with self.subTest(ids=ids):
                fallback = outline.model_copy(deep=True)
                fallback.agents[0].suggested_tool_ids = ids
                fallback.agents[1].suggested_tool_ids = []
                with self.assertRaises(HTTPException) as error:
                    await self._select(outline, _Classifier(), _Model(fallback.model_dump()))
                self.assertEqual(error.exception.status_code, 502)

    async def test_unavailable_route_stays_missing_despite_other_selected_tool(self):
        outline = console.BuilderOutline(agents=[console.PlannedAgent(
            name="Travel", objective="Search rooms and plan travel",
            tool_requirements=["Search hotel rooms", "Route between arbitrary addresses"],
        )])
        fallback = outline.model_copy(deep=True)
        fallback.agents[0].suggested_tool_ids = [TOOLS[0].id]
        fallback.agents[0].missing_resources = ["tool: Route between arbitrary addresses"]
        selected, source = await self._select(
            outline, _Classifier(probabilities={"tool_0_0_0": 0.95}),
            _Model(fallback.model_dump()),
        )
        self.assertEqual(source, "hybrid")
        self.assertEqual(selected.agents[0].suggested_tool_ids, [TOOLS[0].id])
        self.assertEqual(selected.agents[0].missing_resources, fallback.agents[0].missing_resources)

    async def test_requirements_without_candidates_stay_missing_without_jev_call(self):
        classifier = _Classifier()
        selected = await console._jev_resources(classifier, OUTLINE, "Find rooms", [], [])
        self.assertEqual(classifier.calls, [])
        self.assertIn("tool: Search hotel rooms", selected.agents[1].missing_resources)
        self.assertIn("knowledge: Hotel policy", selected.agents[1].missing_resources)

    async def test_tool_need_accepts_probability_at_or_above_point_six(self):
        for confidence in (0.6, 0.75):
            with self.subTest(confidence=confidence):
                selected = await console._jev_resources(
                    _Classifier(probabilities={"tool_1_0_0": confidence}),
                    OUTLINE, "Plan trip", TOOLS, KBS,
                )
                self.assertEqual(selected.agents[1].suggested_tool_ids, [TOOLS[0].id])

    async def test_tool_need_skips_probability_below_point_six(self):
        for probability in (0.5, 0.599):
            selected = await console._jev_resources(
                _Classifier(probabilities={"tool_1_0_0": probability}),
                OUTLINE, "Plan trip", TOOLS, KBS,
            )
            self.assertEqual(selected.agents[1].suggested_tool_ids, [])

    async def test_uncertain_excluded_tool_keeps_jev_selection(self):
        classifier = _Classifier(probabilities={"tool_1_0_1": 0.5})
        model = _Model({})
        with (
            patch.object(
                console, "_builder_classifier", AsyncMock(return_value=classifier)
            ),
            self.assertLogs(console.logger, level="INFO") as logs,
        ):
            selected, source = await console._select_builder_resources(
                OUTLINE, "Plan trip", TOOLS, KBS, model, object(), "user"
            )
        self.assertEqual(source, "jev")
        self.assertEqual(selected.agents[1].suggested_tool_ids, [TOOLS[0].id])
        self.assertEqual(len(classifier.calls), 1)
        self.assertEqual(model.calls, [])
        classifier.client.aclose.assert_awaited_once()
        for message in (
            "selection request", "selection response received",
            "source=jev",
        ):
            self.assertIn(message, "\n".join(logs.output))

    async def test_excluded_tool_still_requires_valid_confidence(self):
        for confidence in (-0.1, 1.1, float("nan")):
            with self.subTest(confidence=confidence), self.assertRaisesRegex(
                ValueError, "Invalid resource judgment"
            ):
                await console._jev_resources(
                    _Classifier(probabilities={"tool_1_0_1": confidence}),
                    OUTLINE, "Plan trip", TOOLS, KBS,
                )

    async def test_uncertain_excluded_tool_still_checks_required_coverage(self):
        outline = OUTLINE.model_copy(deep=True)
        outline.agents[1].tool_requirements.append("Weather forecast")
        selected = await console._jev_resources(
            _Classifier(probabilities={"tool_1_0_1": 0.5}, missing=True),
            outline, "Plan trip with weather", TOOLS, KBS,
        )
        self.assertIn("tool: Weather forecast", selected.agents[1].missing_resources)

    async def test_missing_credential_logs_llm_fallback(self):
        with (
            patch.object(
                console, "_builder_classifier", AsyncMock(return_value=None)
            ),
            self.assertLogs(console.logger, level="INFO") as logs,
        ):
            _, source = await console._select_builder_resources(
                OUTLINE, "Plan trip", TOOLS, KBS,
                _Model(OUTLINE.model_dump()), object(), "user",
            )
        self.assertEqual(source, "llm")
        self.assertIn("no visible TypeSafe credential", "\n".join(logs.output))
        self.assertIn("source=llm", "\n".join(logs.output))

    async def test_empty_agent_falls_back_without_changing_peer_or_kbs(
        self,
    ):
        fallback = console.BuilderOutline(agents=[OUTLINE.agents[1].model_copy(deep=True)])
        fallback.agents[0].suggested_tool_ids = [TOOLS[0].id]
        classifier = _Classifier(probabilities={"tool_1_0_0": 0.5})
        model = _Model(fallback.model_dump())
        with (
            patch.object(
                console, "_builder_classifier", AsyncMock(return_value=classifier)
            ),
            self.assertLogs(console.logger, level="INFO") as logs,
        ):
            selected, source = await console._select_builder_resources(
                OUTLINE, "Plan trip", TOOLS, KBS, model, object(), "user"
            )
        self.assertEqual(source, "hybrid")
        self.assertEqual(selected.agents[1].suggested_tool_ids, [TOOLS[0].id])
        self.assertEqual(selected.agents[0].suggested_tool_ids, [])
        self.assertEqual(
            [agent.suggested_knowledge_base_ids for agent in selected.agents],
            [["policy"], ["policy"]],
        )
        self.assertNotIn("tool: Search hotel rooms", selected.agents[1].missing_resources)
        classifier.client.aclose.assert_awaited_once()
        self.assertEqual(len(model.calls), 1)
        self.assertIn("reason=unmet_tool_requirements", "\n".join(logs.output))
        self.assertIn("source=hybrid", "\n".join(logs.output))
        payload = json.loads(model.calls[0][0][-1].get_text_content())
        self.assertEqual(len(payload["outline"]["agents"]), 1)
        self.assertEqual(payload["outline"]["agents"][0]["name"], "Hotel")

    async def test_shared_tool_goes_to_highest_probability_with_stable_ties(self):
        outline = OUTLINE.model_copy(deep=True)
        outline.agents[0].tool_requirements = ["Search hotel rooms"]
        for first, second, owner in ((0.7, 0.9, 1), (0.9, 0.7, 0), (0.8, 0.8, 0)):
            with self.subTest(first=first, second=second):
                selected = await console._jev_resources(
                    _Classifier(probabilities={
                        "tool_0_0_0": first, "tool_1_0_0": second,
                    }),
                    outline, "Plan trip", TOOLS, KBS,
                )
                console._validate_resource_selection(selected, TOOLS, KBS)
                self.assertEqual(selected.agents[owner].suggested_tool_ids, [TOOLS[0].id])
                self.assertEqual(selected.agents[1 - owner].suggested_tool_ids, [])
                dependent = selected.agents[1 - owner]
                self.assertNotIn("tool: Search hotel rooms", dependent.missing_resources)
                self.assertEqual(dependent.peer_dependencies, [
                    f"{selected.agents[owner].name}: Search hotel rooms",
                ])

    async def test_peer_dependency_survives_fallback_for_a_different_missing_tool(self):
        outline = OUTLINE.model_copy(deep=True)
        outline.agents[0].tool_requirements = ["Search hotel rooms", "Weather forecast"]
        fallback = console.BuilderOutline(agents=[outline.agents[0].model_copy(deep=True)])
        fallback.agents[0].tool_requirements = ["Weather forecast"]
        fallback.agents[0].suggested_tool_ids = [TOOLS[1].id]
        selected, source = await self._select(
            outline, _Classifier(probabilities={"tool_0_0_0": 0.9}),
            _Model(fallback.model_dump()),
        )
        self.assertEqual(source, "hybrid")
        self.assertEqual(selected.agents[0].peer_dependencies, ["Hotel: Search hotel rooms"])
        self.assertEqual(selected.agents[0].suggested_tool_ids, [TOOLS[1].id])
        self.assertEqual(selected.agents[0].missing_resources, [])

    async def test_agent_fallback_cannot_change_accepted_peer_tools(self):
        outline = OUTLINE.model_copy(deep=True)
        outline.agents.append(console.PlannedAgent(
            name="Weather", objective="Forecast weather",
            tool_requirements=["Weather forecast"],
        ))
        fallback = console.BuilderOutline(agents=[outline.agents[2].model_copy(deep=True)])
        fallback.agents[0].suggested_tool_ids = [TOOLS[1].id]
        model = _Model(fallback.model_dump())
        selected, source = await self._select(outline, _Classifier(), model)
        self.assertEqual(source, "hybrid")
        self.assertEqual(selected.agents[1].suggested_tool_ids, [TOOLS[0].id])
        self.assertEqual(selected.agents[2].suggested_tool_ids, [TOOLS[1].id])
        self.assertEqual(len(model.calls), 1)
        payload = json.loads(model.calls[0][0][-1].get_text_content())
        self.assertEqual([tool["id"] for tool in payload["tools"]], [TOOLS[1].id])
        self.assertEqual(payload["outline"]["agents"][0]["name"], "Weather")

    async def test_agent_fallback_rejects_claimed_peer_tool(self):
        outline = OUTLINE.model_copy(deep=True)
        outline.agents[0].tool_requirements = ["Search hotel rooms"]
        fallback = console.BuilderOutline(agents=[outline.agents[0].model_copy(deep=True)])
        fallback.agents[0].suggested_tool_ids = [TOOLS[0].id]
        with self.assertRaises(HTTPException) as error:
            await self._select(outline, _Classifier(), _Model(fallback.model_dump()))
        self.assertEqual(error.exception.status_code, 502)

    async def test_no_free_tools_reports_missing_without_llm(self):
        outline = OUTLINE.model_copy(deep=True)
        outline.agents[0].tool_requirements = ["Search hotel rooms"]
        model = _Model({})
        selected, source = await self._select(outline, _Classifier(), model, TOOLS[:1])
        self.assertEqual(source, "jev")
        self.assertIn("tool: Search hotel rooms", selected.agents[0].missing_resources)
        self.assertEqual(model.calls, [])

    async def test_empty_agents_share_one_fallback_with_exclusive_tools(self):
        outline = OUTLINE.model_copy(deep=True)
        outline.agents[0].tool_requirements = ["Weather forecast"]
        fallback = outline.model_copy(deep=True)
        for index, tool in ((0, TOOLS[1]), (1, TOOLS[0])):
            fallback.agents[index].suggested_tool_ids = [tool.id]
        model = _Model(fallback.model_dump())
        selected, source = await self._select(
            outline, _Classifier(probabilities={"tool_1_0_0": 0.5}), model,
        )
        self.assertEqual(source, "hybrid")
        self.assertEqual(selected.agents[0].suggested_tool_ids, [TOOLS[1].id])
        self.assertEqual(selected.agents[1].suggested_tool_ids, [TOOLS[0].id])
        self.assertEqual(len(model.calls), 1)
        payload = json.loads(model.calls[0][0][-1].get_text_content())
        self.assertEqual(len(payload["outline"]["agents"]), 2)
        self.assertEqual([tool["id"] for tool in payload["tools"]], [tool.id for tool in TOOLS])

    async def test_uncertain_knowledge_preserves_selected_tools(self):
        model = _Model({})
        selected, source = await self._select(
            OUTLINE, _Classifier(probabilities={"knowledge_1_0_0": 0.5}), model,
        )
        self.assertEqual(source, "jev")
        self.assertEqual(selected.agents[1].suggested_tool_ids, [TOOLS[0].id])
        self.assertIn("knowledge: Hotel policy", selected.agents[1].missing_resources)
        self.assertEqual(model.calls, [])

    async def test_context_only_agent_does_not_fall_back(self):
        outline = console.BuilderOutline(agents=[console.PlannedAgent(
            name="Summary", objective="Summarize supplied text",
        )])
        model = _Model({})
        selected, source = await self._select(outline, _Classifier(), model)
        self.assertEqual(source, "jev")
        self.assertEqual(selected.agents[0].suggested_tool_ids, [])
        self.assertEqual(model.calls, [])

    async def test_jev_service_failure_falls_back(self):
        classifier = AsyncMock(side_effect=TimeoutError())
        classifier.client.aclose = AsyncMock()
        model = _Model(OUTLINE.model_dump())
        with patch.object(
            console, "_builder_classifier", AsyncMock(return_value=classifier)
        ):
            selected, source = await console._select_builder_resources(
                OUTLINE, "Plan trip", TOOLS, KBS, model, object(), "user"
            )
        self.assertEqual(source, "llm")
        self.assertIn(
            "tool: Search hotel rooms", selected.agents[1].missing_resources
        )

    async def test_no_resources_does_not_call_jev_for_empty_candidates(self):
        outline = console.BuilderOutline(
            agents=[
                {"name": "Summary", "objective": "Summarize supplied text"}
            ]
        )
        classifier = AsyncMock()
        selected = await console._jev_resources(
            classifier, outline, "Summarize", [], []
        )
        classifier.assert_not_awaited()
        self.assertEqual(selected.agents[0].missing_resources, [])

    def test_duplicate_tools_and_invented_ids_are_rejected(self):
        for ids in ([TOOLS[0].id], ["invented"]):
            outline = OUTLINE.model_copy(deep=True)
            outline.agents[0].suggested_tool_ids = [TOOLS[0].id]
            outline.agents[1].suggested_tool_ids = ids
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                console._validate_resource_selection(outline, TOOLS, KBS)

    async def test_generation_uses_only_approved_resources_and_keeps_skill(
        self,
    ):
        model = _Model(generated())
        result, _, _ = await console._generate(
            "Plan trip", approved().planned_agents, model, CONFIG, "vi"
        )
        self.assertEqual(result.agents[0].selected_tool_ids, [])
        self.assertEqual(result.agents[0].execution_mode, "context_only")
        self.assertEqual(result.agents[1].selected_tool_ids, [TOOLS[0].id])
        self.assertEqual(
            result.agents[1].selected_knowledge_base_ids, ["policy"]
        )
        self.assertTrue(result.agents[1].skill_markdown)
        messages, schema = model.calls[0]
        fields = schema.model_json_schema()["$defs"]["_GeneratedAgentConfig"][
            "properties"
        ]
        self.assertEqual(
            set(fields),
            {"name", "system_prompt", "skill_name", "skill_markdown"},
        )
        payload = json.loads(messages[-1].get_text_content())
        self.assertNotIn(TOOLS[1].id, str(payload))
        self.assertEqual(
            payload["approved_plan"][1]["suggested_tools"][0]["id"],
            TOOLS[0].id,
        )

    async def test_generation_timeout_counts_only_new_agents(self):
        for reuse, expected_timeout in ((False, 120), (True, 60)):
            plans = approved().planned_agents
            payload = generated()
            if reuse:
                plans[0].reuse_agent_id = "existing"
                payload["agents"] = payload["agents"][1:]
            with self.subTest(reuse=reuse), patch.object(
                console.asyncio, "timeout", wraps=console.asyncio.timeout
            ) as timeout:
                await console._generate("Plan trip", plans, _Model(payload), CONFIG, "vi")
                timeout.assert_called_once_with(expected_timeout)

    async def test_generation_timeout_reports_the_actual_team_budget(self):
        model = _Model({})
        model.generate_structured_output = AsyncMock(side_effect=TimeoutError())
        with self.assertRaises(HTTPException) as error:
            await console._generate("Plan trip", approved().planned_agents, model, CONFIG, "vi")
        self.assertIn("120 giây", error.exception.detail)

    async def test_generation_cannot_add_or_rename_agents(self):
        payload = generated()
        payload["agents"][0]["name"] = "Unexpected"
        with self.assertRaises(HTTPException) as error:
            await console._generate(
                "Plan trip",
                approved().planned_agents,
                _Model(payload),
                CONFIG,
                "vi",
            )
        self.assertEqual(error.exception.status_code, 502)
        with self.assertRaises(ValidationError):
            console._GeneratedAgentConfig.model_validate(
                {**generated()["agents"][0], "selected_tool_ids": ["invented"]}
            )

    def test_stale_resources_and_missing_resources_block_confirmation(self):
        cases = [(TOOLS[1:], KBS, approved()), (TOOLS, [], approved())]
        missing = approved()
        missing.planned_agents[1].missing_resources = ["Need tool"]
        cases.append((TOOLS, KBS, missing))
        for tools, kbs, proposal in cases:
            with (
                self.subTest(proposal=proposal),
                self.assertRaises(HTTPException) as error,
            ):
                console._check_approved_resources(proposal, tools, kbs)
            self.assertEqual(error.exception.status_code, 409)

    async def _prepare(
        self,
        previous,
        model,
        *,
        expected_revision=2,
        confirm_outline=True,
        selection=None,
        existing=(),
        classifier=None,
        outline=OUTLINE,
        message="Confirm",
    ):
        storage = SimpleNamespace(
            upsert_message=AsyncMock(), list_agents=AsyncMock(return_value=list(existing)),
            get_agent=AsyncMock(side_effect=lambda user_id, agent_id: next((record for record in existing if record.id == agent_id), None)),
        )
        session = SessionRecord(
            id="builder",
            user_id="user",
            agent_id="workforce-builder",
            config=SessionConfig(workspace_id="builder"),
        )
        messages = [
            AssistantMsg(
                "builder",
                "Review plan",
                structured_output={
                    "workforce_builder_proposal": previous.model_dump()
                },
            )
        ]
        with (
            patch.object(
                console, "_builder_session", AsyncMock(return_value=session)
            ),
            patch.object(
                console,
                "_list_all_builder_messages",
                AsyncMock(return_value=messages),
            ),
            patch.object(console, "_catalog", AsyncMock(return_value=TOOLS)),
            patch.object(
                console, "_knowledge_catalog", AsyncMock(return_value=KBS)
            ),
            patch.object(console, "get_model", AsyncMock(return_value=model)),
            patch.object(
                console,
                "_prepare_builder_memory",
                AsyncMock(return_value="Plan trip"),
            ),
            patch.object(
                console, "_record_builder_prompt_measurement", AsyncMock()
            ),
            patch.object(
                console, "_outline", AsyncMock(return_value=(outline, 10, 10))
            ),
            patch.object(
                console,
                "_select_builder_resources",
                AsyncMock(return_value=deepcopy(selection)),
            ) as select,
            patch.object(console, "_builder_classifier", AsyncMock(return_value=classifier)),
        ):
            result = await console.prepare_builder(
                console.PrepareRequest(
                    message=message,
                    conversation_id="builder",
                    confirm_outline=confirm_outline,
                    expected_revision=expected_revision,
                    chat_model_config=CONFIG,
                ),
                user_id="user",
                storage=storage,
                access=object(),
            )
        if confirm_outline or all(agent.reuse_agent_id for agent in result.planned_agents):
            select.assert_not_awaited()
        else:
            select.assert_awaited_once()
            reserved = {tool.id for agent in result.planned_agents if agent.reuse_agent_id for tool in agent.suggested_tools}
            self.assertTrue(reserved.isdisjoint(tool.id for tool in select.await_args.args[2]))
            self.assertTrue(all(not agent.reuse_agent_id for agent in select.await_args.args[0].agents))
        return result

    async def test_preview_saves_selection_and_shows_missing_resources(self):
        selected = OUTLINE.model_copy(deep=True)
        selected.agents[1].suggested_tool_ids = [TOOLS[0].id]
        selected.agents[1].missing_resources = ["knowledge: Hotel policy"]
        selected.agents[1].peer_dependencies = ["Planner: Summarize verified results"]
        result = await self._prepare(
            approved(),
            _Model({}),
            confirm_outline=False,
            selection=(selected, "jev"),
        )
        self.assertEqual(result.status, "needs_input")
        self.assertTrue(result.resources_locked)
        self.assertEqual(result.resource_selection, "jev")
        self.assertEqual(result.planned_agents[1].suggested_tools, TOOLS[:1])
        self.assertEqual(
            result.planned_agents[1].missing_resources,
            ["knowledge: Hotel policy"],
        )
        self.assertEqual(result.planned_agents[1].peer_dependencies,
                         ["Planner: Summarize verified results"])

    async def test_saved_trials_restore_code_checks_without_changing_messages(self):
        proposal = await self._prepare(approved(), _Model(generated()))
        for status, configuration_passed, expected in (
            ("evaluating", True, "ready"),
            ("blocked", True, "ready"),
            ("blocked", False, "blocked"),
            ("published", True, "published"),
        ):
            with self.subTest(status=status, configuration_passed=configuration_passed):
                payload = proposal.model_dump(mode="json")
                payload["status"] = status
                payload["evaluation_request"] = "Previous trial request"
                for agent in payload["agents"]:
                    agent["evaluation"].update(
                        passed=False,
                        configuration_passed=configuration_passed,
                        behavior={"status": "failed", "passed": False},
                    )
                message = AssistantMsg(
                    "builder", "Generated",
                    structured_output={"workforce_builder_proposal": payload},
                )
                restored = console._stored_proposal([message])
                self.assertEqual(restored.status, expected)
                for agent in restored.agents:
                    self.assertEqual(agent.evaluation["passed"], configuration_passed)
                    self.assertNotIn("behavior", agent.evaluation)
                    self.assertNotIn("configuration_passed", agent.evaluation)
                self.assertNotIn("evaluation_request", restored.model_dump())
                self.assertEqual(payload["status"], status)
                self.assertIn("behavior", payload["agents"][0]["evaluation"])

    async def test_preview_persists_hybrid_source(self):
        result = await self._prepare(
            approved(), _Model({}), confirm_outline=False,
            selection=(OUTLINE, "hybrid"),
        )
        restored = console.ProposalView.model_validate_json(result.model_dump_json())
        self.assertEqual(restored.resource_selection, "hybrid")
        self.assertTrue(restored.resources_locked)

    async def test_outline_grounds_needs_in_available_mcp_capabilities(self):
        model = _Model(OUTLINE.model_dump())
        result, _, _ = await console._outline(
            "Plan trip", TOOLS, model, CONFIG
        )
        self.assertEqual(
            result.agents[1].tool_requirements, ["Search hotel rooms"]
        )
        payload = json.loads(model.calls[0][0][-1].get_text_content())
        self.assertEqual(payload["request"], "Plan trip")
        self.assertEqual(payload["tools"], [tool.model_dump() for tool in TOOLS])
        instructions = model.calls[0][0][0].get_text_content()
        self.assertIn("only team-management role", instructions)
        self.assertIn("Do not propose another Leader", instructions)
        self.assertIn("Each MCP tool must have one specialist owner", instructions)
        self.assertIn("Do not repeat that\ntool requirement on each peer", instructions)
        self.assertIn("do not add hypothetical databases", instructions)
        self.assertIn("user explicitly requests an unavailable operation", instructions)

    async def test_classifier_resolves_visible_credentials_without_exposing_secret(
        self,
    ):
        access = SimpleNamespace(
            list_resource=AsyncMock(
                return_value=[
                    SimpleNamespace(
                        id="typesafe", data={"type": "typesafe_credential"}
                    )
                ]
            ),
            resolve_credential=AsyncMock(
                return_value=SimpleNamespace(
                    data=TypeSafeCredential(api_key="test-secret").model_dump()
                )
            ),
        )
        with patch.object(console, "JevClassifierModel") as factory:
            await console._builder_classifier(access, "viewer")
        access.resolve_credential.assert_awaited_once_with(
            "viewer", "typesafe"
        )
        self.assertEqual(
            factory.call_args.args[0].api_key.get_secret_value(), "test-secret"
        )

    async def test_confirmation_loads_saved_plan_without_rerunning_selection(
        self,
    ):
        previous = approved()
        result = await self._prepare(previous, _Model(generated()))
        self.assertEqual(result.status, "ready")
        self.assertEqual(result.revision, 3)
        self.assertTrue(result.resources_locked)
        self.assertEqual(result.planned_agents, previous.planned_agents)
        self.assertEqual(result.agents[1].selected_tools, TOOLS[:1])

    async def test_stale_confirmation_does_not_call_generation(self):
        model = _Model(generated())
        with self.assertRaises(HTTPException) as error:
            await self._prepare(approved(), model, expected_revision=1)
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(model.calls, [])

    async def test_missing_kb_allows_generation_and_publication(self):
        previous = approved()
        for agent in previous.planned_agents:
            agent.suggested_knowledge_bases = []
            agent.missing_resources = ["knowledge: Hotel policy"]
        model = _Model(generated())
        proposal = await self._prepare(previous, model)
        self.assertEqual(proposal.status, "ready")
        self.assertTrue(
            all(
                not agent.selected_knowledge_bases for agent in proposal.agents
            )
        )
        self.assertEqual(
            proposal.planned_agents[1].missing_resources,
            ["knowledge: Hotel policy"],
        )
        self.assertIn(
            "Missing knowledge bases", model.calls[0][0][0].get_text_content()
        )
        storage = SimpleNamespace(
            get_session=AsyncMock(return_value=object()),
            list_messages=AsyncMock(
                return_value=(
                    [
                        AssistantMsg(
                            "builder",
                            "Generated",
                            structured_output={
                                "workforce_builder_proposal": proposal.model_dump(),
                            },
                        ),
                    ],
                    False,
                )
            ),
            get_mcp=AsyncMock(
                return_value=SimpleNamespace(
                    enabled=True,
                    client=MCPClient(
                        name="travel",
                        is_stateful=False,
                        mcp_config=HttpMCPConfig(
                            url="https://example.test/mcp"
                        ),
                    ),
                )
            ),
            upsert_agent=AsyncMock(),
            upsert_message=AsyncMock(),
        )
        workspace = SimpleNamespace(
            default_mcps=[],
            add_mcp=AsyncMock(),
            add_skill_archive=AsyncMock(),
        )
        primary = SessionRecord(
            id="primary",
            user_id="user",
            agent_id="new-agent",
            config=SessionConfig(workspace_id="workspace"),
        )
        with (
            patch.object(console, "_catalog", AsyncMock(return_value=TOOLS)),
            patch.object(
                console, "_knowledge_catalog", AsyncMock(return_value=[])
            ),
            patch.object(
                console, "_primary_session", AsyncMock(return_value=primary)
            ),
        ):
            result = await console.publish_builder(
                console.PublishRequest(
                    conversation_id="builder",
                    proposal_id=proposal.proposal_id,
                    expected_revision=proposal.revision,
                    knowledge_base_selections=[[], []],
                ),
                user_id="user",
                storage=storage,
                access=object(),
                workspace_manager=SimpleNamespace(
                    get_workspace=AsyncMock(return_value=workspace)
                ),
            )
        self.assertEqual(len(result.agents), 2)
        self.assertEqual(workspace.add_skill_archive.await_count, 2)
        for call in storage.upsert_agent.await_args_list:
            self.assertEqual(call.args[1].data.knowledge_base_ids, [])
            self.assertTrue(call.args[1].data.generated_skill)

    async def test_missing_tool_still_blocks_when_kb_is_also_missing(self):
        previous = approved()
        previous.planned_agents[1].missing_resources = [
            "knowledge: Hotel policy",
            "tool: Search hotel rooms",
        ]
        model = _Model(generated())
        with self.assertRaises(HTTPException) as error:
            await self._prepare(previous, model)
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(model.calls, [])

    async def test_publication_rejects_kb_change_after_generation(self):
        proposal = await self._prepare(approved(), _Model(generated()))
        storage = SimpleNamespace(
            get_session=AsyncMock(return_value=object()),
            list_messages=AsyncMock(
                return_value=(
                    [
                        AssistantMsg(
                            "builder",
                            "Generated",
                            structured_output={
                                "workforce_builder_proposal": proposal.model_dump()
                            },
                        )
                    ],
                    False,
                )
            ),
            upsert_agent=AsyncMock(),
        )
        with (
            patch.object(console, "_catalog", AsyncMock(return_value=TOOLS)),
            patch.object(
                console, "_knowledge_catalog", AsyncMock(return_value=KBS)
            ),
            self.assertRaises(HTTPException) as error,
        ):
            await console.publish_builder(
                console.PublishRequest(
                    conversation_id="builder",
                    proposal_id=proposal.proposal_id,
                    expected_revision=proposal.revision,
                    knowledge_base_selections=[[], ["policy"]],
                ),
                user_id="user",
                storage=storage,
                access=object(),
                workspace_manager=object(),
            )
        self.assertEqual(error.exception.status_code, 409)
        storage.upsert_agent.assert_not_awaited()

    async def test_typesafe_credential_is_available_without_chat_models(self):
        from agentscope.app._router._model import list_models
        from agentscope.app._router._schema import ListModelsRequest

        credential = CredentialFactory.from_dict(
            TypeSafeCredential(api_key="test-key").model_dump()
        )
        self.assertIsInstance(credential, TypeSafeCredential)
        response = await list_models(
            ListModelsRequest(provider="typesafe_credential")
        )
        self.assertEqual(response.total, 0)
