"""Run an Agent Spec's test scenarios with the real model before publishing.

Each scenario is played as one customer message against the rendered prompt
and the agent's tool schemas. Read-only MCP tools are really called so the
agent can answer from data; every other tool call is answered with a
"simulated, not executed" result, so a test can never book, pay or create a
work order. A judge model then checks the transcript against the scenario's
expected behaviour, on top of the deterministic must/must-not checks.
"""

from __future__ import annotations

import asyncio
import json
import time
import unicodedata
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from ..._logging import logger
from ...message import (
    AssistantMsg,
    Msg,
    SystemMsg,
    TextBlock,
    ToolCallBlock,
    ToolResultBlock,
    ToolResultState,
    UserMsg,
)
from ...model import ChatModelBase, ChatResponse
from .._agent_spec import AgentSpec, SpecTest, render_prompt, spec_hash
from .._workforce_policy import governed_system_prompt
from ._publish_gate import MIN_TESTS_TO_PUBLISH, PASS_THRESHOLD, seal_report
from ...model._call_observer import usage_purpose

ToolRunner = Callable[[str, dict], Awaitable[str]]
"""Execute one read-only tool by name with arguments; return its text."""


def catalog_allows_read(meta: dict) -> bool:
    """Only an explicit server classification can authorize a sandbox read.

    Missing or non-boolean metadata fails closed. A spec may demand more
    consent, but it can never turn a write or unknown tool into a read.
    """

    return meta.get("read_only") is True and meta.get("requires_consent", False) is False


_MODEL_ERRORS = {
    "quota": "Tài khoản model hết credit — nạp tiền cho API key hoặc đổi credential.",
    "authentication": "API key của model không hợp lệ — kiểm tra credential.",
    "rate_limit": "Model đang giới hạn tốc độ — thử lại sau ít phút.",
    "connection": "Không kết nối được tới model.",
}


def _model_error(exc: Exception) -> str:
    """Why the model could not be called, for the manager (no raw text)."""
    from ._errors import _classify_type

    kind = _classify_type(exc).value
    return _MODEL_ERRORS.get(kind, f"Không gọi được model ({kind}).")


class _Judgement(BaseModel):
    passed: bool
    reason: str = Field(description="One or two sentences in Vietnamese.")


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold()).replace("đ", "d")
    return "".join(c for c in decomposed if not unicodedata.combining(c))


async def _complete(model: ChatModelBase, messages: list[Msg], tools: list[dict]) -> ChatResponse:
    response = await model(messages=messages, tools=tools or None)
    if isinstance(response, ChatResponse):
        return response
    final: ChatResponse | None = None
    async for chunk in response:
        if chunk.is_last:
            final = chunk
    if final is None:
        raise RuntimeError("model stream ended without a final response")
    return final


def tool_schemas(spec: AgentSpec, discovered: dict[str, dict]) -> list[dict]:
    """OpenAI-style function schemas for the spec's tools."""

    schemas = []
    for tool in spec.tools:
        meta = discovered.get(tool.tool_id, {})
        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": tool.tool_name,
                    "description": (
                        (meta.get("description") or "")
                        + (f" Use when {tool.use_when}." if tool.use_when else "")
                    ).strip()
                    or tool.tool_name,
                    "parameters": meta.get("input_schema") or {"type": "object", "properties": {}},
                },
            },
        )
    return schemas


