"""Focused contract tests for the Workforce Builder console."""

from agentscope.agent import ContextConfig, ReActConfig
from agentscope.app._router._schema import MCPView
from agentscope.app._router._workforce_console import (
    _LEADER_PROMPT,
    BuilderOutline,
    GeneratedAgent,
    PrepareRequest,
    ProposalView,
    _claim_exclusive_tool_ids,
    _normalise_skill,
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


def test_builder_and_leader_follow_the_users_language_naturally() -> None:
    assert _response_language("Hãy tạo cho tôi một team agent") == "vi"
    assert _response_language("Please create a travel agent team") == "en"
    assert _response_language("OK", "Tôi muốn tạo agent khách sạn") == "vi"
    assert "latest message" in _LEADER_PROMPT
    assert "Vietnamese" in _LEADER_PROMPT
    assert "English" in _LEADER_PROMPT
    assert "helpful person" in _LEADER_PROMPT


def test_leader_requires_verified_agent_evidence_for_domain_answers() -> None:
    assert "orchestrator, not a source" in _LEADER_PROMPT
    assert "always require verified evidence" in _LEADER_PROMPT
    assert "Never answer these from pretrained" in _LEADER_PROMPT
    assert "could not be verified" in _LEADER_PROMPT
    assert "wait for the integrator's plan" in _LEADER_PROMPT
    assert "Review CONTENT only" in _LEADER_PROMPT


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


def test_runtime_prompt_policy_overrides_stale_leader_and_wraps_business() -> None:
    assert governed_system_prompt("leader", "old prompt") == WORKFORCE_LEADER_PROMPT
    governed = governed_system_prompt("business", "Hotel specialist")
    assert BUSINESS_AGENT_EVIDENCE_POLICY in governed
    assert governed_system_prompt("business", governed) == governed
    # The platform prompts are domain-neutral: business rules such as a
    # travel budget reserve belong to that business's agents.
    for domain_word in ("hotel", "reserve", "vehicle", "cuisine", "itinerary"):
        assert domain_word not in WORKFORCE_LEADER_PROMPT.casefold()
        assert domain_word not in BUSINESS_AGENT_EVIDENCE_POLICY.casefold()
    assert "done_when" in WORKFORCE_LEADER_PROMPT
    assert "depends_on" in WORKFORCE_LEADER_PROMPT


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
