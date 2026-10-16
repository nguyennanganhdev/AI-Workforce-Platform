"""Workflow states, the `next_action` projection and the one function that changes a state.

Whoever changes a workflow (the command service, the engine, close) goes through
`transition`, so state, revision, the public event and the legality check cannot drift apart.
"""
from __future__ import annotations

from typing import Any, Iterable

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from . import tables as t
from .common import iso, now
from .events import emit

STATES = ("accepted", "active", "waiting_external_event", "awaiting_user", "awaiting_approval",
          "awaiting_confirmation", "needs_attention", "blocked_authorization", "blocked_route_changed",
          "closed")
# A turn may still be running in these two; every other state is a place to rest.
BUSY = ("accepted", "active")
BLOCKED = ("blocked_authorization", "blocked_route_changed")

NEXT_ACTION = {
    "closed": "none", "awaiting_user": "submit_reply", "awaiting_approval": "submit_approval",
    "awaiting_confirmation": "confirm_close", "waiting_external_event": "watch_events",
    "needs_attention": "resolve_attention", "blocked_authorization": "resolve_attention",
    "blocked_route_changed": "resolve_attention", "accepted": "watch_request", "active": "watch_request"}
EXPECTS = {"awaiting_user": "reply", "awaiting_confirmation": "confirmation"}


class IllegalTransition(Exception):
    """A change the state machine forbids (anything out of `closed`, or back to `accepted`)."""


class StateConflict(Exception):
    """The row changed since the caller read it: re-read and decide again."""


def retryable(e: Exception) -> bool:
    """Whether a failed attempt is worth repeating from the start: a lost race on a unique key or
    on the workflow row, or the database's own deadlock/serialization verdict (Postgres 40P01,
    40001). Nothing was committed, so the repeat sees the winner's rows."""
    if isinstance(e, (StateConflict, IntegrityError)):
        return True
    orig = getattr(e, "orig", None)
    code = (getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)
            or getattr(getattr(orig, "__cause__", None), "sqlstate", None))
    return code in ("40P01", "40001")


def next_action(state: str) -> str:
    return NEXT_ACTION[state]


def check(old: str, new: str) -> None:
    if new not in STATES:
        raise IllegalTransition(f"unknown state {new}")
    if old == "closed":
        raise IllegalTransition("a closed workflow never changes")
    if new == "accepted" and old != "accepted":
        raise IllegalTransition("accepted is only the first state")


def _event(new: str, revision: int, reason: str | None, closed_at: float | None) -> tuple[str, dict]:
    body: dict[str, Any] = {"state": new, "revision": revision}
    if new == "closed":
        return "workflow.closed", {**body, "reason": reason, "closed_at": iso(closed_at)}
    if new == "awaiting_user":
        return "workflow.awaiting_user", {**body, "reason": reason or "reply_expected"}
    if new == "needs_attention":
        return "workflow.needs_attention", {**body, "reason": reason}
    return "workflow.status_changed", {**body, **({"reason": reason} if reason else {})}


async def sync_approvals(conn, workflow_id: str, revision: int) -> None:
    """A pending approval always carries the revision the partner must send back (contract 9.4, 9.8)."""
    await conn.execute(update(t.approvals).where(
        t.approvals.c.workflow_id == workflow_id, t.approvals.c.status == "pending")
        .values(workflow_revision=revision))


async def bump(conn, wf: Any) -> dict:
    """Revision+1 without a change of state: the set of pending approvals changed (spec A1). Same
    compare-and-set as `transition`; the public event of the change is the caller's."""
    rev = wf["revision"] + 1
    stamp = now()
    done = await conn.execute(update(t.workflows).where(
        t.workflows.c.id == wf["id"], t.workflows.c.revision == wf["revision"], t.workflows.c.state == wf["state"])
        .values(revision=rev, last_activity_at=stamp))
    if done.rowcount != 1:
        raise StateConflict(wf["id"])
    await sync_approvals(conn, wf["id"], rev)
    return {**dict(wf), "revision": rev, "last_activity_at": stamp}


async def transition(conn, wf: Any, new_state: str, *, reason: str | None = None,
                     request_id: str | None = None,
                     emit_after: Iterable[tuple[str, dict]] = ()) -> dict:
    """Move `wf` (a row as the caller read it) to `new_state` inside the caller's transaction.

    Writes state, revision+1, last activity and the public event of the change, then `emit_after`
    (further events of the same commit). Compare-and-set on state and revision: if another writer
    got there first it raises StateConflict and the caller re-reads. The same state only records
    activity: no revision bump, no event. Returns the updated workflow as a dict.
    """
    old, rev = wf["state"], wf["revision"]
    check(old, new_state)
    if new_state == "needs_attention" and not reason:
        raise ValueError("needs_attention carries a public reason code")
    stamp = now()
    values: dict[str, Any] = {"last_activity_at": stamp}
    if request_id:
        values["current_request_id"] = request_id
    out = {**dict(wf), **values}
    changed = new_state != old
    if changed:
        values.update(state=new_state, revision=rev + 1, expects=EXPECTS.get(new_state))
        if new_state == "closed":
            values.update(close_reason=reason, closed_at=stamp)
        if new_state == "needs_attention":
            values["attention_reason"] = reason
        elif old == "needs_attention":
            values["attention_reason"] = None
        out.update(values)
    done = await conn.execute(update(t.workflows).where(
        t.workflows.c.id == wf["id"], t.workflows.c.state == old, t.workflows.c.revision == rev)
        .values(**values))
    if done.rowcount != 1:
        raise StateConflict(wf["id"])
    if changed:
        await sync_approvals(conn, wf["id"], rev + 1)
        etype, payload = _event(new_state, rev + 1, reason, stamp)
        await emit(conn, wf["conversation_id"], etype, payload, workflow=out)
    for etype, payload in emit_after:
        await emit(conn, wf["conversation_id"], etype, payload, workflow=out)
    return out