@usage_purpose("eval")
async def run_scenario(
    *,
    spec: AgentSpec,
    test: SpecTest,
    model: ChatModelBase,
    schemas: list[dict],
    run_tool: ToolRunner,
    read_only: set[str],
    max_steps: int = 4,
    simulated_tools: set[str] | None = None,
) -> dict[str, Any]:
    """Play one scenario; return the transcript used for checks."""

    system = governed_system_prompt("business", render_prompt(spec))
    messages: list[Msg] = [
        SystemMsg(name="system", content=system),
        UserMsg(name="customer", content=test.scenario),
    ]
    calls: list[dict] = []
    answer = ""
    for _ in range(max_steps):
        response = await _complete(model, messages, schemas)
        tool_calls = [b for b in response.content if isinstance(b, ToolCallBlock)]
        text = "".join(b.text for b in response.content if isinstance(b, TextBlock))
        if not tool_calls:
            answer = text
            break
        blocks: list = [*response.content]
        for call in tool_calls:
            try:
                args = json.loads(call.input or "{}")
            except json.JSONDecodeError:
                args = {}
            if call.name in read_only:
                try:
                    output = await run_tool(call.name, args)
                    executed = True
                    mode = "read_only"
                except Exception as exc:  # noqa: BLE001 - reported in transcript
                    output = f"TOOL ERROR: {exc}"
                    executed = False
                    mode = "error"
            else:
                output = (
                    "SIMULATED: this action was NOT executed during testing. "
                    "No production record or message was created. Do not claim actual completion. "
                    "Follow the tool's server-owned permission and consent policy."
                )
                if call.name in (simulated_tools or set()):
                    output = "SIMULATED: message accepted by the isolated peer/Leader fixture; no production message delivered."
                executed = False
                mode = "simulated"
            calls.append({"name": call.name, "arguments": args, "executed": executed, "mode": mode,
                          **({"fixture_accepted": True} if call.name in (simulated_tools or set()) else {})})
            blocks.append(
                ToolResultBlock(
                    id=call.id,
                    name=call.name,
                    output=[TextBlock(text=output[:8000])],
                    state=ToolResultState.SUCCESS,
                ),
            )
        messages.append(AssistantMsg(name=spec.name, content=blocks))
    else:
        answer = answer or "(agent did not finish within the step limit)"
    return {"answer": answer, "tool_calls": calls}


def deterministic_checks(test: SpecTest, transcript: dict) -> list[dict]:
    folded = _fold(transcript["answer"])
    checks = [
        {"name": f"có '{phrase}'", "passed": _fold(phrase) in folded}
        for phrase in test.must_include
    ]
    checks += [
        {"name": f"không có '{phrase}'", "passed": _fold(phrase) not in folded}
        for phrase in test.must_not_include
    ]
    if test.expect_tool:
        called = [call["name"] for call in transcript["tool_calls"]]
        checks.append(
            {"name": f"gọi tool {test.expect_tool}", "passed": test.expect_tool in called},
        )
    return checks


@usage_purpose("eval_judge")
async def judge(
    model: ChatModelBase,
    spec: AgentSpec,
    test: SpecTest,
    transcript: dict,
) -> _Judgement:
    prompt = (
        "Bạn kiểm thử một AI agent của doanh nghiệp. Chấm agent có làm ĐÚNG "
        "hành vi mong đợi không. Chỉ dựa vào kịch bản, hành vi mong đợi, luật của "
        "agent và bản ghi bên dưới. Lời gọi tool có 'executed: false' là hành động "
        "đã bị chặn trong môi trường thử, không phải lỗi của agent.\n\n"
        "Với fixture_accepted:true, tin nhắn nội bộ đã được peer/Leader fixture tiếp nhận thành công; "
        "được nói đã báo/chuyển nội bộ trong ca thử. Điều này KHÔNG chứng minh giao việc, ghi dữ liệu, "
        "nghiệm thu hay đóng phiếu nghiệp vụ thật. Chấm cả nội dung TeamSay như phần trả lời, "
        "vì Leader là người chuyển hướng dẫn/câu hỏi cho cư dân.\n\n"
        f"LUẬT CỦA AGENT:\n{json.dumps([r.text for r in spec.rules], ensure_ascii=False)}\n\n"
        f"KHÁCH NÓI: {test.scenario}\n"
        f"HÀNH VI MONG ĐỢI: {test.expected}\n\n"
        f"TOOL ĐÃ GỌI: {json.dumps(transcript['tool_calls'], ensure_ascii=False)[:4000]}\n"
        f"AGENT TRẢ LỜI:\n{transcript['answer'][:6000]}"
    )
    response = await model.generate_structured_output(
        messages=[UserMsg(name="reviewer", content=prompt)],
        structured_model=_Judgement,
    )
    return _Judgement.model_validate(response.content)


