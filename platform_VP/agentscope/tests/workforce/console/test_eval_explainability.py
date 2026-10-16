"""Evaluation regressions reproduced with local models and connectors only."""
import json
from types import SimpleNamespace

import pytest

from agentscope.app._agent_spec import AgentSpec, SpecTest, SpecTool
from agentscope.app._service import _agent_eval as evaluation
from agentscope.app._service import _agent_studio as studio
from agentscope.message import TextBlock, ToolCallBlock, ToolResultState
from agentscope.model import ChatResponse
from agentscope.tool import ToolResponse


class TravelModel:
    def __init__(self):
        self.judge_calls = 0
        self.judge_prompt = ""

    async def __call__(self, messages, **_):
        if len(messages) == 2:
            return ChatResponse(content=[ToolCallBlock(id="lookup", name="vh_travel_catalog", input="{}")], is_last=True)
        return ChatResponse(content=[TextBlock(text="Chưa đủ quyền ticket để tra cứu.")], is_last=True)

    async def generate_structured_output(self, messages, **_):
        self.judge_calls += 1
        self.judge_prompt = "\n".join(message.get_text_content() for message in messages)
        return SimpleNamespace(content={"passed": False, "reason": "Không tìm khách sạn."})


def travel_spec():
    return AgentSpec(name="Du lịch", tools=[SpecTool(tool_id="m:vh_travel_catalog", mcp_id="m", tool_name="vh_travel_catalog")],
        tests=[SpecTest(scenario="Tìm khách sạn Đà Nẵng cho hai người.", expected="Tra cứu và báo kết quả.")])


@pytest.mark.asyncio
async def test_ticket_grant_failure_is_environment_error_not_false_agent_verdict(monkeypatch):
    async def tool(**_):
        return ToolResponse(state=ToolResultState.ERROR, content=[TextBlock(text=json.dumps({
            "status": "failed", "error": {"code": "TICKET_GRANT_REQUIRED", "message": "Cần Bearer grant được cấp riêng cho ticket."}}))])
    tool.is_read_only = True

    class Client:
        is_stateful = False

        @classmethod
        def model_validate(cls, _): return cls()

        async def get_tool(self, _): return tool

    record = SimpleNamespace(enabled=True, discovered_tools=[{"name": "vh_travel_catalog", "read_only": True}],
        client=SimpleNamespace(confirm_tools=[], model_dump=lambda **_: {}))

    class Storage:
        async def get_mcp(self, *_): return record

    monkeypatch.setattr(studio, "MCPClient", Client)
    model = TravelModel()
    report = await evaluation.run_spec_tests(spec=travel_spec(), model=model, judge_model=model,
        discovered={"m:vh_travel_catalog": {"read_only": True}}, run_tool=studio.tool_runner(Storage(), "u", travel_spec()))
    assert report["errors"] == 1
    assert report["results"][0]["status"] == "error"
    assert report["results"][0]["tool_calls"][0]["mode"] == "error"
    assert model.judge_calls == 0
    assert not report["publishable"]


@pytest.mark.asyncio
async def test_judge_receives_tool_outputs_not_only_names_and_arguments():
    model = TravelModel()
    result = await evaluation.judge(model, travel_spec(), travel_spec().tests[0], {
        "answer": "Danh mục hiện chưa có khách sạn phù hợp.", "tool_calls": [{"name": "vh_travel_catalog",
            "arguments": {}, "executed": True, "mode": "read_only", "output": "CATALOG_EMPTY_VERIFIED"}]})
    assert result.passed is False
    assert "CATALOG_EMPTY_VERIFIED" in model.judge_prompt


@pytest.mark.asyncio
async def test_tool_business_error_output_is_retained_for_human_review():
    model = TravelModel()

    async def run_tool(*_):
        return json.dumps({"status": "failed", "error": {"code": "TICKET_GRANT_REQUIRED", "message": "Cần quyền ticket."}})

    report = await evaluation.run_spec_tests(spec=travel_spec(), model=model, judge_model=model,
        discovered={"m:vh_travel_catalog": {"read_only": True}}, run_tool=run_tool)
    assert report["errors"] == 1
    assert "TICKET_GRANT_REQUIRED" in report["results"][0]["tool_calls"][0]["output"]


