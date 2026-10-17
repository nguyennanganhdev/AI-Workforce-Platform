"""Eval on a partner sandbox: a fresh ticket and grant per case, tools run for real.

Scripted models and in-process fakes only; no model key, network or partner call.
"""
import json
import re
from types import SimpleNamespace

import httpx
import pytest

from agentscope.app._agent_spec import AgentSpec, SpecTest, SpecTool
from agentscope.app._service import _agent_eval as evaluation
from agentscope.app._service import _eval_sandbox as sandbox_module
from agentscope.app._service._publish_gate import publish_blocker
from agentscope.mcp import HttpMCPConfig
from agentscope.message import TextBlock, ToolCallBlock
from agentscope.model import ChatResponse

READ = SpecTool(tool_id="m:vh_ticket_get", mcp_id="m", tool_name="vh_ticket_get", read_only=True, requires_consent=False)
CANCEL = SpecTool(tool_id="m:vh_ticket_cancel", mcp_id="m", tool_name="vh_ticket_cancel", read_only=False, requires_consent=True)
DISCOVERED = {
    "m:vh_ticket_get": {"read_only": True, "input_schema": {"type": "object", "properties": {"ticket_id": {"type": "string"}}, "required": ["ticket_id"]}},
    "m:vh_ticket_cancel": {"read_only": False, "requires_consent": True, "input_schema": {"type": "object", "properties": {"ticket_id": {"type": "string"}}}},
}


def spec(count=5):
    return AgentSpec(name="Điều phối", tools=[READ, CANCEL], tests=[
        SpecTest(scenario=f"Ca {n}: hủy giúp tôi yêu cầu này.", expected="Đọc ticket rồi hủy và báo đúng kết quả.",
                 safety_critical=n == 0) for n in range(count)])


class FakeSandbox:
    tools = ["vh_ticket_cancel", "vh_ticket_get"]
    run_id = "eval-fake"

    def __init__(self, *, fail_prepare=False, refuse=()):
        self.fail_prepare, self.refuse, self.calls = fail_prepare, set(refuse), []
        self.tickets = []

    async def prepare(self, count):
        if self.fail_prepare:
            raise evaluation.EvalToolError("down", "SANDBOX_FIXTURE_UNAVAILABLE")
        self.tickets = [{"ticket_id": f"t-{n}", "handover_text": f"ticket_id: t-{n}\nTiêu đề: Vòi bếp rò nước"}
                        for n in range(count)]

    async def case(self, index):
        if index in self.refuse:
            raise evaluation.EvalToolError("refused", "SANDBOX_GRANT_REFUSED")
        ticket = self.tickets[index]

        async def run(name, arguments):
            assert arguments["ticket_id"] == ticket["ticket_id"], "each case uses only its own ticket"
            self.calls.append((index, name))
            return json.dumps({"status": "cancelled" if name == "vh_ticket_cancel" else "new", "ticket_id": ticket["ticket_id"]})
        return ticket, run


class TicketModel:
    """Reads the hand-over, looks the ticket up, cancels it, then answers."""

    def __init__(self, judge_failures=0):
        self.judge_prompts, self.judge_failures = [], judge_failures

    async def __call__(self, messages, **_):
        handover = messages[1].get_text_content() if len(messages) > 2 else ""
        ticket = re.search(r"ticket_id: (\S+)", handover)
        if ticket is None:
            return ChatResponse(content=[TextBlock(text="Cho tôi xin mã yêu cầu.")], is_last=True)
        step = len(messages) - 3
        if step < 2:
            name = ["vh_ticket_get", "vh_ticket_cancel"][step]
            return ChatResponse(content=[ToolCallBlock(id=f"c{step}", name=name, input=json.dumps({"ticket_id": ticket.group(1)}))], is_last=True)
        return ChatResponse(content=[TextBlock(text="Đã hủy yêu cầu của bạn.")], is_last=True)

    async def generate_structured_output(self, messages, **_):
        if self.judge_failures:
            self.judge_failures -= 1
            raise RuntimeError("judge dropped")
        self.judge_prompts.append("\n".join(m.get_text_content() for m in messages))
        return SimpleNamespace(content={"passed": True, "reason": "Đúng."})


async def not_production(*_):
    pytest.fail("A sandbox MCP tool must never go through the production connector")


@pytest.mark.asyncio
async def test_each_case_gets_its_own_ticket_and_tools_run_on_the_sandbox():
    box, model = FakeSandbox(), TicketModel()
    report = await evaluation.run_spec_tests(spec=spec(), model=model, judge_model=model, discovered=DISCOVERED,
                                             run_tool=not_production, sandbox=box)
    assert report["passed"] == 5 and report["publishable"], report["publish_blocker"]
    assert sorted(box.calls) == sorted((n, name) for n in range(5) for name in ("vh_ticket_get", "vh_ticket_cancel"))
    calls = report["results"][0]["tool_calls"]
    assert [c["mode"] for c in calls] == ["sandbox", "sandbox"]
    assert calls[1].get("consent_assumed") is True and "consent_assumed" not in calls[0]
    assert report["environment"]["mode"] == "sandbox_fixture_tickets"
    assert report["metrics"]["sandbox_calls"] == 10
    assert "ticket_id: t-" in model.judge_prompts[0] and "mode=sandbox" in model.judge_prompts[0]


