# -*- coding: utf-8 -*-
"""Test cases saved from real conversations, re-run against an agent.

A case keeps the customer's message, the behaviour the user expects and the
real results of the agent's read lookups in that turn, so a re-run replays
the same data instead of generated fixtures. Each run records the agent's
configuration hash, so two runs can be compared as two versions.
"""
import asyncio
import hashlib
import json
import time
from collections import defaultdict, deque
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from ..._logging import logger
from ...message import Msg, ToolCallBlock, ToolResultBlock
from ...model import ChatModelBase
from ..storage import AgentArtifactRecord, AgentRecord, StorageBase
from ._builder_eval import EvalAgent, EvalCase, report, score_case
from ._case_file import _INTERNAL_TOOLS, customer_text, turn_messages

MAX_CASES_PER_RUN = 20
RUNS_PER_DAY = 10
_RECORDED_CHARS = 8000
_DAY = 24 * 3600

# In-process limits, like the Builder eval: one running suite per user.
_running: dict[str, asyncio.Task] = {}
_starts: dict[str, deque] = defaultdict(deque)


class EvalCaseData(BaseModel):
    """A saved test case (``AgentArtifactRecord.data`` of kind ``eval_case``)."""

    scenario: str = Field(min_length=1, max_length=2000)
    expected: str = Field(min_length=1, max_length=2000)
    expect_tool: str = Field(default="", max_length=200)
    # Real results of read tools, by bare tool name, in call order.
    recorded: dict[str, list[str]] = Field(default_factory=dict)
    source_session_id: str | None = None
    source_message_id: str | None = None


class EvalRunData(BaseModel):
    """One run of an agent's suite (``data`` of kind ``eval_run``)."""

    version: str
    model: str
    status: Literal["running", "completed", "failed"] = "running"
    started_at: str
    finished_at: str | None = None
    tests: list[dict] = Field(default_factory=list)
    report: dict | None = None
    error: str | None = None


def _bare(tool_name: str) -> str:
    """``mcp__Server__search_x`` is offered to the agent as ``search_x``."""
    return tool_name.rsplit("__", 1)[-1] if tool_name.startswith("mcp__") else tool_name


def eval_agent(record: AgentRecord) -> EvalAgent:
    """What the eval runner needs of a published agent."""
    return EvalAgent(
        name=record.data.name,
        objective=record.data.build_description or "",
        system_prompt=record.data.system_prompt,
        skill_markdown=record.data.generated_skill or "",
        tools=[binding.model_dump() if hasattr(binding, "model_dump") else dict(binding)
               for binding in record.data.tool_bindings],
    )


