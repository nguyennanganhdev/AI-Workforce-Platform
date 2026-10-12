"""Waking an agent that is parked on an approval (spec 13.3-6, A9), for the engine.

Three things end a parked agent's wait, and each is an event built from the STORED approval row, never from what a
client sent:

  approved / rejected   UserConfirmResultEvent through POST /chat (P0 test 5): the tool runs once, or the agent
                        is told DENIED. Never `rules`.
  expired               UserInterruptEvent through the wake-up queue (P0 test 14; /chat cannot carry it): the
                        pending call is closed as interrupted and the run does not call the model, so the
                        leader is then told in a message of its own and says it to the resident.
  cancelled             the same interrupt, sent when the workflow closed: no session is left parked.
                        Also sent for a decision whose own job gave up (the engine could not deliver the answer):
                        the agent is closed as interrupted, so that nothing keeps the workflow's other jobs back.

The agent that asked may be a specialist, so the event goes to the session stored on the row. The agent
took the event when its run began (`resumed_at`, noted by the gate's on_reply): a 200 alone does not say so.
"""
from __future__ import annotations

import logging
from typing import Any

from agentscope.event import ConfirmResult, UserConfirmResultEvent, UserInterruptEvent
from agentscope.message import ToolCallBlock
from sqlalchemy import insert, or_, select, update

from . import tables as t
from .approvals import RESUME
from .common import now
from .context import clip
from .leader import Leader, leader_of
from .settle import PENDING
from .tables import new_id

log = logging.getLogger("awp.workforce")


def event_for(row: Any) -> UserConfirmResultEvent | UserInterruptEvent:
    eid = RESUME + row["id"]
    if row["status"] in ("approved", "rejected"):
        call = ToolCallBlock(id=row["tool_call_id"], name=row["tool_name"], input=row["arguments"])
        return UserConfirmResultEvent(id=eid, reply_id=row["reply_id"], confirm_results=[
            ConfirmResult(confirmed=row["status"] == "approved", tool_call=call)])
    return UserInterruptEvent(id=eid, reply_id=row["reply_id"])


LOST = "lost"  # the `why` of an approval cancelled because no agent was parked on it any more (recover.orphan_approvals)


def notice(row: Any, why: str | None = None) -> str:
    """Told to the leader after an approval ran out or was withdrawn; ours, so it is not wrapped as untrusted data."""
    what = clip(str((row["summary"] or {}).get("text", row["tool_name"])), 200)
    if why == LOST:  # the platform restarted in the middle of asking: the call that waited for the answer is gone
        return ("<platform-notice>Your request for consent (" + what + ") was cancelled because the platform restarted "
                "while it was open. The resident agreed to nothing and nothing was done for it. Tell the resident with "
                "CaseSay that the request was cancelled and that an answer to it no longer counts; if it is still "
                "needed, ask for their consent again.</platform-notice>")
    if row["status"] == "cancelled":  # withdrawn by the platform: the work it priced ended or was quoted again
        return ("<platform-notice>Your request for consent (" + what + ") was withdrawn: the work it was about ended or "
                "was quoted again. The resident agreed to nothing and nothing was done for it. Tell the resident with "
                "CaseSay that it no longer stands; if a new quote follows you will ask again. Do not repeat the request "
                "on your own.</platform-notice>")
    return ("<platform-notice>The resident did not answer your request for consent in time (" + what + "): it "
            "expired and nothing was done. Tell the resident with CaseSay that it expired and ask whether they "
            "still want it (expects=\"reply\"); do not repeat the request on your own.</platform-notice>")


async def parked(conn, workflow_id: str, session_id: str | None = None) -> bool:
    """An agent of the workflow (or the one with `session_id`) still waits on an approval: pending, or decided
    and not woken yet. Whatever else is said to it meanwhile is lost (P0), so the engine sends it nothing but
    the answer."""
    q = select(t.approvals.c.id).where(
        t.approvals.c.workflow_id == workflow_id, t.approvals.c.reply_id.is_not(None),
        t.approvals.c.status != "cancelled",
        or_(t.approvals.c.status == "pending", t.approvals.c.resumed_at.is_(None)))
    if session_id is not None:
        q = q.where(t.approvals.c.session_id == session_id)
    return (await conn.execute(q.limit(1))).first() is not None