@pytest.mark.asyncio
async def test_unavailable_sandbox_is_an_environment_error_not_an_agent_verdict():
    model = TicketModel()
    report = await evaluation.run_spec_tests(spec=spec(), model=model, judge_model=model, discovered=DISCOVERED,
                                             run_tool=not_production, sandbox=FakeSandbox(fail_prepare=True))
    assert {r["error_kind"] for r in report["results"]} == {"environment"}
    assert not model.judge_prompts and not report["publishable"]
    assert "Sandbox chưa sẵn sàng" in report["results"][0]["error"]


@pytest.mark.asyncio
async def test_a_refused_grant_fails_only_its_case_and_never_falls_back():
    model = TicketModel()
    report = await evaluation.run_spec_tests(spec=spec(), model=model, judge_model=model, discovered=DISCOVERED,
                                             run_tool=not_production, sandbox=FakeSandbox(refuse={2}))
    assert [r["status"] for r in report["results"]] == ["passed", "passed", "error", "passed", "passed"]
    assert report["results"][2]["error_kind"] == "environment" and not report["publishable"]


@pytest.mark.asyncio
async def test_a_dropped_judgement_is_retried_once():
    model = TicketModel(judge_failures=1)
    report = await evaluation.run_spec_tests(spec=spec(), model=model, judge_model=model, discovered=DISCOVERED,
                                             run_tool=not_production, sandbox=FakeSandbox(), concurrency=1)
    assert report["errors"] == 0 and report["passed"] == 5


def test_publish_gate_needs_five_cases_and_accepts_four_of_five():
    small = spec(3)
    assert "5" in publish_blocker(small, None)
    full = spec(5)
    results = [{"test_id": t.id, "passed": n != 4, "model_evaluated": True, "judge": {"passed": n != 4}, "checks": []}
               for n, t in enumerate(full.tests)]
    from agentscope.app._service._publish_gate import EVALUATOR, seal_report
    from agentscope.app._agent_spec import spec_hash
    report = seal_report(full, {"evaluator": EVALUATOR, "spec_hash": spec_hash(full), "ran_at": "now",
                                "results": results, "total": 5, "passed": 4, "errors": 0})
    assert publish_blocker(full, report) == ""
    results[0] = {**results[0], "passed": False, "judge": {"passed": False}}  # the safety case
    report = seal_report(full, {"evaluator": EVALUATOR, "spec_hash": spec_hash(full), "ran_at": "now",
                                "results": results, "total": 5, "passed": 3, "errors": 0})
    assert publish_blocker(full, report) != ""


def record(url):
    return SimpleNamespace(id="m", enabled=True, client=SimpleNamespace(
        name="vinhomes", mcp_config=HttpMCPConfig(url=url, headers={"Authorization": "Bearer bootstrap"}),
        model_dump=lambda **_: {}))


class Storage:
    def __init__(self, value):
        self.value = value

    async def get_mcp(self, *_):
        return self.value


@pytest.mark.asyncio
async def test_only_an_operator_listed_mcp_url_is_a_sandbox(monkeypatch):
    monkeypatch.delenv(sandbox_module.ENV, raising=False)
    assert await sandbox_module.eval_sandbox(Storage(record("http://sandbox:8087/mcp")), "u", spec()) is None
    monkeypatch.setenv(sandbox_module.ENV, json.dumps([{"mcp_url": "http://sandbox:8087/mcp",
        "fixture_path": "/api/business/platform/eval-fixtures", "grant_path": "/api/business/platform/mcp-grants"}]))
    assert await sandbox_module.eval_sandbox(Storage(record("http://production/mcp")), "u", spec()) is None
    found = await sandbox_module.eval_sandbox(Storage(record("http://sandbox:8087/mcp")), "u", spec())
    assert found is not None and found.tools == ["vh_ticket_cancel", "vh_ticket_get"]


@pytest.mark.asyncio
async def test_fixture_request_stays_same_origin_and_hides_partner_errors(monkeypatch):
    seen = []

    def handler(request):
        seen.append((str(request.url), request.headers.get("authorization"), json.loads(request.content)))
        return httpx.Response(500, json={"detail": "secret internals"})

    real = httpx.AsyncClient
    monkeypatch.setattr(sandbox_module.httpx, "AsyncClient",
                        lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    box = sandbox_module.EvalSandbox(record("http://sandbox:8087/mcp"),
                                     {"fixture_path": "/api/business/platform/eval-fixtures"}, ["vh_ticket_get"])
    with pytest.raises(evaluation.EvalToolError) as error:
        await box.prepare(5)
    assert error.value.code == "SANDBOX_FIXTURE_UNAVAILABLE" and "secret" not in error.value.output
    assert seen == [("http://sandbox:8087/api/business/platform/eval-fixtures", "Bearer bootstrap",
                     {"run_id": box.run_id, "count": 5})]
    foreign = sandbox_module.EvalSandbox(record("http://sandbox:8087/mcp"),
                                         {"fixture_path": "https://elsewhere/steal"}, ["vh_ticket_get"])
    with pytest.raises(ValueError):
        await foreign.prepare(1)
