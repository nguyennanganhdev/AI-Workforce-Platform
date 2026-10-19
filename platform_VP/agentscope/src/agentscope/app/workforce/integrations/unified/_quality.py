"""Quality and cost of a manager's partner tickets, from what is stored.

Outcomes come from the workflow and its close reason, message quality from
the case log (CaseSay accepted / refused), and cost from owner-scoped,
per-provider-attempt evidence with immutable operator-supplied prices.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import os
from typing import Any

from sqlalchemy import select

from ...orchestration._tables import public_events, workflows
from ._tables import case_entries, case_sessions

async def ticket_quality(
    uows: Any,
    storage: Any,
    shared_storage: Any,
    manager_account_id: str,
    *,
    days: int = 30,
    success_reasons: tuple[str, ...] = ("resident_confirmed",),
) -> dict:
    since = datetime.now(UTC) - timedelta(days=days)
    async with uows() as uow:
        rows = (
            await uow.execute(
                select(workflows.c.id, workflows.c.state, workflows.c.created_at).where(
                    workflows.c.manager_account_id == manager_account_id,
                    workflows.c.created_at >= since,
                ),
            )
        ).all()
        ids = [row[0] for row in rows]
        closes = (
            await uow.execute(
                select(public_events.c.workflow_id, public_events.c.payload).where(
                    public_events.c.workflow_id.in_(ids),
                    public_events.c.event_type == "workflow.closed",
                ),
            )
        ).all() if ids else []
        entries = (
            await uow.execute(
                select(case_entries.c.workflow_id, case_entries.c.kind, case_entries.c.expects).where(
                    case_entries.c.workflow_id.in_(ids),
                    case_entries.c.kind.in_(("say", "rejected")),
                ),
            )
        ).all() if ids else []
        bindings = (
            await uow.execute(
                select(case_sessions.c.workflow_id, case_sessions.c.session_id).where(
                    case_sessions.c.workflow_id.in_(ids),
                ),
            )
        ).all() if ids else []
    states = {workflow_id: state for workflow_id, state, _created_at in rows}
    try:
        boundary = datetime.fromisoformat(os.environ["WORKFORCE_LEDGER_STARTED_AT"])
        if boundary.tzinfo is None:
            raise ValueError
    except (KeyError, ValueError):
        boundary = None
    covered = {wid for wid, _state, at in rows if boundary and
               (at.replace(tzinfo=UTC) if at.tzinfo is None else at) >= boundary}
    # The column stores the whole public event; its own payload has the reason.
    reason = {workflow_id: ((event or {}).get("payload") or {}).get("reason") for workflow_id, event in closes}
    confirmed = [w for w in ids if states[w] == "closed" and reason.get(w) in success_reasons]
    invitations: dict[str, int] = {}
    says = rejected = 0
    for workflow_id, kind, expects in entries:
        if kind == "say":
            says += 1
            if expects == "confirmation":
                invitations[workflow_id] = invitations.get(workflow_id, 0) + 1
        else:
            rejected += 1

    from ...._model_ledger import aggregate, costed, recording_failures
    calls = costed(await storage.list_model_calls(manager_account_id, since=since.isoformat(), limit=20001))
    truncated = len(calls) > 20000
    calls = calls[:20000]
    session_workflows = dict((sid, wid) for wid, sid in bindings)
    team_workflows = {}
    for wid, sid in bindings:
        session = await storage.get_session(manager_account_id, "", sid)
        if session and session.team_id:
            team_workflows[session.team_id] = wid
    grouped = {wid: [] for wid in ids}
    for call in calls:
        wid = call.get("workflow_id") or team_workflows.get(call.get("team_id")) or session_workflows.get(call.get("session_id"))
        if wid in grouped:
            grouped[wid].append(call)
    metrics = aggregate([call for values in grouped.values() for call in values])
    success_calls = [call for wid in confirmed for call in grouped[wid]]
    success_metrics = aggregate(success_calls)
    successful_complete = bool(confirmed) and all(wid in covered and grouped[wid] for wid in confirmed) and success_metrics["cost_complete"] and not truncated and not recording_failures()
    all_complete = bool(ids) and all(wid in covered and grouped[wid] for wid in ids) and not truncated and not recording_failures()
    # No historical backfill: tickets without per-call evidence remain unknown.
    tokens = {"input": metrics["input_tokens"], "cached": metrics["cached_input_tokens"], "output": metrics["output_tokens"]}
    return {
        "days": days,
        "tickets": len(ids),
        "open": sum(1 for w in ids if states[w] not in ("closed", "needs_attention")),
        "needs_attention": sum(1 for w in ids if states[w] == "needs_attention"),
        "closed_confirmed": len(confirmed),
        "closed_other": sum(1 for w in ids if states[w] == "closed" and w not in confirmed),
        # Confirmed after the first invitation: the user did not reject a result.
        "first_time_confirmed": sum(1 for w in confirmed if invitations.get(w, 0) == 1),
        "messages_sent": says,
        "messages_refused": rejected,
        "refusal_rate": round(rejected / (says + rejected), 3) if says + rejected else 0.0,
        "input_tokens": tokens["input"],
        "cached_input_tokens": tokens["cached"],
        "output_tokens": tokens["output"],
        "cache_rate": round(tokens["cached"] / tokens["input"], 3) if tokens["input"] else 0.0,
        "est_cost_usd": metrics["est_cost_usd"] if all_complete else None,
        "usage_complete": metrics["usage_complete"] and all_complete,
        "cost_complete": metrics["cost_complete"] and all_complete,
        "before_ledger_unknown": True,
        "successful_ticket_cost_usd": success_metrics["est_cost_usd"] if successful_complete else None,
        "cost_per_confirmed_usd": success_metrics["est_cost_usd"] / len(confirmed) if successful_complete else None,
    }
