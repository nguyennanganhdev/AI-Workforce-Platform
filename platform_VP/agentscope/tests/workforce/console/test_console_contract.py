"""Focused contract tests for the Workforce Builder console."""

import asyncio
import inspect
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from fastapi import HTTPException, status

from agentscope.agent import ContextConfig, ReActConfig
from agentscope.app._router._schema import MCPView
from agentscope.app._router._workforce_console import (
    _BUILDER_ARTIFACT_SNAPSHOT_KEY,
    _BUILDER_BACKFILL_KEY,
    _LEADER_PROMPT,
    BuilderGeneration,
    BuilderKnowledgeBase,
    BuilderOutline,
    BuilderTool,
    GeneratedAgent,
    PlannedAgent,
    PlannedAgentView,
    PrepareRequest,
    ProposalView,
    ProposedAgentView,
    PublishRequest,
    _agent_tool_settings,
    _artifact_snapshot,
    _builder_contract_digest,
    _builder_session,
    _claim_exclusive_tool_ids,
    _compile_skill_body,
    _compile_system_prompt,
    _contract_checks,
    _enforce_dynamic_collaboration,
    _execution_mode_matches_tools,
    _existing_agent_covers,
    _generate,
    _generation_issues,
    _group_tool_catalog,
    _legacy_duplicate_candidates,
    _normalise_skill,
    _outline,
    _outline_issues,
    _record_contract_artifacts_match,
    _replace_agent_session_knowledge,
    _replace_agent_workspace_mcps,
    _resolve_outline_reuse_candidate,
    _resolve_proposal_reuse_candidate,
    _resolve_reuse_candidate,
    _resolve_selected_knowledge_bases,
    _resolve_selected_tools,
    _reused_outline_view,
    _reused_proposal_view,
    _schema_keys,
    _select_model_name,
    _similarity,
    _stored_proposal,
    _text_digest,
    publish_builder,
)
from agentscope.app._workforce_policy import (
    BUSINESS_AGENT_EVIDENCE_POLICY,
    WORKFORCE_LEADER_PROMPT,
    governed_system_prompt,
)
from agentscope.app.storage import AgentData, AgentRecord, ChatModelConfig, MCPRecord
from agentscope.mcp import HttpMCPConfig, MCPClient
from agentscope.message import AssistantMsg
from scripts.backfill_builder_contracts import (
    _canonical_contract,
    _synthesised_contract,
)
from scripts.backfill_builder_contracts import _matches as _backfill_matches


def _generated_agent(
    *,
    name: str = "Agent Tư Vấn",
    role: str = "specialist",
    execution_mode: str = "context_only",
    request_modes: tuple[str, ...] = ("advice", "lookup"),
    selected_tool_ids: list[str] | None = None,
) -> GeneratedAgent:
    key = name.casefold().replace(" ", "-")
    supports_action = "action" in request_modes
    return GeneratedAgent.model_validate(
        {
            "name": name,
            "execution_mode": execution_mode,
            "selected_tool_ids": selected_tool_ids or [],
            "behavior_contract": {
                "requirement": {
                    "agent_key": key,
                    "business_profile": {
                        "profile_schema_version": "1",
                        "objective": "Tư vấn lựa chọn phù hợp từ bằng chứng hợp lệ",
                        "responsibilities": [
                            "Phân tích yêu cầu và tạo khuyến nghị dùng được"
                        ],
                        "capabilities": ["recommend"],
                        "input_contract": {"request": "string"},
                        "output_contract": {"recommendations": "list"},
                        "business_scope": "Tư vấn trong phạm vi dữ liệu được giao",
                        "required_constraints": ["Không bịa dữ liệu"],
                        "execution_policy": (
                            "require_approval" if supports_action else "read_only"
                        ),
                        "knowledge_requirements": [],
                    },
                    "capabilities": [
                        {
                            "capability": "recommend",
                            "required": True,
                            "reason": "Cần tạo khuyến nghị cho khách hàng",
                        }
                    ],
                    "effect": "external_operation" if supports_action else "read",
                    "tracking_intent": "create_only",
                },
                "role": role,
                "intake_mode": (
                    "required_before_work" if role == "coordinator" else "none"
                ),
                "required_customer_inputs": (
                    [
                        {
                            "key": "request",
                            "description": "Yêu cầu đầu-cuối do khách hàng xác nhận",
                        },
                    ]
                    if role == "coordinator"
                    else []
                ),
                "request_modes": list(request_modes),
                "deliverables": ["Danh sách lựa chọn và khuyến nghị rõ ràng"],
                "completion_criteria": [
                    "Đã trả lựa chọn phù hợp hoặc blocker cuối cùng cụ thể"
                ],
                "exclusions": ["Không tự thực hiện nghiệp vụ của specialist khác"],
                "operational_facts": ["Tên, giá, trạng thái và chính sách"],
                "no_data_behavior": (
                    "Nêu truy vấn không có kết quả và không suy diễn rằng "
                    "lựa chọn không tồn tại"
                ),
                "tool_error_behavior": (
                    "Giữ kết quả hợp lệ, nêu lỗi công cụ và không lặp lại "
                    "truy vấn không đổi"
                ),
                "partial_result_behavior": (
                    "Đưa toàn bộ kết quả đã xác minh và ghi rõ phần chưa thể xác minh"
                ),
                "customer_input_policy": (
                    "Chỉ hỏi khách về dữ kiện bắt buộc do chính khách sở hữu"
                ),
                "peer_coordination_policy": (
                    "Gửi một nhiệm vụ hữu hạn tới peer phù hợp rồi chờ kết quả"
                ),
                "internal_reporting_policy": (
                    "Khi làm nội bộ, gửi kết quả hoàn chỉnh cho reply owner; "
                    "khi được mention thì trả khách"
                ),
                "synthesis_policy": (
                    "Tổng hợp bằng chứng và blocker thành phương án hữu ích, "
                    "không xin Leader quyết định hộ"
                ),
                "output_sections": [
                    "Khuyến nghị",
                    "Dữ kiện đã xác minh",
                    "Phần chưa xác minh",
                ],
            },
        }
    )


def _approved_outline_for(*agents: GeneratedAgent) -> BuilderOutline:
    return BuilderOutline(
        agents=[
            PlannedAgent(
                name=agent.name,
                objective=(
                    agent.behavior_contract.requirement.business_profile.objective
                ),
                required_capabilities=[
                    item.capability
                    for item in agent.behavior_contract.requirement.capabilities
                    if item.required
                ],
                request_modes=list(agent.behavior_contract.request_modes),
                effect=agent.behavior_contract.requirement.effect.value,
                suggested_tool_ids=agent.selected_tool_ids,
                suggested_knowledge_base_ids=agent.selected_knowledge_base_ids,
            )
            for agent in agents
        ],
    )