async def stuck(conn, workflow_id: str | None = None) -> list[Any]:
    """Approvals whose agent is still parked and will get no answer: cancelled, decided in a workflow that has
    closed since, or decided but the job that carries the answer failed for good (the engine gave up)."""
    q = select(t.approvals, t.workflows.c.state.label("wf_state")).select_from(
        t.approvals.join(t.workflows, t.workflows.c.id == t.approvals.c.workflow_id)).where(
        t.approvals.c.resumed_at.is_(None), t.approvals.c.reply_id.is_not(None), t.approvals.c.status != "pending")
    if workflow_id is not None:
        q = q.where(t.approvals.c.workflow_id == workflow_id)
    rows = (await conn.execute(q)).mappings().all()
    failed = {j["payload"].get("approval_id") for j in (await conn.execute(select(t.jobs.c.payload).where(
        t.jobs.c.kind == "approval_resume", t.jobs.c.status == "failed",
        t.jobs.c.workflow_id.in_({r["workflow_id"] for r in rows})))).mappings()} if rows else set()
    return [r for r in rows if r["status"] == "cancelled" or r["wf_state"] == "closed" or r["id"] in failed]


async def needing_work(conn) -> list[str]:
    """Workflows the periodic sweep must look at because of approvals: a session to close, or requests that wait
    in `awaiting_approval` for a settle that did not come."""
    waiting = select(t.requests.c.workflow_id).select_from(
        t.requests.join(t.workflows, t.workflows.c.id == t.requests.c.workflow_id)).where(
        t.requests.c.status.in_(PENDING), t.workflows.c.state == "awaiting_approval")
    return sorted({*(r["workflow_id"] for r in await stuck(conn)), *(await conn.execute(waiting)).scalars()})


async def get(eng, approval_id: str) -> Any:
    async with eng.ctx.db.engine.connect() as conn:
        return (await conn.execute(select(t.approvals).where(t.approvals.c.id == approval_id))).mappings().one()


async def acked(eng, approval_id: str) -> bool:
    async with eng.ctx.db.engine.connect() as conn:
        return (await conn.execute(select(t.approvals.c.resumed_at).where(
            t.approvals.c.id == approval_id))).scalar() is not None


async def _send(eng, target: Leader, row: Any) -> None:
    event = event_for(row)
    if isinstance(event, UserConfirmResultEvent):
        await eng.client.confirm(target.tenant, target.agent_id, target.session_id, event)
    else:
        await eng.client.abandon(target.tenant, target.agent_id, target.session_id, event)


async def still_parked(eng, target: Leader) -> bool:
    """The session waits on a permission right now (nothing runs in it and its saved run is parked)."""
    try:
        return await eng.client.status(target.tenant, target.agent_id, target.session_id) == "awaiting_permission"
    except Exception:
        log.exception("the session %s could not be read", target.session_id)
        return False


async def unresumed(eng, row: Any, target: Leader) -> Any:
    """The row says its agent took the answer, and the agent is still parked: the run that took it died before it was
    saved (a crash; R9 of the decisions). The acknowledgement is withdrawn so that the answer is sent again."""
    if row["resumed_at"] is None or not await still_parked(eng, target):
        return row
    async with eng.ctx.db.engine.connect() as conn:
        newer = (await conn.execute(select(t.approvals.c.id).where(
            t.approvals.c.session_id == row["session_id"], t.approvals.c.created_at > row["created_at"]).limit(1))).first()
    if newer is not None:
        return row  # parked on a later request of its own
    async with eng.ctx.db.engine.begin() as conn:
        await conn.execute(update(t.approvals).where(t.approvals.c.id == row["id"]).values(resumed_at=None))
    log.warning("approval %s: its agent is still parked after it was woken; the answer is sent again", row["id"])
    return {**row, "resumed_at": None}


