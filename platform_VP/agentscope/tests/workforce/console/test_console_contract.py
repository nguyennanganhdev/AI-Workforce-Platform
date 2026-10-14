"""Focused contract tests for the Workforce Builder console."""

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from agentscope.agent import ContextConfig, ReActConfig
from agentscope.app._router._schema import MCPView
from agentscope.app._router._workforce_console import (
    _LEADER_PROMPT,
    BuilderKnowledgeBase,
    BuilderGeneration,
    BuilderOutline,
    BuilderTool,
    GeneratedAgent,
    PrepareRequest,
    ProposalView,
    _agent_tool_settings,
    _claim_exclusive_tool_ids,
    _execution_mode_matches_tools,
    _ensure_attraction_generation_coverage,
    _ensure_attraction_outline_coverage,
    _group_tool_catalog,
    _normalise_skill,
    _replace_agent_session_knowledge,
    _replace_agent_workspace_mcps,
    _resolve_selected_knowledge_bases,
    _resolve_selected_tools,
    _response_language,
    _select_model_name,
    _similarity,
    _stored_proposal,
)
from agentscope.app._workforce_policy import (
    BUSINESS_AGENT_EVIDENCE_POLICY,
    WORKFORCE_LEADER_PROMPT,
    governed_system_prompt,
)
from agentscope.app.storage import AgentData, ChatModelConfig, MCPRecord
from agentscope.mcp import HttpMCPConfig, MCPClient
from agentscope.message import AssistantMsg


def test_agent_schema_does_not_expose_server_owned_builder_fields() -> None:
    schema = AgentData.model_json_schema()

    assert "system_role" not in schema["properties"]
    assert "lifecycle_state" not in schema["properties"]
    assert "tool_bindings" not in schema["properties"]
    assert "knowledge_base_ids" not in schema["properties"]
    assert "execution_mode" not in schema["properties"]
    assert "evaluation" not in schema["properties"]
    assert "context_config" in schema["properties"]
    assert "react_config" in schema["properties"]
    assert ContextConfig().trigger_ratio == 0.8
    assert ReActConfig() is not None


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


def test_skill_normalisation_adds_safe_front_matter() -> None:
    agent = GeneratedAgent(
        name="Hotel Agent",
        objective="Tìm phòng: theo ngân sách của khách",
        execution_mode="tool_backed",
        system_prompt="Act only on verified hotel inventory and report tool results.",
        selected_tool_ids=["mcp-1:search_rooms"],
        skill_name="Hotel Search",
        skill_markdown="# Workflow\n\nSearch, compare, then report verified options.",
    )

    skill = _normalise_skill(agent)

    assert skill.startswith("---\nname: hotel-search\n")
    assert 'description: "Tìm phòng: theo ngân sách của khách"' in skill
    assert "# Workflow" in skill


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


def test_builder_follows_user_language_and_leader_answers_in_vietnamese() -> None:
    assert _response_language("Hãy tạo cho tôi một team agent") == "vi"
    assert _response_language("Please create a travel agent team") == "en"
    assert _response_language("OK", "Tôi muốn tạo agent khách sạn") == "vi"
    assert "Always answer the customer in natural Vietnamese" in _LEADER_PROMPT
    assert "helpful person" in _LEADER_PROMPT


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
                {"name": "Plan Agent", "objective": "Lập kế hoạch chuyến đi"},
                {
                    "name": "Hotel Agent",
                    "objective": "Tìm và đặt khách sạn",
                    "suggested_tool_ids": ["travel:search_hotels"],
                },
            ],
        },
    )

    assert [agent.name for agent in outline.agents] == [
        "Plan Agent",
        "Hotel Agent",
    ]


def test_builder_materializes_requested_attraction_specialist_and_tools() -> None:
    tools = [
        BuilderTool(
            id="travel:search_attractions",
            mcp_id="travel",
            mcp_name="Travel",
            tool_name="search_attractions",
        ),
        BuilderTool(
            id="travel:book_attraction_ticket",
            mcp_id="travel",
            mcp_name="Travel",
            tool_name="book_attraction_ticket",
        ),
    ]
    outline = _ensure_attraction_outline_coverage(
        BuilderOutline(
            agents=[
                {
                    "name": "Agent Lập Kế Hoạch",
                    "objective": "Lập lịch trình tổng thể",
                    "suggested_tool_ids": ["travel:search_attractions"],
                },
            ],
        ),
        "Tư vấn địa điểm vui chơi tại Phú Quốc",
        tools,
    )

    assert len(outline.agents) == 2
    assert outline.agents[0].suggested_tool_ids == []
    attraction = outline.agents[1]
    assert attraction.name == "Agent Địa Điểm Vui Chơi"
    assert set(attraction.suggested_tool_ids) == {tool.id for tool in tools}

    generation = _ensure_attraction_generation_coverage(
        BuilderGeneration(),
        "Tư vấn địa điểm vui chơi tại Phú Quốc",
        tools,
        "vi",
    )
    assert len(generation.agents) == 1
    assert generation.agents[0].execution_mode == "tool_backed"
    assert set(generation.agents[0].selected_tool_ids) == {
        tool.id for tool in tools
    }


def test_runtime_prompt_policy_overrides_stale_leader_and_wraps_business() -> None:
    assert governed_system_prompt("leader", "old prompt") == WORKFORCE_LEADER_PROMPT
    governed = governed_system_prompt("business", "Hotel specialist")
    assert BUSINESS_AGENT_EVIDENCE_POLICY in governed
    assert governed_system_prompt("business", governed) == governed
    stale = (
        "Hotel specialist\n\nWORKFORCE RUNTIME EVIDENCE POLICY:\n"
        "- stale rule"
    )
    refreshed = governed_system_prompt("business", stale)
    assert "stale rule" not in refreshed
    assert refreshed.count("WORKFORCE RUNTIME EXECUTION POLICY:") == 1
    assert "assemble the right team" in WORKFORCE_LEADER_PROMPT
    assert "ask the customer for task-specific" in WORKFORCE_LEADER_PROMPT
    assert "specialist that needs customer-owned information asks" in (
        WORKFORCE_LEADER_PROMPT
    )
    assert "Follow the authored business role" in governed
    assert "booking, payment, cancellation" in governed
    assert "Never ask the customer to type a confirmation" in governed
    assert "`unpaid_demo` means the booking" in governed


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
        chat_model_config=ChatModelConfig(
            type="openai_credential",
            credential_id="credential-1",
            model="gpt-4o-mini",
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