def _published_agent_record(agent: GeneratedAgent) -> AgentRecord:
    return AgentRecord(
        user_id="user-1",
        data=AgentData(
            id="existing-agent",
            name=agent.name,
            system_prompt=governed_system_prompt(
                "business",
                _compile_system_prompt(agent),
            ),
            context_config=ContextConfig(),
            react_config=ReActConfig(),
            lifecycle_state="published",
            build_description=(
                agent.behavior_contract.requirement.business_profile.objective
            ),
            tool_bindings=[
                {
                    "id": tool_id,
                    "mcp_id": tool_id.split(":", 1)[0],
                    "tool_name": tool_id.split(":", 1)[-1],
                }
                for tool_id in agent.selected_tool_ids
            ],
            knowledge_base_ids=agent.selected_knowledge_base_ids,
            execution_mode=agent.execution_mode,
            generated_skill=_normalise_skill(agent),
            builder_contract=agent.behavior_contract.model_dump(mode="json"),
            evaluation={"passed": True, "contract_compiled": True},
        ),
    )


def test_backfill_treats_an_incompatible_contract_as_legacy() -> None:
    record = _published_agent_record(_generated_agent())

    assert _canonical_contract(record) is not None
    record.data.builder_contract = {"legacy_schema": True}
    assert _canonical_contract(record) is None


def test_backfilled_agent_reuses_natural_request_when_scope_and_tools_match() -> None:
    agent = _generated_agent(
        execution_mode="tool_backed",
        request_modes=("advice", "lookup", "action"),
        selected_tool_ids=["travel:search_hotels", "travel:book_hotel"],
    )
    record = _published_agent_record(agent)
    record.data.name = "Agent khách sạn"
    record.data.build_description = "Tìm và đặt khách sạn phù hợp"
    contract = _synthesised_contract(record)
    record.data.builder_contract = contract.model_dump(mode="json")
    record.data.evaluation[_BUILDER_BACKFILL_KEY] = {
        "contract_sha256": _builder_contract_digest(contract),
        "system_prompt_sha256": _text_digest(record.data.system_prompt),
        "generated_skill_sha256": _text_digest(record.data.generated_skill),
    }
    planned = PlannedAgent(
        name="Agent tìm và đặt khách sạn",
        objective="Tìm và đặt khách sạn phù hợp",
        required_capabilities=["search hotels", "book hotel"],
        request_modes=["advice", "lookup", "action"],
        effect="external_operation",
        suggested_tool_ids=["travel:search_hotels", "travel:book_hotel"],
    )

    assert _existing_agent_covers(
        planned,
        record,
        {"travel:search_hotels", "travel:book_hotel"},
        set(),
    )


def test_published_artifact_snapshot_survives_compiler_change() -> None:
    agent = _generated_agent()
    record = _published_agent_record(agent)
    record.data.system_prompt = "Prompt được publish bằng compiler cũ"
    record.data.generated_skill = "Skill được publish bằng compiler cũ"
    record.data.evaluation[_BUILDER_ARTIFACT_SNAPSHOT_KEY] = _artifact_snapshot(
        agent.behavior_contract,
        record.data.system_prompt,
        record.data.generated_skill,
    )

    assert _record_contract_artifacts_match(record, agent)
    record.data.system_prompt += " đã bị sửa sau publish"
    assert not _record_contract_artifacts_match(record, agent)


def test_backfill_seals_historical_proposal_without_current_compiler() -> None:
    agent = _generated_agent(name="Agent compiler cũ")
    record = _published_agent_record(agent)
    record.data.system_prompt = "Prompt lịch sử"
    record.data.generated_skill = "Skill lịch sử"
    item = ProposedAgentView(
        name=agent.name,
        objective=agent.behavior_contract.requirement.business_profile.objective,
        execution_mode=agent.execution_mode,
        system_prompt=record.data.system_prompt,
        selected_tools=[],
        skill_name="agent-compiler-cu",
        skill_markdown=record.data.generated_skill,
        evaluation={"passed": True, "contract_compiled": True},
        behavior_contract=agent.behavior_contract,
    )

    assert _backfill_matches(record, item)


def test_agent_schema_does_not_expose_server_owned_builder_fields() -> None:
    schema = AgentData.model_json_schema()

    assert "system_role" not in schema["properties"]
    assert "lifecycle_state" not in schema["properties"]
    assert "tool_bindings" not in schema["properties"]
    assert "knowledge_base_ids" not in schema["properties"]
    assert "execution_mode" not in schema["properties"]
    assert "evaluation" not in schema["properties"]
    assert "builder_contract" not in schema["properties"]
    assert "context_config" in schema["properties"]
    assert "react_config" in schema["properties"]
    assert ContextConfig().trigger_ratio == 0.8
    assert ReActConfig() is not None


def test_builder_model_authors_contract_not_prompt_or_skill() -> None:
    properties = GeneratedAgent.model_json_schema()["properties"]

    assert "behavior_contract" in properties
    assert "system_prompt" not in properties
    assert "skill_markdown" not in properties
    assert "objective" not in properties


def test_mcp_view_exposes_catalog_but_not_connection_secret() -> None:
    record = MCPRecord(
        user_id="manager-1",
        client=MCPClient(
            name="partner_hotel",
            is_stateful=False,
            mcp_config=HttpMCPConfig(
                url="https://partner.example/mcp",
                headers={"Authorization": "Bearer secret-value"},
            ),
        ),
        discovered_tools=[
            {
                "name": "search_rooms",
                "description": "Search available rooms",
                "input_schema": {"type": "object"},
            },
        ],
        catalog_revision=1,
    )

    payload = MCPView.from_record(record).model_dump(mode="json")

    assert payload["tools"][0]["name"] == "search_rooms"
    assert "secret-value" not in str(payload)
    assert "headers" not in payload


def test_builder_projects_tool_schema_fields_for_dependency_reasoning() -> None:
    schema = {
        "type": "object",
        "properties": {
            "optional_limit": {"type": "integer"},
            "trace_id": {"type": "string"},
        },
        "required": ["trace_id"],
    }

    assert _schema_keys(schema) == ["trace_id"]
    assert _schema_keys({"type": "object"}) == []


def test_skill_normalisation_adds_safe_front_matter() -> None:
    agent = _generated_agent(
        name="Hotel Agent",
        execution_mode="tool_backed",
        selected_tool_ids=["mcp-1:search_rooms"],
    )

    skill = _normalise_skill(agent)

    assert skill.startswith("---\nname: hotel-agent\n")
    assert "Tư vấn lựa chọn phù hợp" in skill
    assert "## Phạm vi và trách nhiệm" in skill
    assert "## Quy trình" in skill
    assert "Output contract:" in skill
    assert "## Quyền trả lời" in skill


def test_contract_compiler_keeps_role_delta_and_runtime_policy_separate() -> None:
    agent = _generated_agent(role="coordinator")

    authored = _compile_system_prompt(agent)
    runtime = governed_system_prompt("business", authored)
    checks = _contract_checks(agent)

    assert all(checks.values())
    assert "VAI TRÒ NGHIỆP VỤ" in authored
    assert "Phạm vi:" in authored
    assert agent.behavior_contract.no_data_behavior in authored
    assert agent.behavior_contract.peer_coordination_policy in authored
    assert 'Input: {"request":"string"}' in authored
    assert len(authored) < 5_000
    for duplicated_policy in (
        "advice bao gồm read và transform",
        "external action tạo, cập nhật, xóa",
        "monitor là theo dõi trạng thái",
        "Một truy vấn lookup rỗng",
        "Khi khách @mention trực tiếp",
        "Không gửi lời hứa, báo cáo tiến độ",
    ):
        assert duplicated_policy not in authored
    assert "Advice, lookup and action are different intents" in runtime
    assert "A result or answer is completed" in runtime
    assert runtime.count("WORKFORCE RUNTIME EXECUTION POLICY:") == 1