@pytest.mark.asyncio
async def test_internal_team_report_is_available_without_production_delivery():
    class Model:
        async def __call__(self, tools, **_):
            assert "TeamSay" in [tool["function"]["name"] for tool in tools]
            return ChatResponse(content=[ToolCallBlock(id="report", name="TeamSay", input=json.dumps({
                "kind": "result", "content": "Không có khách sạn phù hợp; cần hỏi thêm ngày."}))], is_last=True)

        async def generate_structured_output(self, **_):
            return SimpleNamespace(content={"passed": True, "reason": "Đã báo cáo đúng giới hạn."})

    async def no_connector(*_):
        pytest.fail("Simulated TeamSay must never contact a production peer")

    spec = AgentSpec(name="Travel", tests=[SpecTest(scenario="Tìm phòng.", expected="Báo thiếu dữ liệu.", must_include=["ngày"])])
    model = Model()
    events = []

    async def event(value): events.append(value)

    report = await evaluation.run_spec_tests(spec=spec, model=model, judge_model=model, discovered={}, run_tool=no_connector, on_progress=event)
    assert report["results"][0]["passed"]
    assert report["results"][0]["tool_calls"][0]["fixture_accepted"]
    assert [event["stage"] for event in events] == ["tests_ready", "running", "checking", "judging", "case_completed"]
    assert report["metrics"]["simulated_calls"] == 1


@pytest.mark.asyncio
async def test_progress_is_persisted_scoped_and_does_not_duplicate_full_transcripts():
    from agentscope.app._service._eval_progress import EvalProgress, progress_view
    from agentscope.app._router._workforce_console import builder_progress
    from agentscope.app.storage import ChatModelConfig, SessionConfig, SessionRecord
    from fastapi import HTTPException
    config = SessionConfig(workspace_id="builder", chat_model_config=ChatModelConfig(type="openai_credential", credential_id="offline", model="offline", parameters={}))
    session = SessionRecord(user_id="u", agent_id="workforce-builder", id="builder", config=config)

    class Storage:
        async def get_session(self, user_id, agent_id, session_id):
            return session.model_copy(deep=True) if (user_id, agent_id, session_id) == ("u", "workforce-builder", "builder") else None

        async def update_session_state(self, user_id, agent_id, session_id, state):
            assert (user_id, agent_id, session_id) == ("u", "workforce-builder", "builder")
            session.state = state.model_copy(deep=True)

    storage = Storage()
    progress = EvalProgress(storage, "u", session)
    await progress.stage("generating")
    assert (await builder_progress("builder", "u", storage))["stage"] == "generating"
    with pytest.raises(HTTPException) as denied:
        await builder_progress("builder", "another-owner", storage)
    assert denied.value.status_code == 404
    await progress.event({"stage": "tests_ready", "agent_name": "Travel", "tests": [{"id": "test", "scenario": "Find hotel", "expected": "Ask dates"}]})
    await progress.event({"stage": "case_completed", "test_id": "test", "result": {"status": "error", "passed": False, "error": "Missing grant", "error_kind": "environment", "tool_calls": [{"output": "private evidence"}]}})
    await progress.finish()
    view = progress_view(session)
    assert view["status"] == "completed"
    assert view["agents"][0]["tests"][0]["result"]["error_kind"] == "environment"
    assert "private evidence" not in str(view)
    session.state.middle_context["evaluation_progress"].update(status="running", updated_at="2020-01-01T00:00:00+00:00")
    assert progress_view(session)["status"] == "interrupted"


@pytest.mark.asyncio
async def test_builder_retest_keeps_exact_frozen_spec(monkeypatch):
    from agentscope.app._agent_spec import spec_hash
    from agentscope.app._router import _workforce_console as console
    spec = travel_spec()
    item = console.ProposedAgentView(name=spec.name, objective="Travel", system_prompt="Prompt", selected_tools=[],
        skill_name="travel", skill_markdown="Skill", tests=[], spec=spec.model_dump(mode="json"), evaluation={"checks": {"static": True}})
    captured = []

    async def evaluate(**kwargs):
        captured.append(spec_hash(kwargs["spec"]))
        return {"pass_rate": 0, "spec_hash": spec_hash(spec)}

    async def catalog(*_): return {}
    monkeypatch.setattr(evaluation, "run_spec_tests", evaluate)
    monkeypatch.setattr(studio, "tool_catalog", catalog)
    await console._evaluate_proposed_agent(item, object(), "u", object())
    assert captured == [spec_hash(spec)]
    assert item.spec == spec.model_dump(mode="json")


def test_case_latency_percentiles_use_nearest_rank():
    spec = travel_spec()
    results = [{"test_id": str(n), "passed": True, "latency_ms": n} for n in range(1, 21)]
    metrics = evaluation.evaluation_metrics(spec, results)
    assert (metrics["p50_ms"], metrics["p95_ms"]) == (10, 19)


@pytest.mark.asyncio
async def test_hallucinated_tool_is_not_accepted_as_a_simulated_action():
    model = TravelModel()

    async def no_connector(*_):
        pytest.fail("Unknown tool must never reach a connector")

    report = await evaluation.run_spec_tests(spec=AgentSpec(name="No tools", tests=travel_spec().tests),
        model=model, judge_model=None, discovered={}, run_tool=no_connector)
    result = report["results"][0]
    assert result["passed"] is False
    assert result["tool_calls"][0]["error_code"] == "UNKNOWN_TOOL"
    assert result["checks"][0]["passed"] is False
