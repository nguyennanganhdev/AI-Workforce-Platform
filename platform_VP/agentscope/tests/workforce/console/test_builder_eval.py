"""Builder eval with a scripted model: no provider is ever called."""

import json
from unittest import IsolatedAsyncioTestCase

from agentscope.app._service import _builder_eval as builder_eval
from agentscope.message import TextBlock, ToolCallBlock
from agentscope.model import ChatResponse

HOTEL = builder_eval.EvalAgent(
    name="Agent Khách sạn",
    objective="Tìm khách sạn theo điểm đến, ngày và ngân sách.",
    system_prompt="Bạn là Agent Khách sạn. Tìm và so sánh khách sạn, không bịa giá.",
    skill_markdown="# Khách sạn\nDùng search_hotels để tra cứu.",
    tools=[
        {"tool_name": "search_hotels", "description": "Tìm khách sạn", "input_schema": {
            "type": "object", "properties": {"city": {"type": "string"}}}},
        {"tool_name": "book_hotel", "description": "Đặt phòng", "input_schema": {"type": "object"}},
    ],
)


class _Structured:
    def __init__(self, content):
        self.content = content


class _ScriptedModel:
    """Answers structured calls by schema and chat calls from a script."""

    def __init__(self, *, chat, cases=None, verdict=True, judge_error=None):
        self.chat = list(chat)
        self.cases = cases or [
            {"scenario": "Tìm khách sạn ở Đà Nẵng", "expected": "Tra cứu và đưa lựa chọn", "expect_tool": "search_hotels"},
            {"scenario": "Đặt giúp tôi vé máy bay", "expected": "Từ chối lịch sự, ngoài phạm vi", "safety": True},
        ]
        self.verdict = verdict
        self.judge_error = judge_error
        self.judged = 0

    async def generate_structured_output(self, messages, structured_model, **kwargs):
        if structured_model is builder_eval._CaseSet:
            return _Structured({"cases": self.cases})
        if structured_model is builder_eval._Fixture:
            return _Structured({"output": json.dumps({"hotel": "Sala", "price": "1.450.000"})})
        self.judged += 1
        if self.judge_error and self.judged == 1:
            raise self.judge_error
        return _Structured({"criteria": [
            {"name": name, "passed": self.verdict, "reason": "ok"} for name in builder_eval.CRITERIA
        ], "summary": "ok"})

    async def __call__(self, messages, tools=None, **kwargs):
        return self.chat.pop(0)


def _text(text):
    return ChatResponse(content=[TextBlock(text=text)], is_last=True)


def _tool(name, args):
    return ChatResponse(content=[ToolCallBlock(id=f"c-{name}", name=name, input=json.dumps(args))], is_last=True)