def test_builder_enforces_dynamic_collaboration_without_domain_rules() -> None:
    payload = _generated_agent(role="coordinator").model_dump(mode="json")
    contract = payload["behavior_contract"]
    contract["peer_coordination_policy"] = (
        "Luôn chuyển mọi việc về Leader để xử lý tiếp."
    )
    contract["internal_reporting_policy"] = (
        "Mọi specialist đều gửi kết quả thẳng về Leader trong mọi trường hợp."
    )
    contract["synthesis_policy"] = (
        "Giao đồng thời cho tất cả specialist rồi hỏi Leader chọn phương án."
    )

    normalized = _enforce_dynamic_collaboration(
        GeneratedAgent.model_validate(payload),
    )
    normalized_contract = normalized.behavior_contract

    assert "đúng một specialist" in normalized_contract.synthesis_policy
    assert "live roster" in normalized_contract.peer_coordination_policy
    assert "không chuyển peer work qua Leader" in (
        normalized_contract.peer_coordination_policy
    )
    assert "answer kèm in_reply_to" in (normalized_contract.internal_reporting_policy)
    assert "khi Leader là requester" in (normalized_contract.internal_reporting_policy)


def test_input_readiness_matches_runtime_tool_availability() -> None:
    coordinator_payload = _generated_agent(role="coordinator").model_dump(mode="json")
    coordinator_payload["behavior_contract"]["intake_mode"] = "none"
    coordinator_payload["behavior_contract"]["required_customer_inputs"] = []
    coordinator = GeneratedAgent.model_validate(coordinator_payload)

    specialist_payload = _generated_agent().model_dump(mode="json")
    specialist_payload["behavior_contract"]["intake_mode"] = "required_before_work"
    specialist_payload["behavior_contract"]["required_customer_inputs"] = [
        {"key": "request", "description": "Yêu cầu của khách hàng"},
    ]
    specialist = GeneratedAgent.model_validate(specialist_payload)

    assert not _contract_checks(coordinator)["input_readiness"]
    assert not _contract_checks(specialist)["input_readiness"]


def test_contract_compiler_emits_required_input_gate() -> None:
    payload = _generated_agent(role="coordinator").model_dump(mode="json")
    contract = payload["behavior_contract"]
    contract["intake_mode"] = "required_before_work"
    contract["required_customer_inputs"] = [
        {"key": "origin", "description": "Customer-owned starting location"},
    ]
    contract["requirement"]["business_profile"]["input_contract"] = {
        "request": "string",
        "origin": "string",
    }
    agent = GeneratedAgent.model_validate(payload)

    authored = _compile_system_prompt(agent)

    assert "required_before_work" in authored
    assert "origin: Customer-owned starting location" in authored
    assert _contract_checks(agent)["input_readiness"]


def test_contract_validation_requires_explicit_intake_decision() -> None:
    payload = _generated_agent().model_dump(mode="json")
    del payload["behavior_contract"]["intake_mode"]
    del payload["behavior_contract"]["required_customer_inputs"]
    agent = GeneratedAgent.model_validate(payload)

    assert not _contract_checks(agent)["input_readiness"]


def test_builder_contract_schema_limits_prompt_bloat() -> None:
    schema = GeneratedAgent.model_json_schema()
    contract = schema["$defs"]["AgentBehaviorContract"]
    properties = contract["properties"]

    assert properties["deliverables"]["maxItems"] == 5
    assert properties["operational_facts"]["maxItems"] == 10
    assert properties["no_data_behavior"]["maxLength"] == 300
    assert properties["synthesis_policy"]["maxLength"] == 300


def test_semantic_validation_rejects_oversized_authored_prompt() -> None:
    payload = _generated_agent().model_dump(mode="json")
    payload["behavior_contract"]["requirement"]["business_profile"]["objective"] = (
        "x" * 4_000
    )
    agent = GeneratedAgent.model_validate(payload)

    issues = _generation_issues(BuilderGeneration(agents=[agent]), [], [])

    assert any("authored system prompt quá dài" in issue for issue in issues)


def test_contract_compiler_reuses_canonical_async_completion_condition() -> None:
    payload = _generated_agent(
        request_modes=("action",),
        execution_mode="tool_backed",
        selected_tool_ids=["travel:book"],
    ).model_dump(mode="json")
    requirement = payload["behavior_contract"]["requirement"]
    requirement["tracking_intent"] = "track_to_completion"
    requirement["policy_proposal"] = {
        "schema_version": "1",
        "capabilities": ["recommend"],
        "event_types": ["booking.completed"],
        "required_facts": ["booking_id", "status"],
        "completion_condition": "Provider xác nhận trạng thái completed.",
        "human_confirmation": True,
        "timeout_behavior": "status_query",
    }
    agent = GeneratedAgent.model_validate(payload)

    assert "Provider xác nhận trạng thái completed." in _compile_system_prompt(agent)
    assert "Provider xác nhận trạng thái completed." in _compile_skill_body(agent)


def test_semantic_validation_rejects_action_without_tool() -> None:
    invalid = _generated_agent(request_modes=("action",))
    generation = BuilderGeneration(agents=[invalid])

    issues = _generation_issues(generation, [], [])

    assert any("action bắt buộc phải là tool_backed" in issue for issue in issues)


def test_semantic_validation_rejects_read_only_action_contract() -> None:
    payload = _generated_agent(
        request_modes=("action",),
        execution_mode="tool_backed",
        selected_tool_ids=["travel:book"],
    ).model_dump(mode="json")
    requirement = payload["behavior_contract"]["requirement"]
    requirement["effect"] = "read"
    requirement["business_profile"]["execution_policy"] = "read_only"
    invalid = GeneratedAgent.model_validate(payload)

    issues = _generation_issues(
        BuilderGeneration(agents=[invalid]),
        [
            BuilderTool(
                id="travel:book",
                mcp_id="travel",
                mcp_name="Travel",
                tool_name="book",
            )
        ],
        [],
    )

    assert any("action_external_effect" in issue for issue in issues)
    assert any("action_requires_approval" in issue for issue in issues)


