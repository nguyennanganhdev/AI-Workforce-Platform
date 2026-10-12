"""Picking up what a crash or a failed write left half done, so that nothing waits for a timer.

A turn row stays 'running' when the process died or closing it failed; a job stays 'dispatched' when its
dispatcher died after the turn. Neither may hold a workflow for a whole lease or turn timeout, and neither
may make the leader answer the resident twice. An approval stays 'pending' with no agent parked on it when the
process died between writing the row and saving the parked run: its answer would wake nobody (`orphan_approvals`).
The other way round, an agent that was handed its answer and died before the turn ended is still parked while the
row says it was woken (`orphan_parks`).
"""
from __future__ import annotations

import logging

from agentscope.app.message_bus import MessageBusKeys
from sqlalchemy import func, insert, or_, select, update

from . import tables as t
from .approvals import RESUME, resolve
from .common import now
from .engine import finish_job
from .events import lock_conversation
from .leader import Leader, leader_of
from .resume import LOST, still_parked
from .tables import new_id
from .workflows import BLOCKED, StateConflict

log = logging.getLogger("awp.workforce")

ENDED = ("completed", "parked")  # a turn that did its work; an interrupted one (a crash) did not, and its job runs again


async def orphan_turns(eng, workflow_id: str | None = None) -> int:
    """Mark 'running' turns whose leader session is idle as 'interrupted'.

    A live turn holds the session lock from before its row is written until after it is closed, so a row
    that is still 'running' while the lock is free belongs to a dead run. The rows are read first and the
    lock afterwards: a run that starts in between has a row we never saw."""
    query = select(t.turns.c.id, t.turns.c.workflow_id).where(t.turns.c.status == "running")
    if workflow_id:
        query = query.where(t.turns.c.workflow_id == workflow_id)
    async with eng.ctx.db.engine.connect() as conn:
        rows = (await conn.execute(query)).all()
        cases = {w: c for w, c in (await conn.execute(select(t.workflows.c.id, t.workflows.c.case_id).where(
            t.workflows.c.id.in_({w for _, w in rows})))).all()} if rows else {}
    by_workflow: dict[str, list[str]] = {}
    for turn_id, wid in rows:
        by_workflow.setdefault(wid, []).append(turn_id)
    closed = 0
    for wid, ids in by_workflow.items():
        leader = await leader_of(eng.rt, cases[wid]) if cases.get(wid) else None
        if leader is not None and await eng.rt.bus.is_locked(MessageBusKeys.session_lock(leader.session_id)):
            continue
        async with eng.ctx.db.engine.begin() as conn:
            done = await conn.execute(update(t.turns).where(t.turns.c.id.in_(ids), t.turns.c.status == "running")
                                      .values(status="interrupted", ended_at=now()))
        if done.rowcount:
            log.warning("workflow %s: %s turn(s) were left running and are closed", wid, done.rowcount)
            closed += done.rowcount
    return closed


PARKED = ("awaiting_permission", "running")  # parked on it, or in a run that is about to park (or belongs to another process)


async def orphan_approvals(eng) -> int:
    """At startup, and when a process of the fleet died (spec 13.25): cancel every pending approval whose agent is not
    parked, and have the leader told.

    The resident may already have been shown the request, so it is cancelled in the open (`approval.resolved`, the
    workflow leaves `awaiting_approval`, a late decision gets APPROVAL_NOT_PENDING) and the leader says so; without
    this the workflow would sit in `awaiting_approval` until the approval expired, and an approval given meanwhile
    would run nothing. A session that cannot be read is left alone: the next start looks again.

    When the turn that asked is going to run again (its job is still queued or dispatched: the process died in the
    middle of it) the leader is not told: that turn starts from its message and asks again by itself."""
    async with eng.ctx.db.engine.connect() as conn:
        rows = (await conn.execute(select(t.approvals, t.workflows.c.case_id).select_from(
            t.approvals.join(t.workflows, t.workflows.c.id == t.approvals.c.workflow_id)).where(
            t.approvals.c.status == "pending", t.workflows.c.state.notin_(("closed", *BLOCKED))))).mappings().all()
    cancelled = 0
    for r in rows:
        leader = await leader_of(eng.rt, r["case_id"])
        try:
            status = await eng.client.status(leader.tenant, r["agent_id"], r["session_id"]) if leader else "gone"
        except Exception:
            log.exception("approval %s: the session of its agent could not be read", r["id"])
            continue
        if status is None or status in PARKED:
            continue
        try:
            async with eng.ctx.db.engine.begin() as conn:
                if not await lock_conversation(conn, r["conversation_id"], wait=False):
                    continue
                wf = (await conn.execute(select(t.workflows).where(t.workflows.c.id == r["workflow_id"]))).mappings().one()
                row = (await conn.execute(select(t.approvals).where(t.approvals.c.id == r["id"]))).mappings().one()
                if row["status"] != "pending" or wf["state"] == "closed" or wf["state"] in BLOCKED:
                    continue
                # nobody is parked, so there is nobody to wake: the job goes straight to telling the leader
                await conn.execute(update(t.approvals).where(t.approvals.c.id == r["id"]).values(resumed_at=now()))
                again = (await conn.execute(select(t.jobs.c.id).where(
                    t.jobs.c.workflow_id == wf["id"], t.jobs.c.status.in_(("queued", "dispatched")),
                    t.jobs.c.kind != "approval_resume").limit(1))).first() is not None
                await resolve(conn, wf, row, "cancelled", request_id=None, reason="approval_lost", why=LOST, wake=not again)
        except StateConflict:
            continue
        log.warning("approval %s of workflow %s had no parked agent (session %s): cancelled", r["id"], r["workflow_id"], status)
        cancelled += 1
        eng.kick(r["workflow_id"])
    return cancelled