class TestBuilderEval(IsolatedAsyncioTestCase):
    def test_read_and_write_tools_are_told_apart_by_name(self):
        self.assertTrue(builder_eval.is_read_tool("search_hotels"))
        self.assertTrue(builder_eval.is_read_tool("get_service_catalog"))
        self.assertFalse(builder_eval.is_read_tool("book_hotel"))
        self.assertFalse(builder_eval.is_read_tool("search_and_book"))

    async def test_cases_never_expect_a_tool_the_agent_lacks(self):
        model = _ScriptedModel(chat=[], cases=[
            {"scenario": "a", "expected": "b", "expect_tool": "send_email"},
        ])
        cases = await builder_eval.generate_cases(model, HOTEL)
        self.assertEqual(cases[0].expect_tool, "")

    async def test_reads_get_generated_data_and_writes_are_simulated(self):
        model = _ScriptedModel(chat=[
            _tool("search_hotels", {"city": "Đà Nẵng"}),
            _tool("book_hotel", {"hotel": "Sala"}),
            _text("Đã tìm thấy Sala, 1.450.000đ/đêm."),
        ])
        case = builder_eval.EvalCase(scenario="Tìm và đặt", expected="Tra cứu")
        transcript = await builder_eval.run_case(model, HOTEL, case)
        self.assertEqual([c["mode"] for c in transcript["tool_calls"]], ["fixture", "simulated"])
        self.assertIn("SIMULATED", transcript["tool_calls"][1]["output"])
        self.assertEqual(transcript["answer"], "Đã tìm thấy Sala, 1.450.000đ/đêm.")

    async def test_unknown_tool_fails_the_deterministic_check(self):
        model = _ScriptedModel(chat=[_tool("delete_everything", {}), _text("Xong.")])
        case = builder_eval.EvalCase(scenario="x", expected="y")
        transcript = await builder_eval.run_case(model, HOTEL, case)
        checks = builder_eval.deterministic_checks(case, transcript)
        self.assertFalse(next(c for c in checks if c["name"] == "known_tools")["passed"])

    async def test_full_run_reports_progress_and_an_advisory_pass_rate(self):
        model = _ScriptedModel(chat=[
            _tool("search_hotels", {"city": "Đà Nẵng"}), _text("Có 3 khách sạn."),
            _text("Xin lỗi, tôi chỉ hỗ trợ khách sạn."),
        ])
        progress = builder_eval.new_progress("p1", 2, [HOTEL])
        snapshots = []

        async def on_progress(value):
            snapshots.append(value["agents"][0]["stage"])

        result = await builder_eval.evaluate_proposal(model, [HOTEL], progress, on_progress)
        agent = result["agents"][0]
        self.assertEqual(result["status"], "completed")
        self.assertEqual([t["status"] for t in agent["tests"]], ["passed", "passed"])
        self.assertEqual(agent["report"]["pass_rate"], 1.0)
        self.assertTrue(agent["report"]["advisory"])
        self.assertIn("generating", snapshots)
        self.assertIn("running", snapshots)

    async def test_a_broken_case_is_reported_and_the_rest_still_run(self):
        model = _ScriptedModel(
            chat=[_tool("search_hotels", {}), _text("Có 3 khách sạn."), _text("Ngoài phạm vi.")],
            judge_error=TimeoutError(),
        )
        progress = builder_eval.new_progress("p1", 1, [HOTEL])
        result = await builder_eval.evaluate_proposal(model, [HOTEL], progress)
        statuses = sorted(t["status"] for t in result["agents"][0]["tests"])
        self.assertEqual(statuses, ["error", "passed"])
        self.assertEqual(result["agents"][0]["report"]["errors"], 1)
        self.assertNotIn("Traceback", json.dumps(result, ensure_ascii=False))


class TestBuilderEvalRoutes(IsolatedAsyncioTestCase):
    """POST /builder/evaluate runs in the background and saves into the proposal."""

    async def asyncSetUp(self):
        from types import SimpleNamespace
        from unittest.mock import AsyncMock

        from agentscope.app._router import _workforce_console as console
        from agentscope.message import AssistantMsg
        from tests.workforce.console.test_builder_resources import CONFIG

        self.console = console
        proposal = console.ProposalView(
            conversation_id="builder", proposal_id="p1", revision=3, status="ready",
            assistant_message="Built", chat_model_config=CONFIG, fixed_config={},
            agents=[console.ProposedAgentView(
                name=HOTEL.name, objective=HOTEL.objective, system_prompt=HOTEL.system_prompt,
                selected_tools=[console.BuilderTool(id="m:search_hotels", mcp_id="m", mcp_name="Travel",
                                                    tool_name="search_hotels", input_schema={"type": "object"})],
                skill_name="hotel", skill_markdown=HOTEL.skill_markdown, evaluation={"passed": True},
            )],
        )
        self.message = AssistantMsg("builder", "Built", structured_output={
            "workforce_builder_proposal": proposal.model_dump(mode="json"),
        })
        self.storage = SimpleNamespace(
            get_session=AsyncMock(return_value=SimpleNamespace(id="builder")),
            list_messages=AsyncMock(side_effect=lambda *a, **k: ([self.message], False)),
            upsert_message=AsyncMock(),
        )
        self.model = _ScriptedModel(chat=[
            _tool("search_hotels", {}), _text("Có 3 khách sạn."), _text("Ngoài phạm vi."),
        ])

    async def test_evaluate_runs_in_background_and_saves_the_report(self):
        from unittest.mock import AsyncMock, patch

        with patch.object(self.console, "get_model", AsyncMock(return_value=self.model)):
            started = await self.console.evaluate_builder(
                self.console.EvaluateRequest(conversation_id="builder", proposal_id="p1", expected_revision=3),
                "user", self.storage, access=None,
            )
            self.assertEqual(started["status"], "running")
            await self.console._eval_tasks[("user", "builder")]
        saved = self.message.structured_output["workforce_builder_proposal"]["agents"][0]["evaluation"]["eval"]
        self.assertEqual(saved["report"]["passed"], 2)
        self.storage.upsert_message.assert_awaited_once()
        self.console._eval_runs.clear()
        view = await self.console.get_builder_eval("builder", "user", self.storage)
        self.assertEqual(view["status"], "completed")
        self.assertEqual(view["agents"][0]["name"], HOTEL.name)

    async def test_stale_revision_is_rejected(self):
        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as error:
            await self.console.evaluate_builder(
                self.console.EvaluateRequest(conversation_id="builder", proposal_id="p1", expected_revision=2),
                "user", self.storage, access=None,
            )
        self.assertEqual(error.exception.status_code, 409)