def test_semantic_validation_enforces_the_approved_outline() -> None:
    expected = _generated_agent(
        name="Agent đã duyệt",
        execution_mode="tool_backed",
        selected_tool_ids=["travel:book"],
    )
    expected_payload = expected.model_dump(mode="json")
    expected_payload["selected_knowledge_base_ids"] = ["travel-policy"]
    expected = GeneratedAgent.model_validate(expected_payload)
    changed_payload = expected.model_dump(mode="json")
    changed_payload["name"] = "Agent bị đổi tên"
    changed_payload["selected_tool_ids"] = []
    changed_payload["selected_knowledge_base_ids"] = []
    changed_payload["behavior_contract"]["requirement"]["business_profile"][
        "objective"
    ] = "Objective bị thay đổi"
    changed_payload["execution_mode"] = "context_only"
    changed = GeneratedAgent.model_validate(changed_payload)
    extra = _generated_agent(name="Agent phát sinh")

    issues = _generation_issues(
        BuilderGeneration(agents=[changed, extra]),
        [
            BuilderTool(
                id="travel:book",
                mcp_id="travel",
                mcp_name="Travel",
                tool_name="book",
            ),
        ],
        [BuilderKnowledgeBase(id="travel-policy", name="Travel policy")],
        _approved_outline_for(expected),
    )

    assert any("Số agent không khớp" in issue for issue in issues)
    assert any("tên phải giữ nguyên" in issue for issue in issues)
    assert any("objective phải giữ nguyên" in issue for issue in issues)
    assert any("tool phải giữ nguyên" in issue for issue in issues)
    assert any("Knowledge Base phải giữ nguyên" in issue for issue in issues)


class TestBuilderSemanticRepair(IsolatedAsyncioTestCase):
    async def test_generate_stops_after_exactly_one_repair(self) -> None:
        repaired = _generated_agent()
        repaired_generation = BuilderGeneration(agents=[repaired])
        invalid = repaired_generation.model_dump(mode="json")
        invalid_requirement = invalid["agents"][0]["behavior_contract"]["requirement"]
        invalid_requirement["business_profile"]["capabilities"] = [
            "different-capability",
        ]
        invalid_tracking = repaired_generation.model_dump(mode="json")
        invalid_tracking_requirement = invalid_tracking["agents"][0][
            "behavior_contract"
        ]["requirement"]
        invalid_tracking_requirement["tracking_intent"] = "track_to_completion"

        class _Model:
            context_size = 100_000

            def __init__(self):
                self.outputs = [
                    invalid,
                    invalid_tracking,
                ]
                self.calls = 0
                self.messages = []

            async def count_tokens(self, messages, tools):
                del messages, tools
                return 100

            async def generate_structured_output(self, messages, schema):
                assert isinstance(schema, dict)
                self.messages.append(messages)
                output = self.outputs[self.calls]
                self.calls += 1
                return SimpleNamespace(content=output)

        model = _Model()
        with self.assertRaises(HTTPException):
            await _generate(
                "Tạo agent tư vấn",
                _approved_outline_for(repaired),
                [],
                [],
                model,  # type: ignore[arg-type]
                ChatModelConfig(
                    type="openai_credential",
                    credential_id="credential-1",
                    model="gpt-4.1",
                    parameters={},
                ),
            )

        self.assertEqual(2, model.calls)
        self.assertIn(
            "Approved outline (authoritative JSON)",
            str(model.messages[0][0].content),
        )
        self.assertIn(repaired.name, str(model.messages[0][0].content))
        self.assertIn(
            "capabilities must belong to the business profile",
            str(model.messages[1][-1].content),
        )

    async def test_generate_repairs_invalid_contract_once(self) -> None:
        invalid = _generated_agent(request_modes=("action",))
        repaired = _generated_agent(
            request_modes=("action",),
            execution_mode="tool_backed",
            selected_tool_ids=["travel:book"],
        )

        class _Model:
            context_size = 100_000

            def __init__(self):
                self.outputs = [
                    BuilderGeneration(agents=[invalid]),
                    BuilderGeneration(agents=[repaired]),
                ]
                self.calls = 0
                self.prompts = []

            async def count_tokens(self, messages, tools):
                del messages, tools
                return 100

            async def generate_structured_output(self, messages, schema):
                del schema
                self.prompts.append(str(messages[0].content))
                output = self.outputs[self.calls]
                self.calls += 1
                return SimpleNamespace(content=output.model_dump(mode="json"))

        model = _Model()
        generation, _tokens, _reserve = await _generate(
            "Tạo agent thực hiện hành động",
            _approved_outline_for(repaired),
            [
                BuilderTool(
                    id="travel:book",
                    mcp_id="travel",
                    mcp_name="Travel",
                    tool_name="book",
                    input_keys=["option_id"],
                    output_keys=["booking_id"],
                )
            ],
            [],
            model,  # type: ignore[arg-type]
            ChatModelConfig(
                type="openai_credential",
                credential_id="credential-1",
                model="gpt-4o-mini",
                parameters={},
            ),
        )

        self.assertEqual(2, model.calls)
        self.assertIn("Team tool-flow map", model.prompts[0])
        self.assertIn('"input_keys": ["option_id"]', model.prompts[0])
        self.assertIn('"output_keys": ["booking_id"]', model.prompts[0])
        self.assertEqual("tool_backed", generation.agents[0].execution_mode)
        self.assertEqual(
            [],
            _generation_issues(
                generation,
                [
                    BuilderTool(
                        id="travel:book",
                        mcp_id="travel",
                        mcp_name="Travel",
                        tool_name="book",
                    )
                ],
                [],
            ),
        )

    async def test_generate_runs_three_agents_concurrently(self) -> None:
        agents = [_generated_agent(name=f"Agent {index}") for index in range(4)]

        class _Model:
            context_size = 100_000

            def __init__(self):
                self.active = 0
                self.peak = 0

            async def count_tokens(self, messages, tools):
                del messages, tools
                return 100

            async def generate_structured_output(self, messages, schema):
                del schema
                content = str(messages[0].content)
                agent = next(item for item in agents if item.name in content)
                self.active += 1
                self.peak = max(self.peak, self.active)
                await asyncio.sleep(0.01)
                self.active -= 1
                return SimpleNamespace(
                    content=BuilderGeneration(agents=[agent]).model_dump(mode="json"),
                )

        model = _Model()
        generation, _tokens, _reserve = await _generate(
            "Tạo bốn agent",
            _approved_outline_for(*agents),
            [],
            [],
            model,  # type: ignore[arg-type]
            ChatModelConfig(
                type="openai_credential",
                credential_id="credential-1",
                model="gpt-4.1-mini",
                parameters={},
            ),
        )

        self.assertEqual(3, model.peak)
        self.assertEqual(
            [agent.name for agent in agents],
            [agent.name for agent in generation.agents],
        )

    async def test_generate_repairs_only_the_invalid_agent(self) -> None:
        action = _generated_agent(
            name="Agent Hành Động",
            request_modes=("action",),
            execution_mode="tool_backed",
            selected_tool_ids=["service:act"],
        )
        invalid_action = _generated_agent(
            name="Agent Hành Động",
            request_modes=("action",),
        )
        advisor = _generated_agent(name="Agent Tư Vấn")

        class _Model:
            context_size = 100_000

            def __init__(self):
                self.calls = {action.name: 0, advisor.name: 0}

            async def count_tokens(self, messages, tools):
                del messages, tools
                return 100

            async def generate_structured_output(self, messages, schema):
                del schema
                content = str(messages[0].content)
                selected = action if action.name in content else advisor
                self.calls[selected.name] += 1
                output = (
                    invalid_action
                    if selected is action and self.calls[selected.name] == 1
                    else selected
                )
                return SimpleNamespace(
                    content=BuilderGeneration(agents=[output]).model_dump(mode="json"),
                )

        model = _Model()
        progress_events: list[tuple[str, int, int]] = []

        async def progress(stage, completed, total):
            progress_events.append((stage, completed, total))

        generation, _tokens, _reserve = await _generate(
            "Tạo agent tư vấn và hành động",
            _approved_outline_for(action, advisor),
            [
                BuilderTool(
                    id="service:act",
                    mcp_id="service",
                    mcp_name="Service",
                    tool_name="act",
                ),
            ],
            [],
            model,  # type: ignore[arg-type]
            ChatModelConfig(
                type="openai_credential",
                credential_id="credential-1",
                model="gpt-4.1-mini",
                parameters={},
            ),
            progress,
        )

        self.assertEqual({action.name: 2, advisor.name: 1}, model.calls)
        self.assertEqual(
            [action.name, advisor.name],
            [agent.name for agent in generation.agents],
        )
        self.assertIn(("repairing", 0, 2), progress_events)
        self.assertEqual(("validating", 2, 2), progress_events[-1])


