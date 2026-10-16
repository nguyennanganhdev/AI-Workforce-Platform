"""Reuse is approved before selecting resources and preserves existing agents."""

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from agentscope.app._router import _workforce_console as console
from agentscope.app.storage import AgentData, AgentRecord, InviteConfig
from agentscope.message import AssistantMsg
from tests.workforce.console import test_builder_resources as resources
from tests.workforce.console.test_builder_resources import (
    KBS,
    OUTLINE,
    TOOLS,
    _Classifier,
    _Model,
    approved,
    generated,
)


def existing_agent(agent_id="old-hotel", *, tools=TOOLS[:1]):
    record = AgentRecord(
        id=agent_id,
        user_id="user",
        data=AgentData(
            name="Existing hotel specialist",
            system_prompt="Use verified room inventory and hotel policies to find suitable accommodation.",
            context_config=console._FIXED_CONTEXT,
            react_config=console._FIXED_REACT,
            invite_config=InviteConfig(
                invitable=True, invite_description="Search available hotel rooms"
            ),
            lifecycle_state="published",
            build_description="Search hotel rooms",
            tool_bindings=[tool.model_dump() for tool in tools],
            knowledge_base_ids=[kb.id for kb in KBS],
            execution_mode="tool_backed" if tools else "context_only",
            generated_skill="# Workflow\n\nSearch available rooms and explain the verified hotel cancellation policies.",
        ),
    )
    from agentscope.app._agent_spec import SpecKnowledge, SpecTest, spec_from_legacy
    spec = spec_from_legacy(name=record.data.name, description=record.data.build_description,
        system_prompt=record.data.system_prompt, bindings=record.data.tool_bindings, policy="")
    spec.knowledge = [SpecKnowledge(kb_id=kb.id, name=kb.name) for kb in KBS]
    spec.tests = [SpecTest(scenario="Customer request " + str(i), expected="Use approved resources", safety_critical=i == 0) for i in range(3)]
    record.data.spec = spec.model_dump(mode="json")
    record.data.evaluation = resources.valid_report(spec)
    record.data.published_version = 1
    return record


def reused_plan(record):
    return console.PlannedAgentView(
        name="Hotel",
        objective="Search hotel rooms",
        suggested_tools=TOOLS[:1],
        suggested_knowledge_bases=KBS,
        reuse_agent_id=record.id,
        reuse_agent_name=record.data.name,
        reuse_agent_fingerprint=console._agent_fingerprint(record),
        reuse_probability=0.95,
    )


