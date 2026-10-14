"""Agent Spec rendering, diff and patch rules."""

import pytest

from agentscope.app._agent_spec import (
    AgentSpec,
    SpecOperation,
    SpecPatchError,
    SpecRule,
    SpecTool,
    apply_operations,
    diff_specs,
    render_prompt,
    spec_from_legacy,
    spec_hash,
)
from agentscope.app._agent_templates import TEMPLATES, template_list
from agentscope.app._workforce_policy import (
    BUSINESS_AGENT_EVIDENCE_POLICY,
    governed_system_prompt,
)


def _spec() -> AgentSpec:
    return AgentSpec(
        name="Trợ lý kỹ thuật",
        description="Tiếp nhận sự cố điện nước.",
        audience="cư dân",
        tone="bình tĩnh",
        goal="Phân loại sự cố và hướng dẫn an toàn.",
        scope_out=["Thông tin cá nhân của thợ"],
        rules=[
            SpecRule(text="Hướng dẫn sơ cứu trước", level="must"),
            SpecRule(text="Trả lời ngắn", level="should"),
            SpecRule(text="Hỏi số căn hộ trước khi tra lịch", source="agent", learned_from="ticket-1"),
        ],
        tools=[SpecTool(tool_id="m:lookup", mcp_id="m", tool_name="lookup", use_when="cần phân loại")],
    )


def test_render_puts_each_decision_in_its_section() -> None:
    prompt = render_prompt(_spec())

    assert prompt.startswith("You are Trợ lý kỹ thuật. Tiếp nhận sự cố điện nước.")
    assert "RULES YOU MUST FOLLOW\n- Hướng dẫn sơ cứu trước" in prompt
    assert "PREFERRED PRACTICES\n- Trả lời ngắn" in prompt
    assert "OUT OF SCOPE" in prompt and "Thông tin cá nhân của thợ" in prompt
    assert "- lookup: use when cần phân loại" in prompt
    # Learned lessons are listed separately, after the manager's rules.
    assert prompt.rstrip().endswith("- Hỏi số căn hộ trước khi tra lịch")


def test_prompt_override_keeps_learned_lessons() -> None:
    spec = _spec().model_copy(update={"prompt_override": "Custom prompt by the manager."})
    prompt = render_prompt(spec)

    assert prompt.startswith("Custom prompt by the manager.")
    assert "Hỏi số căn hộ" in prompt
    assert "RULES YOU MUST FOLLOW" not in prompt


def test_legacy_agent_keeps_an_identical_runtime_prompt() -> None:
    authored = "You are the hotel agent. Search before answering."
    governed = governed_system_prompt("business", authored)
    spec = spec_from_legacy(
        name="Hotel",
        description="Find hotels",
        system_prompt=governed,
        bindings=[{"id": "m:search", "mcp_id": "m", "tool_name": "search"}],
        policy=BUSINESS_AGENT_EVIDENCE_POLICY,
    )

    assert governed_system_prompt("business", render_prompt(spec)) == governed
    assert spec.tools[0].tool_name == "search"


def test_operations_add_update_remove_and_diff() -> None:
    before = _spec()
    after = apply_operations(
        before,
        [
            SpecOperation(op="add", field="rules", value={"text": "Không báo giá khi chưa có ảnh"}),
            SpecOperation(op="set", field="tone", value="thân thiện"),
            SpecOperation(op="remove", field="scope_out", item_id="Thông tin cá nhân của thợ"),
        ],
        author="builder",
    )
    changes = {(c.field, c.action) for c in diff_specs(before, after)}

    assert ("rules", "added") in changes
    assert ("tone", "changed") in changes
    assert ("scope_out", "removed") in changes
    added = next(r for r in after.rules if r.text.startswith("Không báo giá"))
    assert added.source == "builder"
    assert spec_hash(before) != spec_hash(after)


def test_agents_cannot_touch_manager_or_locked_rules() -> None:
    spec = _spec()
    manager_rule = spec.rules[0].id
    learned_rule = spec.rules[2].id

    with pytest.raises(SpecPatchError):
        apply_operations(
            spec,
            [SpecOperation(op="remove", field="rules", item_id=manager_rule)],
            author="agent",
        )
    changed = apply_operations(
        spec,
        [SpecOperation(op="update", field="rules", item_id=learned_rule, value={"text": "Hỏi số căn hộ và toà"})],
        author="agent",
    )
    assert any(r.text == "Hỏi số căn hộ và toà" for r in changed.rules)


def test_invalid_patch_changes_nothing() -> None:
    spec = _spec()
    with pytest.raises(SpecPatchError):
        apply_operations(
            spec,
            [
                SpecOperation(op="set", field="tone", value="vui"),
                SpecOperation(op="remove", field="rules", item_id="missing"),
            ],
            author="manager",
        )
    assert spec.tone == "bình tĩnh"


def test_templates_are_valid_and_testable() -> None:
    assert {"travel_cost", "travel_lookup", "resident_technical", "resident_cleaning"} <= set(TEMPLATES)
    for item in template_list():
        spec = AgentSpec.model_validate(item["spec"])
        assert len(spec.tests) >= 3
        assert spec.rules


def test_builder_made_agent_gets_a_spec_with_its_tests() -> None:
    from agentscope.agent import ContextConfig, ReActConfig
    from agentscope.app._router._workforce_console import _seed_spec
    from agentscope.app.storage import AgentData, AgentRecord

    record = AgentRecord(
        user_id="u",
        data=AgentData(
            name="Hotel",
            system_prompt=governed_system_prompt("business", "Find hotels."),
            context_config=ContextConfig(),
            react_config=ReActConfig(),
            lifecycle_state="published",
            build_description="Find hotels",
        ),
    )
    _seed_spec(
        record,
        [{"scenario": f"case {i}", "expected": "uses search"} for i in range(3)],
    )

    assert len(record.data.spec["tests"]) == 3
    assert record.data.published_version == 1
    assert record.data.versions[0]["spec"]["tests"][0]["scenario"] == "case 0"