class TestBuilderModelSelection(IsolatedAsyncioTestCase):
    async def test_builder_session_uses_builder_model_without_changing_runtime(
        self,
    ) -> None:
        runtime_config = ChatModelConfig(
            type="openai_credential",
            credential_id="runtime-credential",
            model="gpt-4.1",
            parameters={},
        )
        builder_config = ChatModelConfig(
            type="openai_credential",
            credential_id="builder-credential",
            model="gpt-4.1-mini",
            parameters={},
        )
        storage = SimpleNamespace(upsert_session=AsyncMock(return_value=object()))

        await _builder_session(
            storage,
            "user-1",
            PrepareRequest(
                message="Tạo một agent",
                chat_model_config=runtime_config,
                builder_chat_model_config=builder_config,
            ),
        )

        saved_config = storage.upsert_session.await_args.kwargs["config"]
        self.assertEqual(builder_config, saved_config.chat_model_config)
        self.assertEqual(runtime_config.model, "gpt-4.1")


class TestBuilderReuseOutline(IsolatedAsyncioTestCase):
    def test_outline_schema_requires_capability_mode_and_effect(self) -> None:
        required = set(PlannedAgent.model_json_schema()["required"])

        self.assertTrue(
            {"required_capabilities", "request_modes", "effect"}.issubset(required),
        )

    async def test_outline_repairs_action_without_a_tool_once(self) -> None:
        invalid = BuilderOutline(
            agents=[
                PlannedAgent(
                    name="Agent hành động",
                    objective="Tra cứu và thực hiện thao tác bên ngoài.",
                    required_capabilities=["execute"],
                    request_modes=["lookup", "action"],
                    effect="read",
                ),
            ],
        )
        valid = BuilderOutline(
            agents=[
                PlannedAgent(
                    name="Agent hành động",
                    objective="Tra cứu và thực hiện thao tác bên ngoài.",
                    required_capabilities=["execute"],
                    request_modes=["lookup", "action"],
                    effect="external_operation",
                    suggested_tool_ids=["service:execute"],
                ),
            ],
        )
        tools = [
            BuilderTool(
                id="service:execute",
                mcp_id="service",
                mcp_name="Service",
                tool_name="execute",
            ),
        ]

        class _Model:
            context_size = 100_000

            def __init__(self):
                self.outputs = [invalid, valid]
                self.messages = []

            async def count_tokens(self, messages, tools):
                del messages, tools
                return 100

            async def generate_structured_output(self, messages, schema):
                assert isinstance(schema, dict)
                self.messages.append(messages)
                return SimpleNamespace(
                    content=self.outputs[len(self.messages) - 1].model_dump(
                        mode="json",
                    ),
                )

        model = _Model()
        outline, _tokens, _reserve = await _outline(
            "Tạo agent có thể tra cứu và thực hiện thao tác",
            tools,
            [],
            [],
            model,  # type: ignore[arg-type]
            ChatModelConfig(
                type="openai_credential",
                credential_id="credential-1",
                model="gpt-4.1-mini",
                parameters={},
            ),
        )

        self.assertEqual(2, len(model.messages))
        self.assertEqual(["service:execute"], outline.agents[0].suggested_tool_ids)
        self.assertIn(
            "action yêu cầu effect=external_operation",
            str(model.messages[1][-1].content),
        )
        self.assertEqual([], _outline_issues(outline, tools, []))

    async def test_outline_receives_compact_existing_agent_catalog(self) -> None:
        existing_agent = _generated_agent(name="Agent hiện có")
        record = _published_agent_record(existing_agent)
        expected = BuilderOutline(
            agents=[
                PlannedAgent(
                    name="Agent yêu cầu mới",
                    objective=(
                        existing_agent.behavior_contract.requirement.business_profile.objective
                    ),
                    required_capabilities=["recommend"],
                    request_modes=["advice", "lookup"],
                    effect="read",
                    reuse_agent_id=record.id,
                ),
            ],
        )

        class _Model:
            context_size = 100_000

            def __init__(self):
                self.messages = []

            async def count_tokens(self, messages, tools):
                del messages, tools
                return 100

            async def generate_structured_output(self, messages, schema):
                assert isinstance(schema, dict)
                self.messages = messages
                return SimpleNamespace(content=expected.model_dump(mode="json"))

        model = _Model()
        outline, _tokens, _reserve = await _outline(
            "Tạo agent có nghiệp vụ đã tồn tại",
            [],
            [],
            [record],
            model,  # type: ignore[arg-type]
            ChatModelConfig(
                type="openai_credential",
                credential_id="credential-1",
                model="gpt-4.1",
                parameters={},
            ),
        )

        self.assertEqual(outline.agents[0].reuse_agent_id, record.id)
        prompt = str(model.messages[0].content)
        self.assertIn(record.id, prompt)
        self.assertIn("tool_ids", prompt)
        self.assertNotIn("WORKFORCE RUNTIME EXECUTION POLICY", prompt)


def test_reuse_similarity_prefers_same_business_capability() -> None:
    same = _similarity(
        "Agent tìm khách sạn và kiểm tra phòng theo ngân sách",
        "Agent kiểm tra phòng khách sạn theo ngân sách và đề xuất lựa chọn",
    )
    unrelated = _similarity(
        "Agent tìm khách sạn và kiểm tra phòng theo ngân sách",
        "Agent chẩn đoán sự cố điện và điều phối kỹ thuật viên",
    )

    assert same > unrelated
    assert unrelated < 0.3