async def orphan_parks(eng) -> int:
    """At startup, and when a process of the fleet died: an agent still parked on an approval that the row says it was
    woken for. The process that woke it died before the run was saved (a run is saved when it ends), so the agent took
    nothing in: the acknowledgement is withdrawn and a job carries the answer again. The tool the resident agreed to
    still runs at most once: its consent is used once (`used_at`) and its operation is in the ledger."""
    a = t.approvals
    latest = select(a.c.session_id, func.max(a.c.created_at).label("at")).group_by(a.c.session_id).subquery()
    async with eng.ctx.db.engine.connect() as conn:
        rows = (await conn.execute(select(a, t.workflows.c.case_id).select_from(
            a.join(t.workflows, t.workflows.c.id == a.c.workflow_id)
            .join(latest, (latest.c.session_id == a.c.session_id) & (latest.c.at == a.c.created_at))).where(
            a.c.status != "pending", a.c.resumed_at.is_not(None), a.c.reply_id.is_not(None),
            t.workflows.c.state.notin_(("closed", *BLOCKED))))).mappings().all()
    put_right = 0
    for r in rows:
        leader = await leader_of(eng.rt, r["case_id"])
        if leader is None or not await still_parked(eng, Leader(leader.tenant, r["agent_id"], r["session_id"])):
            continue
        async with eng.ctx.db.engine.begin() as conn:
            done = await conn.execute(update(a).where(a.c.id == r["id"], a.c.resumed_at.is_not(None)).values(resumed_at=None))
            if done.rowcount != 1:
                continue
            carried = (await conn.execute(select(t.jobs.c.payload).where(
                t.jobs.c.workflow_id == r["workflow_id"], t.jobs.c.kind == "approval_resume",
                t.jobs.c.status.in_(("queued", "dispatched"))))).scalars().all()
            if r["status"] != "cancelled" and not any(p.get("approval_id") == r["id"] for p in carried):
                await conn.execute(insert(t.jobs).values(  # (a cancelled one is closed by resume.unpark)
                    id=new_id("job"), workflow_id=r["workflow_id"], kind="approval_resume",
                    request_id=None, status="queued", payload={"approval_id": r["id"]}, attempts=0, created_at=now()))
        log.warning("approval %s: its agent was handed the answer by a process that died; it is handed over again", r["id"])
        put_right += 1
        eng.kick(r["workflow_id"])
    return put_right


async def spoke(eng, job) -> bool:
    """An attempt of this job was cut short after the leader had spoken to the resident: what it said is out, and
    running the job again would say it a second time."""
    mine = [t.turns.c.job_id == job["id"]]
    if job["kind"] == "approval_resume":
        mine.append(t.turns.c.msg_id == RESUME + str(job["payload"].get("approval_id")))
    async with eng.ctx.db.engine.connect() as conn:
        began = (await conn.execute(select(func.min(t.turns.c.started_at)).where(
            t.turns.c.workflow_id == job["workflow_id"], or_(*mine)))).scalar()
        if began is None:
            return False
        return (await conn.execute(select(t.messages.c.id).where(
            t.messages.c.workflow_id == job["workflow_id"], t.messages.c.sender == "assistant",
            t.messages.c.created_at >= began).limit(1))).first() is not None


async def recover_job(eng, job) -> None:
    """A dispatched job whose dispatcher is gone (its lease ran out): done when its turn ended well or the leader had
    already spoken in it, else another attempt."""
    from .runner import JobFailed

    try:
        if await answered(eng, job) or await spoke(eng, job):
            async with eng.ctx.db.engine.begin() as conn:
                conv = (await conn.execute(select(t.workflows.c.conversation_id).where(
                    t.workflows.c.id == job["workflow_id"]))).scalar_one()
                if not await lock_conversation(conn, conv, wait=False):
                    return  # in use: the next sweep finds the job again
                await finish_job(conn, job["id"], owner=job["lease_owner"])
            eng._unsettled.add(job["workflow_id"])
            eng.kick(job["workflow_id"])
        else:
            await eng._fail(job, JobFailed("the dispatcher is gone"))
            eng.kick(job["workflow_id"])  # the attempt it was given starts now, not at the next sweep
    except Exception:
        log.exception("could not recover job %s", job["id"])


async def answered(eng, job) -> bool:
    """A turn this job started has ended without an error: its work is done, whatever happened to the
    dispatcher afterwards. Sending the message again would make the leader answer twice."""
    async with eng.ctx.db.engine.connect() as conn:
        return (await conn.execute(select(t.turns.c.id).where(
            t.turns.c.job_id == job["id"], t.turns.c.status.in_(ENDED)).limit(1))).first() is not None
