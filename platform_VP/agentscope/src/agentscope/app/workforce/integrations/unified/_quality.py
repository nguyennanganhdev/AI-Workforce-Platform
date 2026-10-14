"""Quality and cost of a manager's partner tickets, from what is stored.

Outcomes come from the workflow and its close reason, message quality from
the case log (CaseSay accepted / refused), and cost from the provider usage
the ticket's room recorded per agent (with cached input).
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from ...orchestration._tables import public_events, workflows
from ._tables import case_entries, case_sessions

# USD per 1M tokens (input, cached input, output), OpenAI Standard tier,
# https://developers.openai.com/api/docs/pricing as read on 15/10/2026.
# Override with WORKFORCE_MODEL_PRICES='{"model": [in, cached, out]}'.
DEFAULT_PRICES = {
    "gpt-5.5": (5.00, 0.50, 30.00),
    "gpt-5.4-mini": (0.75, 0.075, 4.50),
}


def _prices() -> dict[str, tuple[float, float, float]]:
    prices = dict(DEFAULT_PRICES)
    raw = os.getenv("WORKFORCE_MODEL_PRICES", "").strip()
    if raw:
        prices.update({name: tuple(map(float, value)) for name, value in json.loads(raw).items()})
    return prices


def _cost(model: str, input_tokens: int, cached: int, output_tokens: int, prices: dict) -> float | None:
    price = prices.get(model)
    if price is None:
        return None
    return ((input_tokens - cached) * price[0] + cached * price[1] + output_tokens * price[2]) / 1_000_000


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
                select(workflows.c.id, workflows.c.state).where(
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
    states = {workflow_id: state for workflow_id, state in rows}
    # The column stores the whole public event; its own payload has the reason.
    reason = {workflow_id: ((event or {}).get("payload") or {}).get("reason") for workflow_id, event in closes}
    confirmed = [w for w in ids if reason.get(w) in success_reasons]
    invitations: dict[str, int] = {}
    says = rejected = 0
    for workflow_id, kind, expects in entries:
        if kind == "say":
            says += 1
            if expects == "confirmation":
                invitations[workflow_id] = invitations.get(workflow_id, 0) + 1
        else:
            rejected += 1

    prices = _prices()
    tokens = {"input": 0, "cached": 0, "output": 0}
    cost, priced = 0.0, True
    for _workflow_id, session_id in bindings:
        session = await storage.get_session(manager_account_id, "", session_id)
        team_id = getattr(session, "team_id", None)
        record = await shared_storage.get_team_shared_context(manager_account_id, team_id) if team_id else None
        if record is None:
            continue
        for usage in record.state.metrics.provider_usage.values():
            tokens["input"] += usage.input_tokens
            tokens["cached"] += usage.cached_input_tokens
            tokens["output"] += usage.output_tokens
            value = _cost(usage.model, usage.input_tokens, usage.cached_input_tokens, usage.output_tokens, prices)
            if value is None:
                priced = False
            else:
                cost += value
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
        "est_cost_usd": round(cost, 4) if priced else None,
        "cost_per_confirmed_usd": round(cost / len(confirmed), 4) if priced and confirmed else None,
    }