def test_reuse_accepts_a_narrower_tool_subset_only_with_contract_coverage() -> None:
    existing_agent = _generated_agent(
        name="Agent A",
        execution_mode="tool_backed",
        selected_tool_ids=[f"travel:{name}" for name in ("a", "b", "c", "d", "e")],
    )
    record = _published_agent_record(existing_agent)
    planned = PlannedAgent(
        name="Agent B",
        objective=existing_agent.behavior_contract.requirement.business_profile.objective,
        required_capabilities=["recommend"],
        request_modes=["advice", "lookup"],
        effect="read",
        suggested_tool_ids=["travel:b", "travel:d", "travel:e"],
        reuse_agent_id=record.id,
    )
    available = {f"travel:{name}" for name in ("a", "b", "c", "d", "e")}

    assert _existing_agent_covers(planned, record, available, set())
    assert _resolve_reuse_candidate(planned, [record], available, set()) is record

    record.data.system_prompt = "Legacy prompt đã phát hành"
    record.data.generated_skill = "Legacy skill đã phát hành"
    record.data.evaluation[_BUILDER_BACKFILL_KEY] = {
        "contract_sha256": _builder_contract_digest(
            existing_agent.behavior_contract,
        ),
        "system_prompt_sha256": _text_digest(record.data.system_prompt),
        "generated_skill_sha256": _text_digest(record.data.generated_skill),
    }
    assert _existing_agent_covers(planned, record, available, set())
    record.data.system_prompt += " đã bị sửa"
    assert not _existing_agent_covers(planned, record, available, set())
    record.data.system_prompt = "Legacy prompt đã phát hành"

    specific_agent = _generated_agent(
        name="Agent B chuyên biệt",
        execution_mode="tool_backed",
        selected_tool_ids=["travel:b", "travel:d", "travel:e"],
    )
    specific_record = _published_agent_record(specific_agent)
    specific_record.data.id = "existing-agent-specific"
    automatic_plan = planned.model_copy(update={"reuse_agent_id": None})
    assert (
        _resolve_reuse_candidate(
            automatic_plan,
            [record, specific_record],
            available,
            set(),
        )
        is specific_record
    )

    tools = [
        BuilderTool(
            id=tool_id,
            mcp_id="travel",
            mcp_name="Travel",
            tool_name=tool_id.split(":", 1)[1],
        )
        for tool_id in sorted(available)
    ]
    reused_view = _reused_proposal_view(record, tools, [])
    assert reused_view.reuse_agent_id == record.id
    assert {tool.id for tool in reused_view.selected_tools} == available
    assert reused_view.evaluation["reused"] is True

    outline_view = _reused_outline_view(record, tools, [])
    assert outline_view.reuse_agent_id == record.id
    assert outline_view.objective == (
        existing_agent.behavior_contract.requirement.business_profile.objective
    )
    assert {tool.id for tool in outline_view.suggested_tools} == available
    assert outline_view.required_capabilities == ["recommend"]

    record.data.builder_contract = {}
    assert not _existing_agent_covers(planned, record, available, set())
    assert _legacy_duplicate_candidates(planned, [record], available, set()) == [
        record,
    ]


def test_outline_reuse_falls_back_when_model_selects_the_wrong_agent_id() -> None:
    existing_agent = _generated_agent(name="Agent hiện có")
    record = _published_agent_record(existing_agent)
    planned = PlannedAgent(
        name="Agent cần dùng",
        objective=existing_agent.behavior_contract.requirement.business_profile.objective,
        required_capabilities=["recommend"],
        request_modes=["advice", "lookup"],
        effect="read",
        reuse_agent_id="model-selected-the-wrong-id",
    )

    assert _resolve_outline_reuse_candidate(planned, [record], set(), set()) is record


def test_publish_recheck_blocks_a_child_of_a_published_agent() -> None:
    parent = _generated_agent(
        name="Agent du lịch đã publish",
        execution_mode="tool_backed",
        selected_tool_ids=["travel:search", "travel:recommend"],
    )
    record = _published_agent_record(parent)
    child = ProposedAgentView(
        name="Agent tìm lựa chọn du lịch",
        objective=parent.behavior_contract.requirement.business_profile.objective,
        execution_mode="tool_backed",
        system_prompt="unused by reuse matching",
        selected_tools=[
            BuilderTool(
                id="travel:search",
                mcp_id="travel",
                mcp_name="Travel",
                tool_name="search",
            ),
        ],
        skill_name="travel-search",
        skill_markdown="unused by reuse matching",
        evaluation={"passed": True},
        behavior_contract=parent.behavior_contract,
    )

    assert (
        _resolve_proposal_reuse_candidate(
            child,
            [record],
            {"travel:search", "travel:recommend"},
            set(),
        )
        is record
    )


class TestBuilderPublishReuseGuard(IsolatedAsyncioTestCase):
    async def test_late_published_match_is_reported_without_creating_agent(
        self,
    ) -> None:
        existing_agent = _generated_agent(name="Agent đã publish")
        existing_record = _published_agent_record(existing_agent)
        proposed_agent = _generated_agent(name="Agent đề xuất trùng")
        proposal = ProposalView(
            conversation_id="conversation-1",
            proposal_id="proposal-1",
            status="ready",
            assistant_message="Sẵn sàng phát hành",
            agents=[
                ProposedAgentView(
                    name=proposed_agent.name,
                    objective=(
                        proposed_agent.behavior_contract.requirement.business_profile.objective
                    ),
                    execution_mode=proposed_agent.execution_mode,
                    system_prompt=governed_system_prompt(
                        "business",
                        _compile_system_prompt(proposed_agent),
                    ),
                    selected_tools=[],
                    skill_name="agent-de-xuat-trung",
                    skill_markdown=_normalise_skill(proposed_agent),
                    evaluation={"passed": True, "contract_compiled": True},
                    behavior_contract=proposed_agent.behavior_contract,
                ),
            ],
            chat_model_config=ChatModelConfig(
                type="openai_credential",
                credential_id="credential-1",
                model="gpt-4.1-mini",
                parameters={},
            ),
            fixed_config={},
        )
        storage = SimpleNamespace(
            get_session=AsyncMock(return_value=object()),
            list_messages=AsyncMock(
                return_value=(
                    [
                        AssistantMsg(
                            name="agent_builder",
                            content="Sẵn sàng phát hành",
                            structured_output={
                                "workforce_builder_proposal": proposal.model_dump(
                                    mode="json",
                                ),
                            },
                        ),
                    ],
                    None,
                ),
            ),
            list_mcps=AsyncMock(return_value=[]),
            list_agents=AsyncMock(return_value=[existing_record]),
            upsert_agent=AsyncMock(),
        )
        access = SimpleNamespace(list_resource=AsyncMock(return_value=[]))

        with self.assertRaises(HTTPException) as blocked:
            await publish_builder(
                PublishRequest(
                    conversation_id="conversation-1",
                    proposal_id="proposal-1",
                    expected_revision=1,
                ),
                user_id="user-1",
                storage=storage,
                workspace_manager=SimpleNamespace(),
                access=access,
            )

        self.assertEqual(status.HTTP_409_CONFLICT, blocked.exception.status_code)
        self.assertIn(existing_record.data.name, blocked.exception.detail)
        self.assertIn("Builder không cho tạo lại", blocked.exception.detail)
        storage.upsert_agent.assert_not_awaited()


