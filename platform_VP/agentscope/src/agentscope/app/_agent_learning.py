"""Learning after a well-handled ticket: memory and self-improving prompts.

Runs in the background after the Leader answers a ticket whose assignments
were all verified or accepted. For every business agent that worked on it:

1. a model extracts at most three generalizable memories, each citing the
   ticket events it is based on; ids that do not exist are dropped, so an
   unsupported "memory" cannot be stored (provenance gate);
2. the memories are consolidated (add / update-supersedes / no-op) and are
   approved by the agent itself (no manual review, per the product owner);
3. if the agent allows self-improvement, at most one new rule is proposed.
   It is published as a new version (author "agent") only when the agent has
   tests and they still pass at least as well as the published version;
   otherwise it waits as a draft for the manager. Rules written by a person
   or locked are never changed, at most one self-update per agent per day,
   and every change can be rolled back from the version history.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, Field

from .._logging import logger
from ..message import UserMsg
from ..model import ChatModelBase
from ..model._call_observer import usage_purpose
from ._agent_memory import AgentMemoryService, MemoryCandidate, fold_tokens
from ._agent_spec import AgentSpec, SpecOperation, apply_operations
from ._service._agent_eval import MIN_TESTS_TO_PUBLISH, run_spec_tests
from ._service._agent_studio import (
    apply_bindings,
    ensure_spec,
    materialize,
    set_draft,
    tool_catalog,
    tool_runner,
)
from .storage import StorageBase

ModelFactory = Callable[[], Awaitable[tuple[ChatModelBase, ChatModelBase]]]
"""Returns ``(working_model, strong_model)`` for the ticket owner."""

SELF_UPDATE_COOLDOWN = timedelta(hours=24)
_SUCCESS = {"verified", "accepted"}
# Events whose content the platform verified: tool results and the customer.
_BLOCKING = {"queued", "assigned", "challenged", "stopped", "failed"}


class _LearnedMemory(BaseModel):
    kind: Literal["lesson", "fact", "preference"] = "lesson"
    content: str = Field(min_length=1, max_length=600)
    evidence_event_ids: list[str] = Field(default_factory=list, max_length=10)


class _LearnedRule(BaseModel):
    text: str = Field(min_length=1, max_length=400)
    reason: str = Field(default="", max_length=400)
    evidence_event_ids: list[str] = Field(default_factory=list, max_length=10)


class _Learning(BaseModel):
    memories: list[_LearnedMemory] = Field(default_factory=list, max_length=3)
    rule: _LearnedRule | None = None


_EXTRACT_PROMPT = """Bạn rút kinh nghiệm cho một AI agent sau một ticket đã được xác minh là xử lý tốt.

Trả về:
- memories: tối đa 3 điều đáng nhớ để lần sau làm tốt hơn. Mỗi điều phải tổng quát
  (áp dụng cho ticket khác), ngắn gọn, và có evidence_event_ids là id sự kiện
  trong ticket làm căn cứ. "fact" chỉ được lấy từ kết quả tool. Không ghi tên,
  số điện thoại, số căn hộ hay thông tin cá nhân của khách. Không lặp lại luật đã có.
- rule: nhiều nhất 1 luật mới giúp agent làm tốt hơn các ticket tương tự (ví dụ
  một bước kiểm tra nên làm trước). Chỉ đề xuất khi thật sự rút ra từ ticket;
  không trùng hoặc mâu thuẫn với luật đã có. Để null nếu không có.
