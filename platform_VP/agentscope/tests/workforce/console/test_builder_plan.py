"""Approved Builder tools must survive generation and publishing unchanged."""

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from agentscope.agent import ContextConfig, ReActConfig
from agentscope.app._router import _workforce_console as console
from agentscope.app._workforce_policy import (
    BUSINESS_AGENT_EVIDENCE_POLICY,
    governed_system_prompt,
)
from agentscope.app.storage import AgentData, AgentRecord, ChatModelConfig
from agentscope.mcp import HttpMCPConfig, MCPClient
from agentscope.message import AssistantMsg


class TestBuilderPlan(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.config = ChatModelConfig(
            type="openai_credential",
            credential_id="credential",
            model="model",
            parameters={},
        )
        self.plan = [
            console.PlannedAgentView(
                name=f"Agent {index}",
                objective=f"Nghiệp vụ du lịch {index}",
                suggested_tools=[
                    console.BuilderTool(
                        id=f"travel:tool_{index}_{number}",
                        mcp_id="travel",
                        mcp_name="Travel",
                        tool_name=f"tool_{index}_{number}",
                    )
                    for number in range(count)
                ],
            )
            for index, count in enumerate([3, 7, 6, 6])
        ]
        self.outline = console.ProposalView(
            conversation_id="conversation",
            status="needs_input",
            assistant_message="Đây là các agent được đề xuất.",
            planned_agents=self.plan,
            chat_model_config=self.config,
            fixed_config={},
        )
        self.messages = [self._message(self.outline)]
        self.payload = [
            {
                "plan_index": index,
                # Stale model output tries to change the approved plan.
                "name": "Different name",
                "objective": "Different objective",
                "selected_tool_ids": [agent.suggested_tools[0].id],
                "system_prompt": (
                    "Bạn phụ trách nghiệp vụ được giao, suy luận từ yêu cầu "
                    "của khách và trình bày kết quả rõ ràng bằng ngôn ngữ của họ."
                ),
                "skill_name": f"travel-{index}",
                "skill_markdown": (
                    "# Nghiệp vụ\n\nĐối chiếu yêu cầu của khách "
                    "với thông tin đã xác minh."
                ),
            }
            for index, agent in enumerate(self.plan)
        ]
        self.model = SimpleNamespace(
            context_size=128_000,
            count_tokens=AsyncMock(return_value=100),
            generate_structured_output=AsyncMock(
                side_effect=lambda *_: SimpleNamespace(
                    content={"agents": self.payload},
                )
            ),
        )
        self.storage = SimpleNamespace(
            list_agents=AsyncMock(return_value=[]),
            get_session=AsyncMock(
                return_value=SimpleNamespace(id="conversation")
            ),
            list_messages=AsyncMock(
                side_effect=lambda *_a, **_kw: (self.messages, False)
            ),
            get_agent=AsyncMock(return_value=None),
            upsert_agent=AsyncMock(),
            upsert_message=AsyncMock(),
        )
        self.catalog = self.enterContext(
            patch.object(
                console,
                "_catalog",
                AsyncMock(
                    return_value=[
                        tool
                        for agent in self.plan
                        for tool in agent.suggested_tools
                    ]
                ),
            )
        )
        self.enterContext(
            patch.object(
                console,
                "_builder_session",
                AsyncMock(
                    return_value=SimpleNamespace(id="conversation"),
                ),
            )
        )
        self.enterContext(
            patch.object(
                console,
                "_list_all_builder_messages",
                AsyncMock(
                    side_effect=lambda *_: self.messages,
                ),
            )
        )
        self.enterContext(
            patch.object(
                console, "get_model", AsyncMock(return_value=self.model)
            )
        )
        self.enterContext(
            patch.object(
                console,
                "_prepare_builder_memory",
                AsyncMock(
                    return_value="Hội thoại đã tóm tắt, không có danh sách tool.",
                ),
            )
        )
        self.enterContext(
            patch.object(
                console, "_record_builder_prompt_measurement", AsyncMock()
            )
        )
        self.enterContext(
            patch.object(console, "_persist_builder_turn", AsyncMock())
        )

    @staticmethod
    def _message(proposal: console.ProposalView) -> AssistantMsg:
        return AssistantMsg(
            name="agent_builder",
            content=proposal.assistant_message,
            structured_output={
                "workforce_builder_proposal": proposal.model_dump(mode="json")
            },
        )

    async def _prepare(self) -> console.ProposalView:
        return await console.prepare_builder(
            console.PrepareRequest(
                conversation_id="conversation",
                message="Chốt định hướng",
                confirm_outline=True,
                chat_model_config=self.config,
            ),
            user_id="user",
            storage=self.storage,
            access=SimpleNamespace(),
        )

    def _existing(self, tools: list[console.BuilderTool]) -> AgentRecord:
        return AgentRecord(
            id="existing",
            user_id="user",
            data=AgentData(
                name="Existing",
                system_prompt="Existing role",
                build_description=self.plan[0].objective,
                context_config=ContextConfig(),
                react_config=ReActConfig(),
                tool_bindings=[tool.model_dump() for tool in tools],
            ),
        )

    async def test_generation_keeps_plan_after_compaction(self) -> None:
        self.payload.reverse()
        proposal = await self._prepare()

        self.assertEqual(proposal.status, "ready")
        self.assertEqual(proposal.planned_agents, self.plan)
        self.assertEqual(
            [len(agent.selected_tools) for agent in proposal.agents],
            [3, 7, 6, 6],
        )
        for planned, generated in zip(self.plan, proposal.agents):
            self.assertEqual(
                (generated.name, generated.objective),
                (planned.name, planned.objective),
            )
            self.assertEqual(generated.selected_tools, planned.suggested_tools)
            self.assertNotIn(
                BUSINESS_AGENT_EVIDENCE_POLICY, generated.system_prompt
            )
            self.assertIn(
                BUSINESS_AGENT_EVIDENCE_POLICY,
                governed_system_prompt("business", generated.system_prompt),
            )
        sent = self.model.generate_structured_output.call_args.args[0]
        self.assertIn("Bạn viết cấu hình nghiệp vụ", sent[0].get_text_content())
        self.assertIn("không xen", sent[0].get_text_content())
        prompt = "\n".join(message.get_text_content() for message in sent)
        for planned in self.plan:
            for tool in planned.suggested_tools:
                self.assertIn(tool.id, prompt)
        schema = self.model.generate_structured_output.call_args.args[1]
        fields = schema.model_json_schema()["$defs"]["GeneratedAgent"][
            "properties"
        ]
        self.assertNotIn("selected_tool_ids", fields)
        self.assertNotIn("objective", fields)

    async def test_incomplete_or_invalid_agent_indices_are_rejected(
        self,
    ) -> None:
        valid = self.payload[:]
        for indices in ([0, 1, 2], [0, 1, 2, 2], [0, 1, 2, 4]):
            with self.subTest(indices=indices):
                self.payload = [
                    dict(valid[min(index, 3)], plan_index=index)
                    for index in indices
                ]
                with self.assertRaises(HTTPException):
                    await self._prepare()

    async def test_confirmation_requires_available_plan(self) -> None:
        for messages, tools in (
            ([], self.catalog.return_value),
            (self.messages, self.catalog.return_value[1:]),
        ):
            with self.subTest(has_plan=bool(messages)):
                self.messages = messages
                self.catalog.return_value = tools
                with self.assertRaises(HTTPException) as raised:
                    await self._prepare()
                self.assertEqual(raised.exception.status_code, 409)
                self.model.generate_structured_output.assert_not_awaited()

    async def test_reuse_requires_same_tools_and_valid_evaluation(
        self,
    ) -> None:
        approved = self.plan[0].suggested_tools
        for tools, reused in (
            (approved[:1], False),
            (approved + self.plan[1].suggested_tools[:1], False),
            (approved, True),
        ):
            with self.subTest(tool_count=len(tools)):
                self.storage.list_agents.return_value = [self._existing(tools)]
                proposal = await self._prepare()
                self.assertEqual(
                    bool(proposal.agents[0].reuse_agent_id), reused
                )
        self.payload[0]["system_prompt"] = "Prompt ngắn nhưng đủ 20 ký tự."
        proposal = await self._prepare()
        self.assertEqual(proposal.status, "blocked")
        self.assertFalse(proposal.agents[0].evaluation["passed"])

    async def test_publish_rechecks_catalog_plan_and_reuse(self) -> None:
        proposal = await self._prepare()
        request = console.PublishRequest(
            conversation_id="conversation",
            proposal_id=proposal.proposal_id,
            expected_revision=proposal.revision,
        )
        for reason in ("catalog", "plan", "reuse", "legacy"):
            with self.subTest(reason=reason):
                candidate = proposal.model_copy(deep=True)
                self.catalog.return_value = [
                    tool
                    for agent in self.plan
                    for tool in agent.suggested_tools
                ]
                if reason == "catalog":
                    self.catalog.return_value.pop()
                elif reason == "plan":
                    candidate.agents[0].selected_tools.pop()
                elif reason == "reuse":
                    candidate.agents[0].reuse_agent_id = "existing"
                    self.storage.get_agent.return_value = self._existing(
                        self.plan[0].suggested_tools[:1]
                    )
                else:
                    candidate.planned_agents = []
                self.messages = [self._message(candidate)]
                with self.assertRaises(HTTPException) as raised:
                    await console.publish_builder(
                        request,
                        user_id="user",
                        storage=self.storage,
                        workspace_manager=SimpleNamespace(),
                    )
                self.assertEqual(raised.exception.status_code, 409)
                self.storage.upsert_agent.assert_not_awaited()

    async def test_publish_installs_plan_tools_and_authored_prompt(
        self,
    ) -> None:
        proposal = await self._prepare()
        self.messages = [self._message(proposal)]
        self.storage.get_mcp = AsyncMock(
            return_value=SimpleNamespace(
                enabled=True,
                client=MCPClient(
                    name="Travel",
                    is_stateful=False,
                    mcp_config=HttpMCPConfig(url="https://travel.example/mcp"),
                ),
            )
        )
        workspace = SimpleNamespace(
            default_mcps=[],
            add_mcp=AsyncMock(),
            add_skill_archive=AsyncMock(),
        )
        manager = SimpleNamespace(
            get_workspace=AsyncMock(return_value=workspace)
        )
        self.enterContext(
            patch.object(
                console,
                "_primary_session",
                AsyncMock(
                    return_value=SimpleNamespace(
                        id="primary",
                        config=SimpleNamespace(workspace_id="workspace"),
                    ),
                ),
            )
        )
        response = await console.publish_builder(
            console.PublishRequest(
                conversation_id="conversation",
                proposal_id=proposal.proposal_id,
                expected_revision=proposal.revision,
            ),
            user_id="user",
            storage=self.storage,
            workspace_manager=manager,
        )
        self.assertEqual(len(response.agents), 4)
        for planned, call, install in zip(
            self.plan,
            self.storage.upsert_agent.call_args_list,
            workspace.add_mcp.call_args_list,
        ):
            record = call.args[1]
            self.assertEqual(
                [binding["id"] for binding in record.data.tool_bindings],
                [tool.id for tool in planned.suggested_tools],
            )
            self.assertEqual(
                install.args[0].enable_tools,
                [tool.tool_name for tool in planned.suggested_tools],
            )
            self.assertTrue(
                record.data.system_prompt.startswith("Bạn phụ trách")
            )
            self.assertNotIn(
                BUSINESS_AGENT_EVIDENCE_POLICY, record.data.system_prompt
            )
        self.assertEqual(workspace.add_skill_archive.await_count, 4)