def test_workforce_model_default_does_not_depend_on_card_order() -> None:
    assert (
        _select_model_name(
            "openai_credential",
            ["gpt-4.1-mini", "gpt-4o-mini"],
            None,
        )
        == "gpt-4o-mini"
    )
    assert (
        _select_model_name(
            "openai_credential",
            ["gpt-4.1-mini", "gpt-4o-mini"],
            "gpt-4o",
        )
        == "gpt-4o"
    )


def test_builder_prepare_requires_user_selected_model() -> None:
    schema = PrepareRequest.model_json_schema()

    assert "chat_model_config" in schema["required"]


def test_workforce_agents_answer_in_natural_vietnamese() -> None:
    assert "Always answer the customer in natural Vietnamese" in _LEADER_PROMPT
    assert "helpful person" in _LEADER_PROMPT
    assert "Rewrite internal reports into one coherent response" in _LEADER_PROMPT
    assert "never paste them verbatim" in _LEADER_PROMPT
    assert "Do not call TeamSay back to its sender" in _LEADER_PROMPT
    assert "Reply to the customer immediately" in _LEADER_PROMPT


def test_leader_is_domain_agnostic_and_stops_unproductive_discussion() -> None:
    assert "domain-agnostic" in _LEADER_PROMPT
    assert "orchestrator, not a specialist" in _LEADER_PROMPT
    assert "same point repeats" in _LEADER_PROMPT
    assert "without new information" in _LEADER_PROMPT
    assert "dependency" in _LEADER_PROMPT
    assert "cycle or runtime limit" in _LEADER_PROMPT
    assert "Do not restart stopped work" in _LEADER_PROMPT
    assert "current member results" in _LEADER_PROMPT
    assert "do not promise that the team will continue later" in _LEADER_PROMPT
    assert "do not repeat" in _LEADER_PROMPT
    assert "speak on behalf of a pending consent flow" in _LEADER_PROMPT
    for domain_example in ("hotel", "restaurant", "trip", "booking"):
        assert domain_example not in _LEADER_PROMPT.casefold()


def test_builder_outline_keeps_team_capabilities_separate() -> None:
    outline = BuilderOutline.model_validate(
        {
            "agents": [
                {
                    "name": "Plan Agent",
                    "objective": "Lập kế hoạch chuyến đi",
                    "required_capabilities": ["plan"],
                    "request_modes": ["advice"],
                    "effect": "read",
                },
                {
                    "name": "Hotel Agent",
                    "objective": "Tìm và đặt khách sạn",
                    "required_capabilities": ["search", "book"],
                    "request_modes": ["lookup", "action"],
                    "effect": "external_operation",
                    "suggested_tool_ids": ["travel:search_hotels"],
                },
            ],
        },
    )

    assert [agent.name for agent in outline.agents] == [
        "Plan Agent",
        "Hotel Agent",
    ]


def test_runtime_prompt_policy_overrides_stale_leader_and_wraps_business() -> None:
    assert governed_system_prompt("leader", "old prompt") == WORKFORCE_LEADER_PROMPT
    governed = governed_system_prompt("business", "Business specialist")
    assert BUSINESS_AGENT_EVIDENCE_POLICY in governed
    assert governed_system_prompt("business", governed) == governed
    stale = "Business specialist\n\nWORKFORCE RUNTIME EVIDENCE POLICY:\n- stale rule"
    refreshed = governed_system_prompt("business", stale)
    assert "stale rule" not in refreshed
    assert refreshed.count("WORKFORCE RUNTIME EXECUTION POLICY:") == 1
    assert "assemble the right team" in WORKFORCE_LEADER_PROMPT
    assert "Ask task-specific questions only" in WORKFORCE_LEADER_PROMPT
    assert "Customer clarification is the narrow" in WORKFORCE_LEADER_PROMPT
    assert "Follow the authored business role" in governed
    assert "create, update, delete, submit, communicate" in governed
    assert "Never ask the customer to type a confirmation" in governed
    assert "Tool-specific status semantics" in governed
    assert "pretrained knowledge" in governed
    assert "call a matching attached MCP tool before answering" in governed
    assert "exact successful tool results" in governed
    assert "empty lookup/search result proves only" in governed
    assert "Do not repeat an unchanged call" in governed
    assert "Advice, lookup and action are different intents" in governed
    assert "never implies an external mutation" in governed
    assert "preserve all other verified useful results" in governed
    assert "Do not ask the Leader to approve" in governed
    assert "A coordinator must turn verified peer outputs" in governed
    assert "not a promise" in governed
    assert "no suitable peer" in governed
    assert "project configuration" in governed
    assert "credentials/tokens" in governed
    assert "terminal kind=result/error to the Leader" in governed
    assert "answer the customer directly in natural Vietnamese" in governed


def test_builder_and_global_templates_use_only_abstract_work_types() -> None:
    templates = "\n".join(
        (
            inspect.getsource(_outline),
            inspect.getsource(_generate),
            _compile_system_prompt(_generated_agent()),
            _compile_skill_body(_generated_agent()),
            BUSINESS_AGENT_EVIDENCE_POLICY,
        )
    ).casefold()

    for work_type in ("read", "transform", "lookup", "external action", "monitor"):
        assert work_type in templates
    for domain_term in (
        "travel",
        "hotel",
        "restaurant",
        "transport",
        "attraction",
        "sightseeing",
        "booking",
        "unpaid_demo",
        "availability",
        "reservation",
        "payment",
        "cancellation",
        "khách sạn",
        "nhà hàng",
        "đặt chỗ",
        "thanh toán",
    ):
        assert domain_term not in templates


def test_builder_claims_each_tool_for_only_one_agent() -> None:
    claimed: set[str] = set()
    first = _claim_exclusive_tool_ids(
        ["travel:search_hotels", "travel:search_hotels"],
        {"travel:search_hotels", "travel:book_hotel"},
        claimed,
    )
    second = _claim_exclusive_tool_ids(
        ["travel:search_hotels", "travel:book_hotel", "invented"],
        {"travel:search_hotels", "travel:book_hotel"},
        claimed,
    )

    assert first == (["travel:search_hotels"], [], [])
    assert second == (
        ["travel:book_hotel"],
        ["invented"],
        ["travel:search_hotels"],
    )


def test_builder_allows_context_only_agent_without_mcp() -> None:
    assert "execution_mode" in GeneratedAgent.model_json_schema()["required"]
    assert (
        "selected_knowledge_base_ids"
        in GeneratedAgent.model_json_schema()["properties"]
    )
    selected = [
        BuilderTool(
            id="travel:search_hotels",
            mcp_id="travel",
            mcp_name="travel",
            tool_name="search_hotels",
        ),
    ]

    assert _execution_mode_matches_tools("context_only", [])
    assert not _execution_mode_matches_tools("context_only", selected)
    assert _execution_mode_matches_tools("tool_backed", selected)
    assert not _execution_mode_matches_tools("tool_backed", [])