async def run_spec_tests(
    *,
    spec: AgentSpec,
    model: ChatModelBase,
    judge_model: ChatModelBase | None,
    discovered: dict[str, dict],
    run_tool: ToolRunner,
    concurrency: int = 3,
    simulated_tool_schemas: list[dict] | None = None,
) -> dict[str, Any]:
    """Run every test of ``spec``; return a report tied to the spec hash."""

    schemas = tool_schemas(spec, discovered)
    simulated_names = {item["function"]["name"] for item in simulated_tool_schemas or []}
    if simulated_names.intersection(tool.tool_name for tool in spec.tools):
        raise ValueError("A simulated runtime tool cannot replace a registered MCP tool")
    schemas.extend(simulated_tool_schemas or [])
    name_counts: dict[str, int] = {}
    for tool in spec.tools:
        name_counts[tool.tool_name] = name_counts.get(tool.tool_name, 0) + 1
    read_only = {
        tool.tool_name
        for tool in spec.tools
        if catalog_allows_read(discovered.get(tool.tool_id, {}))
        and not tool.requires_consent
        and tool.tool_id == f"{tool.mcp_id}:{tool.tool_name}"
        and name_counts[tool.tool_name] == 1
    }
    semaphore = asyncio.Semaphore(concurrency)
    started_at = time.monotonic()

    async def one(test: SpecTest) -> dict:
        async with semaphore:
            scenario_started_at = time.monotonic()
            try:
                transcript = await run_scenario(
                    spec=spec,
                    test=test,
                    model=model,
                    schemas=schemas,
                    run_tool=run_tool,
                    read_only=read_only,
                    simulated_tools=simulated_names,
                )
            except Exception as exc:  # noqa: BLE001 - a model failure is not a test result
                logger.exception("Agent test %s failed to run", test.id)
                error = _model_error(exc)
                return {
                    "test_id": test.id,
                    "scenario": test.scenario,
                    "expected": test.expected,
                    "latency_ms": round((time.monotonic() - scenario_started_at) * 1000),
                    "passed": False,
                    "error": error,
                    "checks": [],
                    "judge": {"passed": False, "reason": f"Không chạy được: {error}"},
                    "answer": "",
                    "tool_calls": [],
                    "model_evaluated": False,
                }
            checks = deterministic_checks(test, transcript)
            verdict = None
            error = None
            if judge_model is not None:
                try:
                    verdict = (await judge(judge_model, spec, test, transcript)).model_dump()
                except Exception as exc:  # noqa: BLE001
                    error = _model_error(exc)
                    verdict = {"passed": False, "reason": f"Không chấm được: {error}"}
            passed = all(c["passed"] for c in checks) and (verdict is None or verdict["passed"])
            return {
                **({"error": error} if error else {}),
                "test_id": test.id,
                "scenario": test.scenario,
                "expected": test.expected,
                "latency_ms": round((time.monotonic() - scenario_started_at) * 1000),
                "passed": passed,
                "checks": checks,
                "judge": verdict,
                "model_evaluated": judge_model is not None and error is None,
                **transcript,
            }

    results = await asyncio.gather(*(one(test) for test in spec.tests))
    passed = sum(item["passed"] for item in results)
    total = len(results)
    rate = round(passed / total, 3) if total else 0.0
    # A scenario the model could not play says nothing about the agent.
    errors = [item["error"] for item in results if item.get("error")]
    report = {
        "evaluator": "agent_spec_model_v1",
        "spec_hash": spec_hash(spec),
        "ran_at": datetime.now(UTC).isoformat(),
        "latency_ms": round((time.monotonic() - started_at) * 1000),
        "total": total,
        "passed": passed,
        "pass_rate": rate,
        "errors": len(errors),
        "model_error": errors[0] if errors else None,
        "results": results,
        "simulated_runtime_tools": sorted(simulated_names),
    }
    return seal_report(spec, report)


__all__ = [
    "MIN_TESTS_TO_PUBLISH",
    "PASS_THRESHOLD",
    "deterministic_checks",
    "run_scenario",
    "run_spec_tests",
    "tool_schemas",
]