class TestBuilderEvalLimits(TestBuilderEvalRoutes):
    async def test_another_users_conversation_eval_is_not_readable(self):
        from unittest.mock import AsyncMock

        from fastapi import HTTPException

        self.storage.get_session = AsyncMock(return_value=None)
        with self.assertRaises(HTTPException) as error:
            await self.console.get_builder_eval("builder", "intruder", self.storage)
        self.assertEqual(error.exception.status_code, 404)

    async def test_running_evals_per_user_are_bounded(self):
        import asyncio

        from fastapi import HTTPException

        blocker = asyncio.Event()
        tasks = [asyncio.create_task(blocker.wait()) for _ in range(self.console._EVAL_RUNS_PER_USER)]
        for index, task in enumerate(tasks):
            self.console._eval_tasks[("user", f"other-{index}")] = task
        try:
            with self.assertRaises(HTTPException) as error:
                await self.console.evaluate_builder(
                    self.console.EvaluateRequest(conversation_id="builder", proposal_id="p1", expected_revision=3),
                    "user", self.storage, access=None,
                )
            self.assertEqual(error.exception.status_code, 429)
        finally:
            blocker.set()
            await asyncio.gather(*tasks)
            self.console._eval_tasks.clear()

    async def test_eval_starts_per_day_are_bounded(self):
        import time

        from fastapi import HTTPException

        self.console._eval_starts["user"] = [time.time()] * self.console._EVAL_STARTS_PER_DAY
        try:
            with self.assertRaises(HTTPException) as error:
                await self.console.evaluate_builder(
                    self.console.EvaluateRequest(conversation_id="builder", proposal_id="p1", expected_revision=3),
                    "user", self.storage, access=None,
                )
            self.assertEqual(error.exception.status_code, 429)
        finally:
            self.console._eval_starts.clear()

    async def test_deleting_a_conversation_cancels_its_running_eval(self):
        import asyncio
        from unittest.mock import AsyncMock

        task = asyncio.create_task(asyncio.Event().wait())
        self.console._eval_tasks[("user", "builder")] = task
        self.console._eval_runs[("user", "builder")] = {"status": "running"}
        self.storage.delete_session = AsyncMock()

        await self.console.delete_builder_conversation("builder", "user", self.storage)
        await asyncio.sleep(0)

        self.assertTrue(task.cancelled())
        self.assertNotIn(("user", "builder"), self.console._eval_tasks)
        self.assertNotIn(("user", "builder"), self.console._eval_runs)

    async def test_concurrent_leader_bootstraps_create_one_leader(self):
        import asyncio
        from types import SimpleNamespace
        from unittest.mock import AsyncMock, patch

        agents: list = []

        async def list_agents(_user):
            await asyncio.sleep(0)
            return list(agents)

        async def upsert_agent(_user, record):
            await asyncio.sleep(0)
            agents.append(record)

        storage = SimpleNamespace(list_agents=list_agents, upsert_agent=upsert_agent)
        session = SimpleNamespace(id="s", config=SimpleNamespace(workspace_id="w", name="Ticket"))
        workspace = SimpleNamespace(default_mcps=[])
        manager = SimpleNamespace(get_workspace=AsyncMock(return_value=workspace))
        with (
            patch.object(self.console, "_primary_session", AsyncMock(return_value=session)),
            patch.object(self.console, "_model_config", AsyncMock(return_value=None)),
        ):
            await asyncio.gather(
                self.console._leader("user", storage, manager),
                self.console._leader("user", storage, manager),
            )

        self.assertEqual(len(agents), 1)

    async def test_tool_calls_per_step_are_capped(self):
        calls = [ToolCallBlock(id=f"c{i}", name="search_hotels", input="{}") for i in range(10)]
        model = _ScriptedModel(chat=[ChatResponse(content=calls, is_last=True), _text("Xong.")])
        transcript = await builder_eval.run_case(model, HOTEL, builder_eval.EvalCase(scenario="x", expected="y"))
        modes = [c["mode"] for c in transcript["tool_calls"]]
        self.assertEqual(modes.count("fixture"), builder_eval.MAX_TOOL_CALLS_PER_STEP)
        self.assertEqual(modes.count("skipped"), 10 - builder_eval.MAX_TOOL_CALLS_PER_STEP)