class TestBuilderReuse(IsolatedAsyncioTestCase):
    async def _reuse(self, outline, records, probabilities=None):
        classifier = _Classifier(probabilities=probabilities)
        with patch.object(
            console, "_builder_classifier", AsyncMock(return_value=classifier)
        ):
            result = await console._reuse_builder_agents(
                outline, records, TOOLS, KBS, object(), "user", "Find hotel rooms and explain hotel policies"
            )
        return result, classifier

    async def test_reuse_threshold_and_existing_resources(self):
        record = existing_agent()
        outline = console.BuilderOutline(agents=[OUTLINE.agents[1]])
        for probability, expected in [(0.8, record.id), (0.79, None), (0.5, None)]:
            with self.subTest(probability=probability):
                result, classifier = await self._reuse(
                    outline, [record], {"reuse_0_0": probability}
                )
                self.assertEqual(result.agents[0].reuse_agent_id, expected)
                self.assertEqual(
                    result.agents[0].suggested_tool_ids,
                    [TOOLS[0].id] if expected else [],
                )
                self.assertEqual(
                    result.agents[0].suggested_knowledge_base_ids,
                    ["policy"] if expected else [],
                )
                classifier.client.aclose.assert_awaited_once()
        self.assertIsNone(outline.agents[0].reuse_agent_id)

    async def test_reuse_judgment_receives_request_and_actual_agent_instructions(self):
        record = existing_agent()
        _, classifier = await self._reuse(OUTLINE, [record])
        state, questions = classifier.calls[0]
        self.assertEqual(state["request"], "Find hotel rooms and explain hotel policies")
        self.assertEqual(state["existing_agents"][0]["system_prompt"], record.data.system_prompt)
        self.assertEqual(state["existing_agents"][0]["skill_markdown"], record.data.generated_skill)
        self.assertIsNotNone(questions["reuse_0_0"].criteria)

    async def test_optional_kb_does_not_mark_accepted_reuse_as_missing_resources(self):
        record = existing_agent()
        record.data.knowledge_base_ids = []
        spec = console.AgentSpec.model_validate(record.data.spec)
        spec.knowledge = []
        record.data.spec = spec.model_dump(mode="json")
        record.data.evaluation = resources.valid_report(spec)
        outline = console.BuilderOutline(agents=[console.PlannedAgent(
            name="Hotel", objective="Search hotel rooms",
            tool_requirements=["Search hotel rooms"],
            knowledge_requirements=["Internal booking policy, if any"],
        )])
        selected, _ = await self._reuse(outline, [record])
        console._validate_resource_selection(selected, TOOLS, KBS)
        self.assertEqual(selected.agents[0].reuse_agent_id, record.id)
        self.assertEqual(selected.agents[0].missing_resources, [])

    async def test_same_existing_agent_collapses_two_plan_entries(self):
        outline = OUTLINE.model_copy(deep=True)
        outline.agents[0].objective = "Explain hotel cancellation policies"
        result, _ = await self._reuse(outline, [existing_agent()])
        self.assertEqual(len(result.agents), 1)
        self.assertIn("Explain hotel cancellation policies", result.agents[0].objective)
        self.assertIn("Search hotel rooms", result.agents[0].objective)
        self.assertEqual(result.agents[0].tool_requirements, ["Search hotel rooms"])
        console._validate_resource_selection(result, TOOLS, KBS)

    async def test_highest_probability_wins_and_equal_scores_are_stable(self):
        outline = console.BuilderOutline(agents=[OUTLINE.agents[1]])
        records = [existing_agent("b"), existing_agent("a")]
        for probabilities, expected in [
            ({"reuse_0_0": 0.8, "reuse_0_1": 0.99}, "b"),
            ({"reuse_0_0": 0.9, "reuse_0_1": 0.9}, "a"),
        ]:
            result, _ = await self._reuse(outline, records, probabilities)
            self.assertEqual(result.agents[0].reuse_agent_id, expected)

    async def test_missing_or_resource_mismatched_reused_agent_is_rejected(self):
        record = existing_agent()
        plan = reused_plan(record)
        for stored in [None, record]:
            if stored:
                plan.suggested_tools = []
            with self.assertRaises(HTTPException) as error:
                await console._check_reused_agents(
                    [plan],
                    SimpleNamespace(get_agent=AsyncMock(return_value=stored)),
                    "user",
                    TOOLS,
                    KBS,
                )
            self.assertEqual(error.exception.status_code, 409)

    async def test_two_existing_agents_cannot_claim_same_tool(self):
        records = [existing_agent("a"), existing_agent("b")]
        result, _ = await self._reuse(
            OUTLINE,
            records,
            {
                "reuse_0_0": 0.99,
                "reuse_0_1": 0.1,
                "reuse_1_0": 0.1,
                "reuse_1_1": 0.99,
            },
        )
        self.assertEqual([agent.reuse_agent_id for agent in result.agents], ["a", None])

    async def test_unavailable_agents_are_excluded_and_llm_reuse_is_ignored(self):
        records = []
        for field, value in [
            ("lifecycle_state", "draft"),
            ("lifecycle_state", "withdrawn"),
            ("system_role", "leader"),
            ("knowledge_base_ids", ["gone"]),
            ("tool_bindings", [{"id": "missing"}]),
        ]:
            record = existing_agent()
            setattr(record.data, field, value)
            records.append(record)
        record = existing_agent()
        record.data.invite_config.invitable = False
        records.append(record)
        record = existing_agent()
        record.user_id = "other"
        records.append(record)
        outline = OUTLINE.model_copy(deep=True)
        outline.agents[0].reuse_agent_id = "injected"
        outline.agents[0].suggested_tool_ids = ["injected"]
        result, classifier = await self._reuse(outline, records)
        self.assertTrue(all(agent.reuse_agent_id is None for agent in result.agents))
        self.assertEqual(result.agents[0].suggested_tool_ids, [])
        self.assertEqual(classifier.calls, [])
        self.assertNotIn(
            "reuse_agent_id", console.PlannedAgent.model_json_schema()["properties"]
        )

    async def test_context_only_candidate_cannot_cover_required_operations(self):
        result, classifier = await self._reuse(OUTLINE, [existing_agent(tools=[])])
        self.assertEqual(result.agents[0].reuse_agent_id, "old-hotel")
        self.assertIsNone(result.agents[1].reuse_agent_id)
        self.assertEqual(list(classifier.calls[0][1]), ["reuse_0_0"])

    async def test_jev_failure_keeps_new_agents(self):
        with patch.object(
            console,
            "_builder_classifier",
            AsyncMock(side_effect=RuntimeError("offline")),
        ):
            result = await console._reuse_builder_agents(
                OUTLINE, [existing_agent()], TOOLS, KBS, object(), "user", "Find hotel rooms"
            )
        self.assertEqual(result, OUTLINE)

    async def test_preview_reserves_reused_tools_before_selecting_new_agents(self):
        record = existing_agent()
        selected = console.BuilderOutline(
            agents=[OUTLINE.agents[0].model_copy(deep=True)]
        )
        selected.agents[0].suggested_knowledge_base_ids = ["policy"]
        result = await resources.TestBuilderResources._prepare(
            self,
            approved(),
            _Model({}),
            confirm_outline=False,
            existing=[record],
            classifier=_Classifier(probabilities={"reuse_0_0": 0.1}),
            selection=(selected, "llm"),
        )
        self.assertIsNone(result.planned_agents[0].reuse_agent_id)
        self.assertEqual(result.planned_agents[1].reuse_agent_id, record.id)
        self.assertEqual(result.resource_selection, "hybrid")
        self.assertEqual(sum(not agent.reuse_agent_id for agent in result.planned_agents), 1)

    async def test_all_reused_skips_resource_selection_and_generation(self):
        record = existing_agent()
        preview = await resources.TestBuilderResources._prepare(
            self,
            approved(),
            _Model({}),
            confirm_outline=False,
            existing=[record],
            classifier=_Classifier(),
            message="Tạo nhóm trợ lý du lịch",
        )
        self.assertEqual(len(preview.planned_agents), 1)
        self.assertTrue(all(agent.reuse_agent_id for agent in preview.planned_agents))
        self.assertEqual(preview.planned_agents[0].reuse_agent_id, record.id)
        model = _Model({})
        ready = await resources.TestBuilderResources._prepare(
            self, preview, model, existing=[record], expected_revision=preview.revision
        )
        self.assertEqual(ready.status, "ready")
        self.assertEqual(model.calls, [])
        self.assertEqual(ready.agents[0].system_prompt, record.data.system_prompt)
        self.assertEqual(ready.agents[0].skill_markdown, record.data.generated_skill)

    async def test_mixed_confirmation_generates_only_new_agents(self):
        record = existing_agent()
        previous = approved()
        previous.planned_agents[1] = reused_plan(record)
        payload = generated()
        payload["agents"] = payload["agents"][:1]
        model = _Model(payload)
        result = await resources.TestBuilderResources._prepare(
            self, previous, model, existing=[record]
        )
        self.assertEqual(result.status, "ready")
        self.assertEqual(
            [agent.reuse_agent_id for agent in result.agents], [None, record.id]
        )
        self.assertEqual(len(model.calls), 1)

    async def test_changed_reused_agent_blocks_confirmation_before_model_call(self):
        record = existing_agent()
        previous = approved()
        previous.planned_agents[1] = reused_plan(record)
        record.data.system_prompt += " Changed"
        model = _Model(generated())
        with self.assertRaises(HTTPException) as error:
            await resources.TestBuilderResources._prepare(
                self, previous, model, existing=[record]
            )
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(model.calls, [])

    async def _publish(self, proposal, record):
        storage = SimpleNamespace(
            get_session=AsyncMock(return_value=object()),
            get_agent=AsyncMock(return_value=record),
            list_messages=AsyncMock(
                return_value=(
                    [
                        AssistantMsg(
                            "builder",
                            "Ready",
                            structured_output={
                                "workforce_builder_proposal": proposal.model_dump()
                            },
                        )
                    ],
                    False,
                )
            ),
            claim_builder_publish=AsyncMock(return_value=True),
            upsert_agent=AsyncMock(),
            upsert_message=AsyncMock(),
        )
        workspace = SimpleNamespace(get_workspace=AsyncMock())
        with (
            patch.object(console, "_catalog", AsyncMock(return_value=TOOLS)),
            patch.object(console, "_knowledge_catalog", AsyncMock(return_value=KBS)),
        ):
            result = await console.publish_builder(
                console.PublishRequest(
                    conversation_id="builder",
                    proposal_id=proposal.proposal_id,
                    expected_revision=proposal.revision,
                ),
                request=SimpleNamespace(),
                user_id="user",
                storage=storage,
                access=object(),
                workspace_manager=workspace,
            )
        storage.upsert_agent.assert_not_awaited()
        workspace.get_workspace.assert_not_awaited()
        return result

    async def test_publish_returns_existing_id_without_changing_agent(self):
        record = existing_agent()
        previous = approved()
        previous.planned_agents = [reused_plan(record)]
        proposal = await resources.TestBuilderResources._prepare(
            self, previous, _Model({}), existing=[record]
        )
        before = record.model_dump()
        result = await self._publish(proposal, record)
        self.assertEqual(
            [(item.agent_id, item.reused) for item in result.agents],
            [(record.id, True)],
        )
        self.assertEqual(record.model_dump(), before)
        record.data.invite_config.invitable = False
        with self.assertRaises(HTTPException) as error:
            await self._publish(proposal, record)
        self.assertEqual(error.exception.status_code, 409)

    async def test_new_plan_cannot_switch_to_reuse_after_generation(self):
        record = existing_agent()
        proposal = await resources.TestBuilderResources._prepare(
            self, approved(), _Model(generated()), existing=[record]
        )
        self.assertTrue(all(agent.reuse_agent_id is None for agent in proposal.agents))
        proposal.agents[1].reuse_agent_id = record.id
        with self.assertRaises(HTTPException) as error:
            await self._publish(proposal, record)
        self.assertEqual(error.exception.status_code, 409)
