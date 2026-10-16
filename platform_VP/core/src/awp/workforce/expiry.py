"""Expiry of a workflow that stopped moving (spec A9). A workflow that waits for a person or a worker is not
stalled, so only a workflow that should be moving by itself is flagged.

  accepted/active   nothing ran, queued or happened for `case_stall_seconds`  -> needs_attention (stalled)
  waiting_external_event  no news for `request_timeout_hours`                  -> needs_attention (external_timeout)
  awaiting_user / awaiting_approval / awaiting_confirmation                    never change by time

The one thing that does run out in a resting workflow is an approval (`expires_at`, route policy
`approval_ttl_seconds`): it becomes `expired`, the agent that asked is woken with an interrupt and the leader
is told to say so (resume.py), and the workflow is active again.

Each candidate is re-checked under the conversation's lock, so a reply, a close or a turn that landed
since the scan wins.
"""
from __future__ import annotations

import logging
import time

from sqlalchemy import func, select

from .. import db as core
from . import tables as t
from .approvals import resolve
from .common import now
from .events import lock_conversation
from .settle import fail_message, settle_request
from .settling import settle_waiting, unfinished
from .workflows import BLOCKED, StateConflict, transition

log = logging.getLogger("awp.workforce")


async def idle_for(conn, wf) -> float:
    """Seconds since the workflow last did anything: a transition, a turn, or an item in the case file
    (workers busy in the room write items, so a long team consultation is not a stall)."""
    turn = (await conn.execute(select(func.max(func.coalesce(t.turns.c.ended_at, t.turns.c.started_at)))
                               .where(t.turns.c.workflow_id == wf["id"]))).scalar() or 0
    item = 0
    if wf["case_id"]:
        item = (await conn.execute(select(func.max(core.case_items.c.created_at)).where(
            core.case_items.c.case_id == wf["case_id"]))).scalar() or 0
    return time.time() - max(wf["last_activity_at"] or 0, wf["created_at"], turn, item)


def due(wf, idle: float, stall: float, external: float) -> str | None:
    if wf["state"] in ("accepted", "active") and stall > 0 and idle > stall:
        return "stalled"
    if wf["state"] == "waiting_external_event" and idle > external:
        return "external_timeout"
    return None


async def expire_approvals(eng) -> int:
    """Approvals past `expires_at`: expired, and a job to wake the agent. A decision that landed first wins
    (the row is read again under the conversation's lock)."""
    db = eng.ctx.db
    async with db.engine.connect() as conn:
        due_now = (await conn.execute(select(t.approvals.c.id, t.approvals.c.workflow_id).where(
            t.approvals.c.status == "pending", t.approvals.c.expires_at.is_not(None),
            t.approvals.c.expires_at <= now()))).all()
    expired = 0
    for appr, wid in due_now:
        try:
            async with db.engine.begin() as conn:
                conv = (await conn.execute(select(t.workflows.c.conversation_id).where(t.workflows.c.id == wid))).scalar_one()
                if not await lock_conversation(conn, conv, wait=False):
                    continue  # somebody is working on this conversation: the next sweep looks again
                row = (await conn.execute(select(t.approvals).where(t.approvals.c.id == appr))).mappings().one()
                wf = (await conn.execute(select(t.workflows).where(t.workflows.c.id == wid))).mappings().one()
                if row["status"] != "pending" or wf["state"] == "closed" or wf["state"] in BLOCKED:
                    continue
                await resolve(conn, wf, row, "expired", request_id=None, reason="approval_expired")
        except StateConflict:  # a writer got there first; the next sweep looks again
            continue
        expired += 1
        eng.kick(wid)
    return expired


async def expire(eng) -> int:
    s, db = eng.settings, eng.ctx.db
    external = s.request_timeout_hours * 3600
    swept = await expire_approvals(eng)
    async with db.engine.connect() as conn:
        rows = (await conn.execute(select(t.workflows).where(
            t.workflows.c.state.in_(("accepted", "active", "waiting_external_event"))))).mappings().all()
        todo = [w for w in rows if due(w, await idle_for(conn, w), s.case_stall_seconds, external)]
    expired = 0
    for w in todo:
        async with db.engine.begin() as conn:
            if not await lock_conversation(conn, w["conversation_id"], wait=False):
                continue
            wf = (await conn.execute(select(t.workflows).where(t.workflows.c.id == w["id"]))).mappings().one()
            reason = due(wf, await idle_for(conn, wf), s.case_stall_seconds, external)
            if reason is None or await unfinished(conn, wf["id"], s.wf_turn_timeout_seconds):
                continue
            await transition(conn, wf, "needs_attention", reason=reason)
            if reason == "stalled":  # whoever waits for an answer is told it will not come
                ids = (await conn.execute(select(t.requests.c.id).where(
                    t.requests.c.workflow_id == wf["id"], t.requests.c.status.in_(("accepted", "queued", "running")))
                )).scalars().all()
                for rid in ids:
                    await settle_request(conn, rid, status="failed", error=fail_message("stalled"))
            await settle_waiting(conn, wf["id"])
            expired += 1
    return expired + swept