Viết bằng ngôn ngữ của luật hiện có (thường là tiếng Việt). Trả mảng rỗng nếu không có gì mới."""


def _ticket_digest(state: Any, task: Any, agent_id: str, session_id: str) -> tuple[str, set[str]]:
    """Compact, id-annotated view of the ticket for one agent."""

    events = [e for e in state.events if e.task_id == task.id and not e.stale]
    ids = {event.id for event in events}
    lines: list[str] = []
    for event in [e for e in events if e.kind in {"customer_message", "customer_reply"}][-3:]:
        who = "KHÁCH" if event.kind == "customer_message" else "TRẢ LỜI KHÁCH"
        lines.append(f"[{event.id}] {who}: {event.content[:800]}")
    assignment = task.assignments.get(session_id)
    if assignment is not None:
        lines.append(f"NHIỆM VỤ: {assignment.goal[:800]}")
        if assignment.done_when:
            lines.append(f"TIÊU CHÍ: {assignment.done_when[:400]}")
        if assignment.challenges:
            lines.append(f"BỊ PHẢN BIỆN {assignment.challenges} lần: {assignment.last_feedback[:400]}")
    for event in [e for e in events if e.kind == "external_event" and e.source_session_id == session_id][-3:]:
        lines.append(f"[{event.id}] KẾT QUẢ TOOL: {event.content[:1200]}")
    for event in [
        e
        for e in events
        if e.kind in {"result", "answer"} and (e.source_agent_id == agent_id or e.source_session_id == session_id)
    ][-2:]:
        lines.append(f"[{event.id}] AGENT BÁO CÁO: {event.content[:1200]}")
    return "\n".join(lines), ids


def ticket_succeeded(task: Any) -> bool:
    """Every assignment ended verified/accepted and the runtime stopped nothing."""

    statuses = [assignment.status for assignment in task.assignments.values()]
    if not statuses or any(status in _BLOCKING for status in statuses):
        return False
    if not any(status in _SUCCESS for status in statuses):
        return False
    rejections = sum(branch.evidence_rejections for branch in task.collaboration.values())
    return rejections <= 1


class AgentLearningService:
    """Background learning triggered by a successful Leader answer."""

    def __init__(
        self,
        storage: StorageBase,
        shared_context: Any,
        workspace_manager: Any,
    ) -> None:
        self._storage = storage
        self._shared_context = shared_context
        self._shared_storage = shared_context.storage
        self._workspace_manager = workspace_manager
        self._memory = AgentMemoryService(shared_context.storage)
        self._running: set[tuple[str, str]] = set()
        self._tasks: set[asyncio.Task] = set()

    @property
    def memory(self) -> AgentMemoryService:
        return self._memory

    def schedule(self, user_id: str, team_id: str, models: ModelFactory) -> None:
        key = (user_id, team_id)
        if key in self._running:
            return
        self._running.add(key)

        async def runner() -> None:
            try:
                await self.learn(user_id, team_id, models)
            except Exception:  # noqa: BLE001 - background isolation
                logger.exception("Agent learning failed for team %s", team_id)
            finally:
                self._running.discard(key)

        task = asyncio.create_task(runner(), name=f"agent-learning-{team_id}")
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    @usage_purpose("learning")
    async def learn(self, user_id: str, team_id: str, models: ModelFactory) -> dict:
        record = await self._shared_storage.get_team_shared_context(user_id, team_id)
        task = (
            record.state.tasks.get(record.state.active_task_id)
            if record and record.state.active_task_id
            else None
        )
        if task is None or not ticket_succeeded(task):
            return {"learned": False, "reason": "ticket not verified as successful"}
        latest = max((e.revision for e in record.state.events if e.task_id == task.id), default=0)
        if task.learned_revision >= latest:
            return {"learned": False, "reason": "already learned"}
        working_model, strong_model = await models()
        for selected in (working_model, strong_model):
            underlying = getattr(selected, "_model", selected)
            underlying._usage_attributes = {"user_id": user_id, "team_id": team_id, "purpose": "learning"}
        outcome: dict[str, Any] = {"learned": True, "agents": {}}
        for session_id, assignment in task.assignments.items():
            if not assignment.agent_id:
                continue
            agent = await self._storage.get_agent(user_id, assignment.agent_id)
            if agent is None or agent.data.system_role != "business":
                continue
            ensure_spec(agent)
            spec = AgentSpec.model_validate(agent.data.spec)
            if not (spec.memory_enabled or spec.self_improve):
                continue
            for selected in (working_model, strong_model):
                underlying = getattr(selected, "_model", selected)
                underlying._usage_attributes.update(agent_id=agent.id, session_id=session_id)
            if hasattr(self._storage, "get_session"):
                session = await self._storage.get_session(user_id, agent.id, session_id)
                if session and session.state.middle_context.get("workflow_id"):
                    for selected in (working_model, strong_model):
                        getattr(selected, "_model", selected)._usage_attributes["workflow_id"] = session.state.middle_context["workflow_id"]
            digest, event_ids = _ticket_digest(record.state, task, agent.id, session_id)
            try:
                response = await strong_model.generate_structured_output(
                    messages=[
                        UserMsg(
                            name="learning",
                            content=(
                                _EXTRACT_PROMPT
                                + "\n\nLUẬT HIỆN CÓ:\n"
                                + "\n".join(f"- {rule.text}" for rule in spec.rules)
                                + "\n\nTICKET:\n"
                                + digest
                            ),
                        ),
                    ],
                    structured_model=_Learning,
                )
                learning = _Learning.model_validate(response.content)
            except Exception:  # noqa: BLE001
                logger.exception("Learning extraction failed for agent %s", agent.id)
                continue
            result: dict[str, Any] = {}
            if spec.memory_enabled:
                candidates = [
                    MemoryCandidate(
                        kind=item.kind,
                        content=item.content,
                        evidence_event_ids=item.evidence_event_ids,
                    )
                    for item in learning.memories
                ]
                # Provenance gate: an item without a real source is dropped,
                # and a fact must rest on a tool result or the customer's own
                # words, never on an agent's report (a wrong fact is copied
                # into later tickets).
                result["memories"] = await self._memory.consolidate(
                    user_id,
                    agent.id,
                    candidates,
                    ticket_id=team_id,
                    model=strong_model,
                )
            if spec.self_improve and learning.rule is not None:
                rule_evidence = await self._memory._evidence(user_id, agent.id, team_id,
                    MemoryCandidate(kind="lesson", content=learning.rule.text,
                                    evidence_event_ids=learning.rule.evidence_event_ids), strong_model)
                if not rule_evidence:
                    result["rule"] = {"applied": False, "reason": "rule evidence not verified"}
                    outcome["agents"][agent.id] = result
                    continue
                result["rule"] = await self._self_improve(
                    user_id,
                    agent.id,
                    learning.rule,
                    team_id,
                    working_model,
                    strong_model,
                )
            outcome["agents"][agent.id] = result
        await self._shared_context.mark_learned(user_id, team_id, task.id, latest)
        return outcome

    async def _self_improve(
        self,
        user_id: str,
        agent_id: str,
        rule: _LearnedRule,
        team_id: str,
        working_model: ChatModelBase,
        strong_model: ChatModelBase,
    ) -> dict:
        agent = await self._storage.get_agent(user_id, agent_id)
        if agent is None:
            return {"applied": False, "reason": "agent missing"}
        spec = AgentSpec.model_validate(agent.data.spec)
        folded = " ".join(fold_tokens(rule.text))
        if any(folded and folded in " ".join(fold_tokens(r.text)) for r in spec.rules):
            return {"applied": False, "reason": "duplicate rule"}
        now = datetime.now(UTC)
        recent = [
            v
            for v in agent.data.versions
            if v.get("author") == "agent"
            and v.get("created_at")
            and now - datetime.fromisoformat(v["created_at"]) < SELF_UPDATE_COOLDOWN
        ]
        if recent:
            return {"applied": False, "reason": "cooldown"}
        if agent.data.draft_spec is not None and agent.data.draft_meta.get("author") != "agent":
            return {"applied": False, "reason": "manager draft in progress"}
        candidate = apply_operations(
            spec,
            [
                SpecOperation(
                    op="add",
                    field="rules",
                    value={
                        "text": rule.text,
                        "level": "should",
                        "source": "agent",
                        "learned_from": f"ticket {team_id[:8]}",
                    },
                ),
            ],
            author="agent",
        )
        note = f"Tự cải tiến sau ticket {team_id[:8]}: {rule.reason or rule.text}"[:1000]
        if len(candidate.tests) < MIN_TESTS_TO_PUBLISH:
            set_draft(agent, candidate, author="agent", note=note + " (cần kiểm thử)")
            await self._storage.upsert_agent(user_id, agent)
            return {"applied": False, "reason": "drafted: not enough tests to auto-publish"}
        report = await run_spec_tests(
            spec=candidate,
            model=working_model,
            judge_model=strong_model,
            discovered=await tool_catalog(self._storage, user_id),
            run_tool=tool_runner(self._storage, user_id, candidate),
        )
        baseline = float((agent.data.evaluation or {}).get("pass_rate") or (agent.data.evaluation or {}).get("score") or 0.0)
        if not report["publishable"] or report["pass_rate"] < baseline:
            return {
                "applied": False,
                "reason": f"tests {report['passed']}/{report['total']} below the published version",
            }
        # Re-read right before writing so a concurrent manager edit wins.
        agent = await self._storage.get_agent(user_id, agent_id)
        if agent is None or (agent.data.draft_spec is not None and agent.data.draft_meta.get("author") != "agent"):
            return {"applied": False, "reason": "manager edited meanwhile"}
        version = materialize(agent, candidate, author="agent", note=note, evaluation=report)
        from .storage._base import AgentRevisionConflict
        try:
            await self._storage.upsert_agent(user_id, agent)
        except AgentRevisionConflict:
            return {"applied": False, "reason": "agent changed while publishing"}
        await apply_bindings(self._storage, self._workspace_manager, user_id, agent, candidate)
        return {"applied": True, "version": version}


__all__ = ["AgentLearningService", "ticket_succeeded"]
