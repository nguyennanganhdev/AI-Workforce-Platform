"""A planned agent that does the job of an existing one: the manager chooses to update, reuse or create."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from agentscope.agent import ContextConfig, ReActConfig
from agentscope.app._router import _workforce_console as console
from agentscope.app.storage import AgentData, AgentRecord, ChatModelConfig
from agentscope.message import AssistantMsg

CONFIG = ChatModelConfig(type="openai_credential", credential_id="c", model="gpt-6-luna", parameters={})
CLEANING = "Tiếp nhận phản ánh vệ sinh khu vực chung, đánh giá phạm vi dọn dẹp và chuyển điều phối"


def existing(agent_id, name, objective, tools=(), state="published"):
    return AgentRecord(id=agent_id, user_id="u", source="user", data=AgentData(
        name=name, system_role="business", lifecycle_state=state, build_description=objective,
        system_prompt="Bạn là " + name, context_config=ContextConfig(), react_config=ReActConfig(),
        spec={"name": name, "tools": [{"tool_id": tool, "mcp_id": "m", "tool_name": tool.split(":")[1]} for tool in tools]}))


def test_similar_agents_are_found_by_job_or_by_tools():
    agents = [existing("a1", "Agent Vệ Sinh", CLEANING),
              existing("a2", "Agent An Ninh", "Xử lý sự việc an ninh, người lạ", tools=["m:vh_ticket_get", "m:vh_guard"])]
    same_job = console._similar_agent("Tiếp nhận phản ánh vệ sinh khu vực chung và đánh giá phạm vi dọn dẹp", set(), agents)
    assert (same_job.agent_id, same_job.published) == ("a1", True) and same_job.score >= 0.4
    same_tools = console._similar_agent("Bảo vệ tòa nhà", {"m:vh_guard", "m:vh_ticket_get"}, agents)
    assert same_tools.agent_id == "a2" and same_tools.score == 1.0
    assert console._similar_agent("Báo cáo doanh thu hằng ngày cho kế toán", set(), agents) is None


def _run(decisions, generated, records):
    planned = console.ProposalView(
        conversation_id="b1", status="needs_input", assistant_message="Dàn ý", chat_model_config=CONFIG, fixed_config={},
        planned_agents=[console.PlannedAgentView(name="Vệ Sinh", objective=CLEANING, similar=console.SimilarAgentView(
            agent_id="a1", name="Agent Vệ Sinh", score=0.8, published=True))])
    message = AssistantMsg(name="builder", content="Dàn ý", structured_output={"workforce_builder_proposal": planned.model_dump(mode="json")})
    generate = AsyncMock(return_value=(console.BuilderGeneration(agents=generated), 10, 10))
    seen = {}

    async def evaluate(item, *_args, **_kw):
        item.spec = {"name": item.name}
        item.evaluation["passed"] = True

    async def persist(_storage, _user, _session, _message, proposal):
        seen["proposal"] = proposal

    storage = SimpleNamespace(list_agents=AsyncMock(return_value=records))
    with patch.multiple(console,
                        _list_all_builder_messages=AsyncMock(return_value=[message]),
                        _catalog=AsyncMock(return_value=[]), _library=AsyncMock(return_value=({}, {})),
                        get_model=AsyncMock(), _prepare_builder_memory=AsyncMock(return_value="Hội thoại"),
                        _generate=generate, _record_builder_prompt_measurement=AsyncMock(),
                        _evaluate_proposed_agent=evaluate, _persist_builder_turn=persist):
        result = asyncio.run(console._prepare_builder(
            console.PrepareRequest(message="Tôi xác nhận", chat_model_config=CONFIG, confirm_outline=True, decisions=decisions),
            "u", storage, object(), SimpleNamespace(id="b1"), None))
    return result, generate


def agent(name):
    return console.GeneratedAgent(name=name, objective=CLEANING, system_prompt="Bạn đánh giá phạm vi vệ sinh " * 3,
                                  needs_tools=False, skill_name="ve-sinh", skill_markdown="# Vệ sinh\nLàm việc an toàn.")


def test_an_undecided_similar_agent_stops_generation():
    with pytest.raises(HTTPException) as exc:
        _run({}, [agent("Vệ Sinh")], [existing("a1", "Agent Vệ Sinh", CLEANING)])
    assert exc.value.status_code == 409 and "Vệ Sinh" in exc.value.detail


def test_reuse_keeps_the_existing_agent_and_does_not_generate_a_copy():
    result, generate = _run({"Vệ Sinh": "reuse"}, [agent("Vệ Sinh")], [existing("a1", "Agent Vệ Sinh", CLEANING)])
    assert [(item.name, item.reuse_agent_id) for item in result.agents] == [("Agent Vệ Sinh", "a1")]
    assert result.status == "ready"
    note = generate.await_args.args[0]
    assert "Do not generate 'Vệ Sinh'" in note and "EXISTING AGENTS" in note


def test_update_publishes_a_new_version_of_the_existing_agent():
    result, generate = _run({"Vệ Sinh": "update"}, [agent("Agent Vệ Sinh")], [existing("a1", "Agent Vệ Sinh", CLEANING)])
    [item] = result.agents
    assert (item.update_agent_id, item.update_agent_name, item.reuse_agent_id) == ("a1", "Agent Vệ Sinh", None)
    assert "keeping the name 'Agent Vệ Sinh'" in generate.await_args.args[0]


def test_create_keeps_a_separate_new_agent():
    result, _ = _run({"Vệ Sinh": "create"}, [agent("Vệ Sinh")], [existing("a1", "Agent Vệ Sinh", CLEANING)])
    [item] = result.agents
    assert (item.update_agent_id, item.reuse_agent_id) == (None, None)


def test_publishing_an_update_adds_a_version_to_the_existing_agent_and_reuse_creates_nothing():
    from datetime import UTC, datetime

    from agentscope.app._agent_spec import AgentSpec, SpecTest, spec_hash
    from agentscope.app._service._publish_gate import EVALUATOR, seal_report

    spec = AgentSpec(name="Agent Vệ Sinh", tests=[SpecTest(id=f"t{n}", scenario=f"Hỏi {n}", expected="An toàn",
                                                          safety_critical=n == 0) for n in range(5)])
    report = seal_report(spec, {"spec_hash": spec_hash(spec), "evaluator": EVALUATOR, "ran_at": datetime.now(UTC).isoformat(),
        "total": 5, "passed": 5, "pass_rate": 1., "errors": 0, "model_error": None,
        "results": [{"test_id": t.id, "passed": True, "model_evaluated": True, "judge": {"passed": True}, "checks": [],
                     "error": None} for t in spec.tests]})
    old = existing("a1", "Agent Vệ Sinh", CLEANING)
    old.data.invite_config.invitable = True
    guard = existing("a2", "Agent An Ninh", "An ninh")
    guard.data.invite_config.invitable = True
    update = console.ProposedAgentView(name="Agent Vệ Sinh", objective=CLEANING, system_prompt="Bạn " * 20,
        selected_tools=[], skill_name="", skill_markdown="", spec=spec.model_dump(mode="json"),
        evaluation={"passed": True, "checks": {"static": True}, "model_report": report},
        update_agent_id="a1", update_agent_name="Agent Vệ Sinh")
    reuse = console.ProposedAgentView(name="Agent An Ninh", objective="An ninh", system_prompt="x", selected_tools=[],
        skill_name="", skill_markdown="", evaluation={"passed": True, "checks": {}, "reused": True},
        reuse_agent_id="a2", reuse_agent_name="Agent An Ninh")
    proposal = console.ProposalView(conversation_id="b1", proposal_id="p1", revision=1, status="ready",
        assistant_message="ok", chat_model_config=CONFIG, fixed_config={}, agents=[update, reuse])
    message = AssistantMsg(name="builder", content="ok", structured_output={"workforce_builder_proposal": proposal.model_dump(mode="json")})
    saved = []
    storage = SimpleNamespace(get_session=AsyncMock(return_value=object()), list_messages=AsyncMock(return_value=([message], False)),
        get_agent=AsyncMock(side_effect=lambda _u, agent_id: {"a1": old, "a2": guard}[agent_id]),
        claim_builder_publish=AsyncMock(return_value=True), upsert_message=AsyncMock(),
        upsert_agent=AsyncMock(side_effect=lambda _u, record: saved.append(record)))
    with patch.object(console, "_primary_session", AsyncMock(return_value=SimpleNamespace(id="s1"))), \
         patch("agentscope.app._service._agent_studio.apply_bindings", AsyncMock()):
        result = asyncio.run(console.publish_builder(console.PublishRequest(conversation_id="b1", proposal_id="p1",
                                                                           expected_revision=1), SimpleNamespace(), "u", storage, object()))
    assert [(a.agent_id, a.updated, a.reused) for a in result.agents] == [("a1", True, False), ("a2", False, True)]
    [record] = saved
    assert record.id == "a1" and record.data.lifecycle_state == "published" and record.data.published_version >= 1


def test_only_passed_publishes_the_passing_agents_and_keeps_the_rest_to_fix():
    from datetime import UTC, datetime

    from agentscope.app._agent_spec import AgentSpec, SpecTest, spec_hash
    from agentscope.app._service._publish_gate import EVALUATOR, seal_report

    spec = AgentSpec(name="Agent Vệ Sinh", tests=[SpecTest(id=f"t{n}", scenario=f"Hỏi {n}", expected="An toàn",
                                                          safety_critical=n == 0) for n in range(5)])
    report = seal_report(spec, {"spec_hash": spec_hash(spec), "evaluator": EVALUATOR, "ran_at": datetime.now(UTC).isoformat(),
        "total": 5, "passed": 5, "pass_rate": 1., "errors": 0, "model_error": None,
        "results": [{"test_id": t.id, "passed": True, "model_evaluated": True, "judge": {"passed": True}, "checks": [],
                     "error": None} for t in spec.tests]})
    old = existing("a1", "Agent Vệ Sinh", CLEANING)
    passing = console.ProposedAgentView(name="Agent Vệ Sinh", objective=CLEANING, system_prompt="Bạn " * 20,
        selected_tools=[], skill_name="", skill_markdown="", spec=spec.model_dump(mode="json"),
        evaluation={"passed": True, "checks": {"static": True}, "model_report": report},
        update_agent_id="a1", update_agent_name="Agent Vệ Sinh")
    failing = console.ProposedAgentView(name="Agent Đặt Phòng", objective="Đặt phòng", system_prompt="Bạn " * 20,
        selected_tools=[], skill_name="", skill_markdown="", spec={"name": "Agent Đặt Phòng"},
        evaluation={"passed": False, "checks": {"static": True}, "publish_blocker": "Kiểm thử đạt 3/5"})
    proposal = console.ProposalView(conversation_id="b1", proposal_id="p1", revision=1, status="blocked",
        assistant_message="ok", chat_model_config=CONFIG, fixed_config={}, agents=[passing, failing])
    message = AssistantMsg(name="builder", content="ok", structured_output={"workforce_builder_proposal": proposal.model_dump(mode="json")})
    saved = []
    storage = SimpleNamespace(get_session=AsyncMock(return_value=object()), list_messages=AsyncMock(return_value=([message], False)),
        get_agent=AsyncMock(return_value=old), claim_builder_publish=AsyncMock(return_value=True), upsert_message=AsyncMock(),
        upsert_agent=AsyncMock(side_effect=lambda _u, record: saved.append(record)))

    def publish(only_passed):
        return asyncio.run(console.publish_builder(console.PublishRequest(conversation_id="b1", proposal_id="p1",
            expected_revision=1, only_passed=only_passed), SimpleNamespace(), "u", storage, object()))

    with patch.object(console, "_primary_session", AsyncMock(return_value=SimpleNamespace(id="s1"))), \
         patch("agentscope.app._service._agent_studio.apply_bindings", AsyncMock()):
        with pytest.raises(HTTPException) as exc:
            publish(False)
        assert exc.value.status_code == 409 and not saved
        result = publish(True)
    assert [(a.agent_id, a.updated) for a in result.agents] == [("a1", True)]
    assert [record.id for record in saved] == ["a1"]
    kept = console.ProposalView.model_validate(
        storage.upsert_message.await_args.args[2].structured_output["workforce_builder_proposal"])
    assert kept.status == "blocked" and kept.proposal_id != "p1" and kept.revision == 2
    assert [(item.name, item.reuse_agent_id) for item in kept.agents] == [("Agent Vệ Sinh", "a1"), ("Agent Đặt Phòng", None)]
    assert "Agent Đặt Phòng" in storage.upsert_message.await_args.args[2].get_text_content()


def test_the_library_note_stays_valid_json_and_counts_what_it_leaves_out():
    import json

    skills = {f"s{n}": {"skill_id": f"s{n}", "name": f"Skill {n}", "description": "mô tả " * 200, "markdown": "x" * 5000}
              for n in range(40)}
    note = console._library_note({}, skills)
    listing = note.split("Library skills (reuse by skill_id):\n")[1]
    shown, _, rest = listing.partition(" (+")
    entries = json.loads(shown)
    assert entries and all("markdown" not in entry and len(entry["description"]) <= 300 for entry in entries)
    assert rest.startswith(f"{40 - len(entries)} more not shown")


def _failing_proposal(round_=0):
    tests = [{"scenario": f"Ca {n}", "expected": "An toàn", "safety_critical": n == 0} for n in range(5)]
    report = {"pass_rate": 0.4, "results": [{"scenario": "Ca 1", "expected": "Tra phiếu", "passed": False,
               "judge": {"reason": "Không tra phiếu", "criteria": [{"name": "task_completion", "passed": False, "reason": "x"}]},
               "answer": "Mình chưa rõ", "tool_calls": []}]}
    item = console.ProposedAgentView(name="Agent Vệ Sinh", objective=CLEANING, system_prompt="Cũ " * 40, selected_tools=[],
        skill_name="ve-sinh", skill_markdown="# Vệ sinh", tests=tests, spec={"name": "Agent Vệ Sinh"},
        evaluation={"passed": False, "checks": {"static": True}, "model_report": report,
                    **({"repair": {"round": round_}} if round_ else {})})
    return console.ProposalView(conversation_id="b1", proposal_id="p1", revision=4, status="blocked", assistant_message="",
        chat_model_config=CONFIG, fixed_config={}, agents=[item])


def _repair(proposal, plan):
    message = AssistantMsg(name="builder", content="", structured_output={"workforce_builder_proposal": proposal.model_dump(mode="json")})
    seen = {}

    async def evaluate(item, *_args, **_kw):
        seen["spec"] = dict(item.spec)
        item.evaluation["passed"] = True

    async def persist(_s, _u, _sid, _m, saved):
        seen["saved"] = saved

    progress = SimpleNamespace(stage=AsyncMock(), finish=AsyncMock(), fail=AsyncMock())
    storage = SimpleNamespace(get_session=AsyncMock(return_value=SimpleNamespace(id="b1")))
    with patch.multiple(console, _list_all_builder_messages=AsyncMock(return_value=[message]), get_model=AsyncMock(),
                        _builder_structured_call=AsyncMock(return_value=(SimpleNamespace(content=plan), 1, 1)),
                        _evaluate_proposed_agent=evaluate, _persist_builder_turn=persist), \
         patch("agentscope.app._service._eval_progress.EvalProgress", return_value=progress):
        result = asyncio.run(console.repair_builder(console.PublishRequest(conversation_id="b1", proposal_id="p1",
                                                                         expected_revision=4), "u", storage, object()))
    return result, seen


def test_repair_corrects_the_prompt_and_evaluates_again_without_publishing():
    plan = {"explanation": "Agent không tra phiếu; đã thêm luật tra phiếu trước khi trả lời.",
            "system_prompt": "Bạn là Agent Vệ Sinh. Luôn tra phiếu bằng công cụ trước khi trả lời. " * 3,
            "tests": [{"scenario": "Ca 1", "expected": "x", "safety_critical": False}]}  # weakens safety: ignored
    result, seen = _repair(_failing_proposal(), plan)
    [item] = result.agents
    assert "Luôn tra phiếu" in item.system_prompt and seen["spec"] == {}
    assert len(item.tests) == 5 and item.tests[0]["safety_critical"]
    assert item.evaluation["repair"] == {"round": 1, "explanation": plan["explanation"], "changed": ["prompt"],
                                         "previous_pass_rate": 0.4}
    assert (result.status, result.revision) == ("ready", 5) and seen["saved"] is result


def test_repair_stops_after_the_allowed_rounds():
    with pytest.raises(HTTPException) as exc:
        _repair(_failing_proposal(round_=2), {"explanation": "x"})
    assert exc.value.status_code == 409
