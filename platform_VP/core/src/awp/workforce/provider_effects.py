"""What an event that may be applied does (spec 7.3): the operation, its public events, the templated message, the evidence
and the leader's wake-up. Everything shown comes from the schema's public fields, never from the raw `data`.

The wake-up is a queued `provider_wake` job, and the queue is kept short: news about an operation that is queued and not yet
read by the leader is merged into the job that waits (the leader gets one turn that lists what happened, newest last,
and is told the operation's state as it is when the turn starts), not one turn per event.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import insert, select, update

from . import tables as t
from .common import now, opaque_id
from .approvals import resolve
from .events import emit
from .messages import add_assistant_message
from .provider_schema import Rule, cost_note, evidence_text, public, quotes, render
from .settling import operations_at_rest
from .tables import new_id
from .workflows import bump, transition

EVENT_KEYS = ("event_type", "status", "operation_id", "external_job_id", "fields", "evidence_ref", "terminal", "done",
              "receipt_id", "note")
MAX_EARLIER = 4  # the earlier reports a merged wake still lists; the rest are only counted


async def apply_effects(conn, ctx, row: Any, rule: Rule, op: Any, wf: dict) -> tuple | None:
    """Returns (workflow id, job id) when a wake-up job was queued or grew, for the engine to be told after the commit."""
    ev = row["payload"]
    given = ev.get("external_job_id")
    job = op["external_job_id"] or (given if opaque_id(given) else None)
    version = ev.get("provider_version")
    status = rule.op_status
    await conn.execute(update(t.operations).where(t.operations.c.id == op["id"]).values(
        status=status, normalized_status=rule.status, last_rank=rule.rank, external_job_id=job, updated_at=now(),
        provider_version=str(version) if version is not None else op["provider_version"]))
    wf = await bump(conn, wf)
    fields = public(rule, ev.get("data") or {})
    # `status` is the integration's own word (contract 9.7); `operation_state` is the platform's five-valued one
    changed = {"operation_id": op["id"], "status": rule.status, "operation_state": status, "tool": op["tool_name"],
               "client_reference": op["client_reference"], **({"external_job_id": job} if job else {})}
    await emit(conn, wf["conversation_id"], "operation.status_changed", changed, workflow=wf)
    if rule.public_status and wf["ticket_id"]:
        await emit(conn, wf["conversation_id"], "ticket.status_changed",
                   {"ticket_id": wf["ticket_id"], "status": rule.public_status, "details": fields}, workflow=wf)
    wf, resumed = await withdraw_consents(conn, wf, op["id"]) if rule.terminal or quotes(fields) else (wf, None)
    text = render(rule, ev.get("data") or {})
    if text:  # no model: the words are the schema's, the values the provider's allowed fields
        await add_assistant_message(conn, wf, text, None, source="provider")
    ref = None
    if rule.keeps_evidence:
        item = await ctx.rt.cases.add(wf["case_id"], "evidence", "provider", {
            "tool": f"provider:{rule.event_type}", "input": rule.event_type, "text": evidence_text(rule, fields),
            "job": row["receipt_id"], "op": op["id"]}, conn=conn)
        ref = item.ref
    event = {"event_type": rule.event_type, "status": rule.status, "operation_id": op["id"], "external_job_id": job,
             "fields": fields, "evidence_ref": ref, "terminal": rule.terminal, "done": rule.done,
             "receipt_id": row["receipt_id"], "note": cost_note(fields)}
    if rule.wake:
        return await queue_wake(conn, wf["id"], event)
    if rule.terminal and wf["state"] == "waiting_external_event":  # nobody was woken: see where the work stands
        how = await at_rest(conn, wf)
        if how == "mixed":  # some was done and some was not: the resident must hear it from the leader
            return await queue_wake(conn, wf["id"], event)
        if how == "confirm":
            await transition(conn, wf, "awaiting_confirmation", reason="operation_completed")
        elif how == "failed":
            await transition(conn, wf, "needs_attention", reason="operation_failed")
    elif rule.reopen and not rule.terminal and wf["state"] == "awaiting_confirmation":
        await transition(conn, wf, "waiting_external_event", reason="operation_reopened")  # there is work to wait for again
    return resumed


async def withdraw_consents(conn, wf: dict, op_id: str) -> tuple[dict, tuple | None]:
    """The work ended or was quoted again: the resident must not agree to a price for what no longer stands. Every pending
    consent that prices this operation is withdrawn (`cancelled`, with its public event), the agent parked on it is let go
    and the leader is told, through the same jobs an expired approval uses (resume.py)."""
    rows = (await conn.execute(select(t.approvals).where(
        t.approvals.c.workflow_id == wf["id"], t.approvals.c.operation_id == op_id,
        t.approvals.c.status == "pending").order_by(t.approvals.c.created_at))).mappings().all()
    job = None
    for row in rows:
        wf, job = await resolve(conn, wf, row, "cancelled", request_id=None, reason="approval_withdrawn")
    return wf, (wf["id"], job) if job else None


async def at_rest(conn, wf: dict) -> str | None:
    """Where the tracked work stands once the last operation is over: None while something still moves or cannot be found
    out about, `confirm` when what was done is the resident's to confirm, `failed` when nothing was, and `mixed` when some
    of it was done and some was not (that is not a thing to confirm: the resident has to be told which)."""
    rows = (await conn.execute(select(t.operations.c.status, t.operations.c.tool_name, t.operations.c.result).where(
        t.operations.c.workflow_id == wf["id"]))).all()
    tracking = dict((await conn.execute(select(t.tools.c.name, t.tools.c.tracking).where(
        t.tools.c.route_id == wf["route_id"]))).all())
    moving, lost = operations_at_rest(rows, tracking)
    if moving or lost:
        return None
    done = any(s == "completed" for s, _, _ in rows)
    if done and any(s == "failed" for s, _, _ in rows):
        return "mixed"
    return "confirm" if done else "failed"


async def queue_wake(conn, workflow_id: str, event: dict) -> tuple[str, str]:
    """A wake-up job for `event`, or the queued one of the same operation grown by it. The caller holds the conversation's
    lock, as the engine does when it takes a job, so a job is either still queued here or already taken."""
    queued = (await conn.execute(select(t.jobs.c.id, t.jobs.c.payload).where(
        t.jobs.c.workflow_id == workflow_id, t.jobs.c.kind == "provider_wake", t.jobs.c.status == "queued")
        .order_by(t.jobs.c.created_at, t.jobs.c.id))).all()
    same = next((j for j in reversed(queued) if "event_type" in j[1] and j[1].get("operation_id") == event["operation_id"]), None)
    if same is not None:
        old = same[1]
        earlier = [*(old.get("earlier") or []), {k: old[k] for k in EVENT_KEYS if k in old}]
        await conn.execute(update(t.jobs).where(t.jobs.c.id == same[0], t.jobs.c.status == "queued").values(
            payload={**event, "earlier": earlier[-MAX_EARLIER:],
                     "omitted": old.get("omitted", 0) + max(0, len(earlier) - MAX_EARLIER)}))
        return workflow_id, same[0]
    job_id = new_id("job")
    await conn.execute(insert(t.jobs).values(id=job_id, workflow_id=workflow_id, kind="provider_wake", request_id=None,
                                             status="queued", attempts=0, created_at=now(), payload=event))
    return workflow_id, job_id
