"""Eval cases fail only for agent defects (local scripted models only)."""
import json
from types import SimpleNamespace

import pytest

from agentscope.app._agent_spec import AgentSpec, SpecTest, SpecTool
from agentscope.app._service import _agent_eval as evaluation
from agentscope.message import TextBlock, ToolCallBlock
from agentscope.model import ChatResponse

SEARCH = {"type": "object", "properties": {"city": {"type": "string"}}}


class _Status(Exception):
    def __init__(self, status):
        super().__init__(f"HTTP {status}")
        self.status_code = status


class ScriptedModel:
    """Calls ``tool`` once, then answers; fixture and judge replies are canned.

    Eval shallow-copies the model per role, so counters live in shared lists.
    """

    def __init__(self, tool, fail_first=None):
        self.tool, self.fail_first, self.log = tool, fail_first, []

    @property
    def calls(self):
        return self.log.count("agent")

    @property
    def fixture_calls(self):
        return self.log.count("fixture")

    async def __call__(self, messages, **_):
        self.log.append("agent")
        if self.fail_first is not None and self.calls == 1:
            raise self.fail_first
        if not any(getattr(m, "role", "") == "assistant" for m in messages):
            return ChatResponse(content=[ToolCallBlock(id="t", name=self.tool, input=json.dumps({"city": "Đà Nẵng"}))], is_last=True)
        return ChatResponse(content=[TextBlock(text="Có 2 khách sạn, giá 2,650,000 VND.")], is_last=True)

    async def generate_structured_output(self, messages, structured_model, **_):
        if structured_model is evaluation._FixtureOutput:
            self.log.append("fixture")
            return SimpleNamespace(content={"output": json.dumps({"hotels": [{"name": "A", "price": 2650000}]})})
        return SimpleNamespace(content={"passed": True, "reason": "Đúng.", "criteria": [
            {"name": name, "passed": True, "reason": "ok"} for name in ("task_completion", "evidence", "scope_safety", "tool_use")]})


def _spec(tool, consent=False):
    return AgentSpec(name="Du lịch",
        tools=[SpecTool(tool_id=f"m:{tool}", mcp_id="m", tool_name=tool, requires_consent=consent)],
        tests=[SpecTest(scenario="Tìm khách sạn Đà Nẵng.", expected="Tra cứu và báo giá.", must_include=["2.650.000"])])


async def _never(*_):
    pytest.fail("An unannotated tool must never reach the live connector in eval")


@pytest.fixture(autouse=True)
def _no_pause(monkeypatch):
    monkeypatch.setattr(evaluation, "_RETRY_DELAYS", (0.0, 0.0))


@pytest.mark.asyncio
async def test_unannotated_search_gets_generated_data_without_a_ticket():
    model = ScriptedModel("search_hotels")
    report = await evaluation.run_spec_tests(spec=_spec("search_hotels"), model=model, judge_model=model,
        discovered={"m:search_hotels": {"read_only": False, "input_schema": SEARCH}}, run_tool=_never)
    result = report["results"][0]
    assert result["tool_calls"][0]["mode"] == "fixture"
    assert "hotels" in result["tool_calls"][0]["output"]
    assert "handover" not in result
    assert result["status"] == "passed", result
    assert report["environment"]["mode"] == "generated_reads"


@pytest.mark.asyncio
async def test_owner_marked_consent_is_recorded_as_assumed():
    model = ScriptedModel("search_hotels")
    report = await evaluation.run_spec_tests(spec=_spec("search_hotels", consent=True), model=model, judge_model=model,
        discovered={"m:search_hotels": {"read_only": False, "requires_consent": True, "input_schema": SEARCH}}, run_tool=_never)
    call = report["results"][0]["tool_calls"][0]
    assert (call["mode"], call.get("consent_assumed")) == ("fixture", True)


@pytest.mark.asyncio
async def test_sensitive_action_stays_simulated():
    model = ScriptedModel("book_hotel")
    report = await evaluation.run_spec_tests(spec=_spec("book_hotel"), model=model, judge_model=model,
        discovered={"m:book_hotel": {"read_only": False, "input_schema": SEARCH}}, run_tool=_never)
    assert report["results"][0]["tool_calls"][0]["mode"] == "simulated"
    assert model.fixture_calls == 0


@pytest.mark.asyncio
async def test_rate_limited_model_call_is_retried_instead_of_losing_the_case():
    model = ScriptedModel("search_hotels", fail_first=_Status(429))
    report = await evaluation.run_spec_tests(spec=_spec("search_hotels"), model=model, judge_model=model,
        discovered={"m:search_hotels": {"read_only": False, "input_schema": SEARCH}}, run_tool=_never)
    assert report["results"][0]["status"] == "passed"


@pytest.mark.asyncio
async def test_invalid_credentials_are_not_retried():
    model = ScriptedModel("search_hotels", fail_first=_Status(401))
    report = await evaluation.run_spec_tests(spec=_spec("search_hotels"), model=model, judge_model=model,
        discovered={"m:search_hotels": {"read_only": False, "input_schema": SEARCH}}, run_tool=_never)
    assert (report["results"][0]["status"], report["results"][0]["error_kind"]) == ("error", "model")
    assert model.calls == 1


def test_figures_match_whatever_the_thousands_separator():
    test = SpecTest(scenario="x", expected="y", must_include=["2.650.000"], must_not_include=["3.000.000"])
    for answer in ("Giá 2,650,000 VND", "Giá 2 650 000 VND", "Giá 2650000 VND"):
        assert all(c["passed"] for c in evaluation.deterministic_checks(test, {"answer": answer, "tool_calls": []}))
    assert not evaluation.deterministic_checks(test, {"answer": "Giá 2.65 triệu", "tool_calls": []})[0]["passed"]


@pytest.mark.asyncio
@pytest.mark.parametrize("tool", ["create_ticket", "assign_technician", "vh_work_order_reschedule", "vh_ticket_add_note"])
async def test_a_tool_that_may_write_never_gets_generated_success(tool):
    model = ScriptedModel(tool)
    report = await evaluation.run_spec_tests(spec=_spec(tool, consent=True), model=model, judge_model=model,
        discovered={f"m:{tool}": {"read_only": False, "requires_consent": True, "input_schema": SEARCH}}, run_tool=_never)
    assert report["results"][0]["tool_calls"][0]["mode"] == "simulated"
    assert model.fixture_calls == 0


@pytest.mark.parametrize("tool,expected", [
    ("check_hotel_availability", True), ("get_flight_details", True), ("calculate_expression", True),
    ("vh_travel_prepare", False), ("update_details", False), ("book_flight", False),
])
def test_read_names(tool, expected):
    assert evaluation._named_as_read(tool) is expected


@pytest.mark.asyncio
async def test_failed_fixture_generation_is_an_environment_error():
    class NoFixture(ScriptedModel):
        async def generate_structured_output(self, messages, structured_model, **kwargs):
            if structured_model is evaluation._FixtureOutput:
                raise _Status(401)
            return await super().generate_structured_output(messages, structured_model, **kwargs)

    model = NoFixture("search_hotels")
    report = await evaluation.run_spec_tests(spec=_spec("search_hotels"), model=model, judge_model=model,
        discovered={"m:search_hotels": {"read_only": False, "input_schema": SEARCH}}, run_tool=_never)
    result = report["results"][0]
    assert (result["status"], result["error_kind"]) == ("error", "environment")