def agent_version(record: AgentRecord, model_name: str) -> str:
    """A short hash of everything that changes an agent's behaviour."""
    agent = eval_agent(record)
    payload = json.dumps(
        {
            "prompt": agent.system_prompt,
            "skill": agent.skill_markdown,
            "tools": sorted(tool.get("id", tool.get("tool_name", "")) for tool in agent.tools),
            "knowledge": sorted(record.data.knowledge_base_ids),
            "model": model_name,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def case_from_turn(
    messages: list[Msg],
    message_id: str,
    agent_id: str,
    leader_agent_id: str,
) -> tuple[str, dict[str, list[str]]] | None:
    """The turn's customer message and the agent's real read results.

    ``agent_id`` is the agent the case will test; replies without
    ``team_agent_id`` belong to ``leader_agent_id``.
    """
    turn = turn_messages(messages, message_id)
    if not turn or turn[0].role != "user":
        return None
    recorded: dict[str, list[str]] = {}
    for message in turn:
        author = str(message.metadata.get("team_agent_id") or leader_agent_id)
        if message.role != "assistant" or author != agent_id:
            continue
        blocks = message.get_content_blocks()
        results = {b.id: b for b in blocks if isinstance(b, ToolResultBlock)}
        for call in blocks:
            if not isinstance(call, ToolCallBlock) or call.name in _INTERNAL_TOOLS:
                continue
            result = results.get(call.id)
            if result is None or str(result.state) != "success":
                continue
            output = result.output if isinstance(result.output, str) else "\n".join(
                getattr(block, "text", "") for block in result.output if getattr(block, "text", "")
            )
            recorded.setdefault(_bare(call.name), []).append(output[:_RECORDED_CHARS])
    return customer_text(turn[0]), recorded


class EvalLimitError(Exception):
    """A suite cannot start now; the message says why."""


def reserve_run(user_id: str) -> None:
    """Admit one suite run for ``user_id`` or raise :class:`EvalLimitError`."""
    task = _running.get(user_id)
    if task is not None and not task.done():
        raise EvalLimitError("Một lượt chạy ca kiểm thử khác đang chạy. Hãy chờ lượt đó xong.")
    starts = _starts[user_id]
    now = time.monotonic()
    while starts and now - starts[0] > _DAY:
        starts.popleft()
    if len(starts) >= RUNS_PER_DAY:
        raise EvalLimitError(f"Đã chạy đủ {RUNS_PER_DAY} lượt trong 24 giờ. Hãy thử lại sau.")
    starts.append(now)


def _now() -> str:
    return datetime.now(UTC).isoformat()


async def run_suite(
    storage: StorageBase,
    user_id: str,
    agent: AgentRecord,
    model: ChatModelBase,
    run: AgentArtifactRecord,
    cases: list[AgentArtifactRecord],
    concurrency: int = 2,
) -> None:
    """Score every case, saving the run after each one finishes."""
    data = EvalRunData.model_validate(run.data)
    lock = asyncio.Lock()

    async def save() -> None:
        async with lock:
            run.data = data.model_dump()
            await storage.upsert_agent_artifact(user_id, run)

    subject = eval_agent(agent)
    gate = asyncio.Semaphore(concurrency)

    async def one(index: int, case: AgentArtifactRecord) -> None:
        saved = EvalCaseData.model_validate(case.data)
        item = data.tests[index]
        async with gate:

            async def on_stage(name: str) -> None:
                item["status"] = name

            outcome = await score_case(
                model,
                subject,
                EvalCase(
                    id=case.id,
                    scenario=saved.scenario,
                    expected=saved.expected,
                    expect_tool=saved.expect_tool,
                ),
                recorded=saved.recorded,
                on_stage=on_stage,
            )
            item.update(outcome)
            await save()

    try:
        await asyncio.gather(*(one(index, case) for index, case in enumerate(cases)))
        data.report = report(data.tests)
        data.status = "completed"
    except Exception:  # noqa: BLE001 - the run must end in a final state
        logger.exception("Eval suite failed for agent %s", agent.id)
        data.status = "failed"
        data.error = "Không chạy xong bộ ca kiểm thử."
    data.finished_at = _now()
    await save()


async def start_suite(
    storage: StorageBase,
    user_id: str,
    agent: AgentRecord,
    model: ChatModelBase,
    model_name: str,
    cases: list[AgentArtifactRecord],
) -> AgentArtifactRecord:
    """Save the run record, then score it in the background (after
    :func:`reserve_run`)."""
    run = AgentArtifactRecord(
        user_id=user_id,
        agent_id=agent.id,
        kind="eval_run",
        data=EvalRunData(
            version=agent_version(agent, model_name),
            model=model_name,
            started_at=_now(),
            tests=[
                {
                    "case_id": case.id,
                    "scenario": case.data["scenario"],
                    "expected": case.data["expected"],
                    "status": "pending",
                }
                for case in cases
            ],
        ).model_dump(),
    )
    await storage.upsert_agent_artifact(user_id, run)
    _running[user_id] = asyncio.create_task(
        run_suite(storage, user_id, agent, model, run, cases),
    )
    return run


def compare_runs(older: dict[str, Any], newer: dict[str, Any]) -> list[dict]:
    """Per case: status in each run, and whether it got better or worse."""
    before = {test["case_id"]: test.get("status") for test in older.get("tests", [])}
    rows = []
    for test in newer.get("tests", []):
        old = before.get(test["case_id"])
        new = test.get("status")
        change = "same"
        if old == "passed" and new != "passed":
            change = "worse"
        elif old != "passed" and new == "passed" and old is not None:
            change = "better"
        elif old is None:
            change = "new"
        rows.append({"case_id": test["case_id"], "scenario": test["scenario"],
                     "before": old, "after": new, "change": change})
    return rows