def test_agent_tool_settings_group_mcps_and_reject_stale_ids() -> None:
    catalog = [
        BuilderTool(
            id="mcp-1:search",
            mcp_id="mcp-1",
            mcp_name="Search MCP",
            tool_name="search",
        ),
        BuilderTool(
            id="mcp-1:detail",
            mcp_id="mcp-1",
            mcp_name="Search MCP",
            tool_name="detail",
        ),
        BuilderTool(
            id="mcp-2:send",
            mcp_id="mcp-2",
            mcp_name="Action MCP",
            tool_name="send",
        ),
    ]

    groups = _group_tool_catalog(catalog)
    selected, invalid = _resolve_selected_tools(
        catalog,
        ["mcp-1:detail", "missing:tool", "mcp-1:detail"],
    )

    assert [(group.mcp_name, len(group.tools)) for group in groups] == [
        ("Search MCP", 2),
        ("Action MCP", 1),
    ]
    assert [tool.id for tool in selected] == ["mcp-1:detail"]
    assert invalid == ["missing:tool"]


def test_builder_resolves_only_registered_knowledge_bases() -> None:
    catalog = [
        BuilderKnowledgeBase(
            id="kb-policy",
            name="Chính sách",
            description="Quy định nội bộ",
        ),
    ]

    selected, invalid = _resolve_selected_knowledge_bases(
        catalog,
        ["kb-policy", "missing", "kb-policy"],
    )

    assert [knowledge.id for knowledge in selected] == ["kb-policy"]
    assert invalid == ["missing"]


class TestAgentToolWorkspaceSync(IsolatedAsyncioTestCase):
    async def test_settings_include_enabled_mcp_without_tools(self) -> None:
        mcp = SimpleNamespace(
            id="empty-mcp",
            enabled=True,
            display_name="Empty MCP",
            client=SimpleNamespace(name="empty_mcp"),
            discovered_tools=[],
        )
        settings = await _agent_tool_settings(
            SimpleNamespace(
                list_mcps=AsyncMock(return_value=[mcp]),
            ),
            SimpleNamespace(list_resource=AsyncMock(return_value=[])),
            "user-1",
            SimpleNamespace(
                id="agent-1",
                data=SimpleNamespace(tool_bindings=[], knowledge_base_ids=[]),
            ),
        )

        self.assertEqual(len(settings.mcps), 1)
        self.assertEqual(settings.mcps[0].mcp_name, "Empty MCP")
        self.assertEqual(settings.mcps[0].tools, [])

    async def test_replaces_workspace_mcps_with_exact_selection(self) -> None:
        client = MCPClient(
            name="travel_mcp",
            is_stateful=False,
            mcp_config=HttpMCPConfig(url="https://example.test/mcp"),
        )
        storage = SimpleNamespace(
            get_mcp=AsyncMock(
                return_value=SimpleNamespace(enabled=True, client=client),
            ),
            list_sessions=AsyncMock(
                return_value=[
                    SimpleNamespace(
                        id="session-1",
                        config=SimpleNamespace(workspace_id="workspace-1"),
                    ),
                ],
            ),
        )
        workspace = SimpleNamespace(
            default_mcps=[SimpleNamespace(name="default-mcp")],
            list_mcps=AsyncMock(
                return_value=[SimpleNamespace(name="old-mcp")],
            ),
            remove_mcp=AsyncMock(),
            add_mcp=AsyncMock(),
        )
        manager = SimpleNamespace(
            get_workspace=AsyncMock(return_value=workspace),
        )

        await _replace_agent_workspace_mcps(
            storage,
            manager,
            "user-1",
            SimpleNamespace(id="agent-1"),
            [
                BuilderTool(
                    id="mcp-1:search",
                    mcp_id="mcp-1",
                    mcp_name="travel_mcp",
                    tool_name="search",
                ),
                BuilderTool(
                    id="mcp-1:book",
                    mcp_id="mcp-1",
                    mcp_name="travel_mcp",
                    tool_name="book",
                ),
            ],
        )

        self.assertCountEqual(
            [item.args[0] for item in workspace.remove_mcp.await_args_list],
            ["old-mcp", "default-mcp"],
        )
        added_client = workspace.add_mcp.await_args.args[0]
        self.assertEqual(added_client.name, "travel_mcp")
        self.assertEqual(added_client.enable_tools, ["search", "book"])

    async def test_replaces_existing_session_knowledge_with_agent_defaults(
        self,
    ) -> None:
        config = SimpleNamespace(
            knowledge_config=None,
            model_copy=lambda deep: SimpleNamespace(knowledge_config=None),
        )
        storage = SimpleNamespace(
            list_sessions=AsyncMock(
                return_value=[SimpleNamespace(id="session-1", config=config)],
            ),
            upsert_session=AsyncMock(),
        )

        await _replace_agent_session_knowledge(
            storage,
            "user-1",
            SimpleNamespace(id="agent-1"),
            ["kb-policy"],
        )

        saved_config = storage.upsert_session.await_args.kwargs["config"]
        self.assertEqual(
            saved_config.knowledge_config.knowledge_base_ids,
            ["kb-policy"],
        )
        self.assertEqual(saved_config.knowledge_config.parameters["mode"], "agentic")


def test_builder_proposal_round_trips_through_persisted_message() -> None:
    proposal = ProposalView(
        conversation_id="builder-conversation-1",
        status="needs_input",
        assistant_message="Đề xuất Plan Agent và Hotel Agent.",
        clarification_question="Bạn có chốt định hướng này không?",
        planned_agents=[
            PlannedAgentView(
                name="Plan Agent",
                objective="Lập kế hoạch từ kết quả của các specialist.",
                suggested_tools=[
                    BuilderTool(
                        id="travel:plan",
                        mcp_id="travel",
                        mcp_name="Travel",
                        tool_name="plan",
                    ),
                ],
                suggested_knowledge_bases=[
                    BuilderKnowledgeBase(
                        id="travel-policy",
                        name="Travel policy",
                    ),
                ],
            ),
        ],
        chat_model_config=ChatModelConfig(
            type="openai_credential",
            credential_id="credential-1",
            model="gpt-4o-mini",
            parameters={},
        ),
        builder_chat_model_config=ChatModelConfig(
            type="openai_credential",
            credential_id="builder-credential-1",
            model="gpt-4.1-mini",
            parameters={},
        ),
        fixed_config={},
    )
    message = AssistantMsg(
        name="agent_builder",
        content=proposal.assistant_message,
        structured_output={
            "workforce_builder_proposal": proposal.model_dump(mode="json"),
        },
    )

    restored = _stored_proposal([message])

    assert restored is not None
    assert restored.conversation_id == "builder-conversation-1"
    assert restored.status == "needs_input"
    assert restored.chat_model_config.model == "gpt-4o-mini"
    assert restored.builder_chat_model_config is not None
    assert restored.builder_chat_model_config.model == "gpt-4.1-mini"
    assert restored.planned_agents[0].suggested_tools[0].id == "travel:plan"
    assert restored.planned_agents[0].suggested_knowledge_bases[0].id == "travel-policy"
