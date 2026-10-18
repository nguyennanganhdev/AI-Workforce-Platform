"""Read-only measurements of one Workforce ticket.

The numbers come from the ticket's durable Shared Context record: provider
usage (including prompt-cache hits), collaboration branch counters and the
event history. They let an operator, the evaluation script and the agent
management page answer "how much did this case cost and how did the agents
work together" without reading raw transcripts.
"""

from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..deps import get_current_user_id, get_shared_context_storage, get_storage
from ..storage import StorageBase
from ..storage._utils import _ensure_team_members, _resolve_team_leader

workforce_insights_router = APIRouter(
    prefix="/workforce/console",
    tags=["workforce-console"],
)


class UsageView(BaseModel):
    """Provider usage of one agent (or the ticket total)."""

    agent_id: str = ""
    agent_name: str = ""
    model: str = ""
    calls: int = 0
    calls_with_usage: int = 0
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    cache_hit_ratio: float = 0.0


class BranchView(BaseModel):
    """Collaboration counters of one agent session in the active task."""

    session_id: str
    agent_name: str = ""
    status: str
    reason: str = ""
    exchanges: int = 0
    model_calls: int = 0
    measured_tokens: int = 0
    active_seconds: float = 0.0
    verifications: int = 0
    evidence_rejections: int = 0


class TicketMetricsView(BaseModel):
    """Everything measured for one ticket (Leader session)."""

    session_id: str
    team_id: str | None = None
    task_id: str | None = None
    total: UsageView = Field(default_factory=UsageView)
    by_agent: list[UsageView] = Field(default_factory=list)
    branches: list[BranchView] = Field(default_factory=list)
    event_counts: dict[str, int] = Field(default_factory=dict)
    context: dict[str, int | str] = Field(default_factory=dict)
    assignments: list[dict] = Field(default_factory=list)


def _ratio(cached: int, total: int) -> float:
    return round(cached / total, 4) if total else 0.0


@workforce_insights_router.get(
    "/tickets/{session_id}/metrics",
    response_model=TicketMetricsView,
)
async def ticket_metrics(
    session_id: str,
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
    shared_storage: StorageBase = Depends(get_shared_context_storage),
) -> TicketMetricsView:
    """Return token, cache and collaboration measurements of a ticket."""

    session = await storage.get_session(user_id, "", session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    view = TicketMetricsView(session_id=session_id, team_id=session.team_id)
    if session.team_id is None:
        return view
    record = await shared_storage.get_team_shared_context(user_id, session.team_id)
    if record is None:
        return view

    names: dict[str, str] = {}
    team = await storage.get_team(user_id, session.team_id)
    if team is not None:
        leader = await _resolve_team_leader(storage, user_id, team)
        if leader is not None:
            names[leader.session_id] = leader.name
        for member in await _ensure_team_members(storage, user_id, team):
            agent = await storage.get_agent(member.owner_id, member.agent_id)
            if agent is not None:
                names[member.session_id] = agent.data.name

    state = record.state
    view.task_id = state.active_task_id
    total = UsageView(agent_name="(tổng)")
    for agent_id, usage in state.metrics.provider_usage.items():
        item = UsageView(
            agent_id=agent_id,
            agent_name=usage.agent_name,
            model=usage.model,
            calls=usage.calls,
            calls_with_usage=usage.calls_with_usage,
            input_tokens=usage.input_tokens,
            cached_input_tokens=usage.cached_input_tokens,
            output_tokens=usage.output_tokens,
            cache_hit_ratio=_ratio(usage.cached_input_tokens, usage.input_tokens),
        )
        view.by_agent.append(item)
        total.calls += item.calls
        total.calls_with_usage += item.calls_with_usage
        total.input_tokens += item.input_tokens
        total.cached_input_tokens += item.cached_input_tokens
        total.output_tokens += item.output_tokens
    total.cache_hit_ratio = _ratio(total.cached_input_tokens, total.input_tokens)
    view.total = total

    task = state.tasks.get(state.active_task_id) if state.active_task_id else None
    if task is not None:
        for sid, branch in task.collaboration.items():
            view.branches.append(
                BranchView(
                    session_id=sid,
                    agent_name=names.get(sid, ""),
                    status=branch.status,
                    reason=branch.reason,
                    exchanges=branch.exchanges,
                    model_calls=branch.model_calls,
                    measured_tokens=branch.measured_tokens,
                    active_seconds=round(branch.active_seconds, 2),
                    verifications=branch.verifications,
                    # The core keeps no per-branch evidence rejections.
                    evidence_rejections=getattr(branch, "evidence_rejections", 0),
                ),
            )
        view.assignments = [
            {**assignment.model_dump(mode="json"), "agent_name": names.get(sid, "")}
            for sid, assignment in getattr(task, "assignments", {}).items()
        ]
    view.event_counts = dict(Counter(event.kind for event in state.events))
    metrics = state.metrics
    view.context = {
        "packets_built": metrics.packets_built,
        "compactions": metrics.compactions,
        "compaction_failures": metrics.compaction_failures,
        "peak_packet_tokens": metrics.peak_packet_tokens,
        "peak_total_prompt_tokens": metrics.peak_total_prompt_tokens,
        "total_measured_prompt_tokens": metrics.total_measured_prompt_tokens,
        "model_calls_measured": metrics.model_calls_measured,
        "summary_model_calls": metrics.summary_model_calls,
        "prompt_budget_failures": metrics.prompt_budget_failures,
        "packet_budget_failures": metrics.packet_budget_failures,
        "token_counter": metrics.last_token_counter,
    }
    return view


__all__ = ["workforce_insights_router"]
