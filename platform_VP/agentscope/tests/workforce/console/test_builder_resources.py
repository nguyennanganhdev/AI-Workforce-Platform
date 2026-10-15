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
from agentscope.classifier import BinaryAnswer, ChoiceAnswer
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
    def __init__(self, *, uncertain=False, missing=False):
        self.calls = []
        self.client = SimpleNamespace(aclose=AsyncMock())
        self.uncertain, self.missing = uncertain, missing

    async def __call__(self, *, state, questions):
        self.calls.append((deepcopy(state), questions))
        if "tool_0" in questions:
            return SimpleNamespace(
                content={
                    "tool_0": ChoiceAnswer(
                        "agent_1",
                        0.5 if self.uncertain else 0.95,
                        {"agent_1": 1.0},
                    ),
                    "tool_1": ChoiceAnswer("none", 0.95, {"none": 1.0}),
                    "kb_0_0": BinaryAnswer(0.95),
                    "kb_1_0": BinaryAnswer(0.95),
                }
            )
        return SimpleNamespace(
            content={
                key: BinaryAnswer(
                    0.05 if self.missing and key.startswith("tool") else 0.95
                )
                for key in questions
            }
        )


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
        self.assertEqual(len(classifier.calls), 2)
        self.assertEqual(OUTLINE.agents[1].suggested_tool_ids, [])

    async def test_jev_records_missing_capability(self):
        selected = await console._jev_resources(
            _Classifier(missing=True), OUTLINE, "Plan trip", TOOLS, KBS
        )
        self.assertEqual(
            selected.agents[1].missing_resources, ["tool: Search hotel rooms"]
        )

    async def test_uncertain_jev_falls_back_to_llm_without_changing_boundaries(
        self,
    ):
        fallback = OUTLINE.model_copy(deep=True)
        fallback.agents[1].suggested_tool_ids = [TOOLS[0].id]
        for agent in fallback.agents:
            agent.suggested_knowledge_base_ids = ["policy"]
        classifier = _Classifier(uncertain=True)
        model = _Model(fallback.model_dump())
        with patch.object(
            console, "_builder_classifier", AsyncMock(return_value=classifier)
        ):
            selected, source = await console._select_builder_resources(
                OUTLINE, "Plan trip", TOOLS, KBS, model, object(), "user"
            )
        self.assertEqual(source, "llm")
        self.assertEqual(selected, fallback)
        classifier.client.aclose.assert_awaited_once()
        self.assertEqual(len(model.calls), 1)

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
    ):
        storage = SimpleNamespace(
            upsert_message=AsyncMock(), list_agents=AsyncMock(return_value=[])
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
                console, "_outline", AsyncMock(return_value=(OUTLINE, 10, 10))
            ),
            patch.object(
                console,
                "_select_builder_resources",
                AsyncMock(return_value=selection),
            ) as select,
        ):
            result = await console.prepare_builder(
                console.PrepareRequest(
                    message="Confirm",
                    conversation_id="builder",
                    confirm_outline=confirm_outline,
                    expected_revision=expected_revision,
                    chat_model_config=CONFIG,
                ),
                user_id="user",
                storage=storage,
                access=object(),
            )
        if confirm_outline:
            select.assert_not_awaited()
        else:
            select.assert_awaited_once()
        return result

    async def test_preview_saves_selection_and_shows_missing_resources(self):
        selected = OUTLINE.model_copy(deep=True)
        selected.agents[1].suggested_tool_ids = [TOOLS[0].id]
        selected.agents[1].missing_resources = ["knowledge: Hotel policy"]
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

    async def test_outline_extracts_needs_without_loading_full_catalogs(self):
        model = _Model(OUTLINE.model_dump())
        result, _, _ = await console._outline(
            "Plan trip", TOOLS, model, CONFIG
        )
        self.assertEqual(
            result.agents[1].tool_requirements, ["Search hotel rooms"]
        )
        self.assertNotIn(
            TOOLS[1].id,
            str([message.get_text_content() for message in model.calls[0][0]]),
        )

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