async def wake(eng, wid: str, target: Leader, row: Any) -> None:
    """Send the event until the agent took it."""
    await eng._deliver(wid, target, "", RESUME + row["id"], "", send=lambda: _send(eng, target, row),
                       acked=lambda: acked(eng, row["id"]))


async def run(eng, wid: str, job: Any, leader: Leader) -> None:
    """The job `approval_resume`: wake the agent that asked, wait for its turn to end, and for an expired
    approval then wake the leader to tell the resident."""
    from .runner import JobFailed

    row = await get(eng, job["payload"]["approval_id"])
    target = Leader(leader.tenant, row["agent_id"], row["session_id"])
    if job["attempts"] > 1:  # the attempt before this one may have died after the agent took the answer
        row = await unresumed(eng, row, target)
    for _ in range(3):
        if row["resumed_at"] is None:  # a repeated attempt finds the agent already woken
            await wake(eng, wid, target, row)
        await eng._await_end(wid, job, leader, target)
        # The agent's turn may have run in another process of the fleet (AgentScope's wake-up queue), and that process
        # may have died in it: the turn is over, and the agent is still parked. Then it is handed its answer again.
        row = await unresumed(eng, await get(eng, row["id"]), target)
        if row["resumed_at"] is not None:
            break
    else:
        raise JobFailed("the agent never took the decision in")
    await eng._check_turn(wid, RESUME + row["id"])
    if row["status"] in ("expired", "cancelled") and not await eng._halted(wid):
        async with eng.ctx.db.engine.connect() as conn:
            waits = await parked(conn, wid, leader.session_id)
        why = job["payload"].get("why")
        if waits:  # the leader is itself parked on another approval: a message to it would be lost (P0), so the notice waits for it
            await defer_notice(eng, wid, row, why)
            return
        msg_id = f"{job['id']}.notice"
        await eng._deliver(wid, leader, notice(row, why), msg_id, "platform")
        await eng._await_end(wid, job, leader)
        await eng._check_turn(wid, msg_id)


async def defer_notice(eng, wid: str, row: Any, why: str | None = None) -> None:
    """The notice of an expired approval as a job of its own: the engine sends it when no agent is parked."""
    async with eng.ctx.db.engine.begin() as conn:
        await conn.execute(insert(t.jobs).values(
            id=new_id("job"), workflow_id=wid, kind="notice", request_id=None, status="queued",
            payload={"approval_id": row["id"], **({"why": why} if why else {})}, attempts=0, created_at=now()))


async def unpark(eng, wid: str) -> bool:
    """Close the pending call of every session still parked on an approval nobody will answer (see `stuck`).
    True when something was sent."""
    async with eng.ctx.db.engine.connect() as conn:
        wf = (await conn.execute(select(t.workflows).where(t.workflows.c.id == wid))).mappings().first()
        if wf is None:
            return False
        rows = await stuck(conn, wid)
    if not rows:
        return False
    lead = await leader_of(eng.rt, wf["case_id"])
    if lead is None:
        return False
    for r in rows:
        target = Leader(lead.tenant, r["agent_id"], r["session_id"])
        cancelled = {**r, "status": "cancelled"}  # whatever was decided, a closed workflow only interrupts
        try:
            await eng._deliver(wid, target, "", RESUME + r["id"], "", send=lambda: _send(eng, target, cancelled),
                               acked=lambda: acked(eng, r["id"]))
        except Exception:  # the session is not parked any more, or is gone: do not try for ever
            log.exception("approval %s: the parked session could not be closed", r["id"])
            async with eng.ctx.db.engine.begin() as conn:
                await conn.execute(update(t.approvals).where(t.approvals.c.id == r["id"]).values(resumed_at=now()))
    return True
