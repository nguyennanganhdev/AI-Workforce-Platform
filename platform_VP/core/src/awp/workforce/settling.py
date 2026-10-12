"""Settle: when the leader's session has gone idle, read what the database says about the chain of
turns, decide where the workflow rests (decide.py), and apply that in ONE transaction: the state change
with its events, the requests it completes, a nudge job or the safe message.

It is idempotent. Run twice on the same facts it does nothing the second time, so the engine runs it
after every job and again whenever a turn the engine did not start (a worker's report waking the leader)
ends. It never runs while a job is queued or dispatched or a turn is running: the facts would be half.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import insert, or_, select

from .. import db as core
from ..casefile import build_view
from . import tables as t
from .close import shut
from .common import now
from .decide import Decision, Facts, decide
from .events import lock_conversation
from .jobs import cycle_job
from .lookup import inflight_request, route_of, rules_of
from .messages import add_assistant_message, owed
from .settle import PENDING, settle_request
from .tables import new_id
from .workflows import BLOCKED, BUSY, transition


async def team_names(rt, tenant: str, leader_session: str) -> list[str]:
    """Names of the workers the leader created, from AgentScope's team roster. The room binds a worker
    only when its first run starts, so a worker just created is in this list before it is anywhere else."""
    from ..agentscope_client import owner_of

    user, names = owner_of(tenant), []
    for team in await rt.storage.list_teams(user):
        if team.session_id != leader_session:
            continue
        for m in team.data.members:
            agent = await rt.storage.get_agent(m.owner_id, m.agent_id)
            names.append(agent.data.name if agent else m.agent_id)
    return names


async def workers_pending(rt, case_id: str) -> bool:
    """The leader's chain is not over, whatever it said: a worker has not reported, a question or a
    challenge is still open, or something addressed to the leader is not read yet (the worker's report
    is in the case file but the turn it wakes has not started, so the digest cursor is behind it)."""
    items = await rt.cases.items(case_id)
    view = build_view(items)
    members = await rt.cases.sessions_of_case(case_id)
    lead = next((m for m in members if m["role"] == "leader"), None)
    case = await rt.cases.get_case(case_id)
    created = await team_names(rt, case["tenant"], lead["session_id"]) if lead and case else []
    bound = [w["agent_name"] for w in members if w["role"] == "worker"]
    if [n for n in {*created, *bound} if n not in view.reports]:
        return True
    if view.open_questions() or view.open_challenges():
        return True
    if lead is None:
        return False
    seen = await rt.cases.get_cursor(case_id, lead["session_id"])
    return any(i.id > seen and (i.kind == "report" or i.addressee == lead["agent_name"]) for i in items)


async def unfinished(conn, workflow_id: str, turn_timeout: float, held: bool = False) -> bool:
    """A job is queued or dispatched, or a turn is running (one running for longer than the timeout is
    a leftover of a crash, not a turn). `held`: the workflow waits for the resident's decision, so a queued job
    that is not the answer to a decision is held back by the engine until then (resume.parked) and is not work
    in progress."""
    where = [t.jobs.c.workflow_id == workflow_id]
    if held:
        where.append(or_(t.jobs.c.status == "dispatched", t.jobs.c.kind == "approval_resume"))
    job = (await conn.execute(select(t.jobs.c.id).where(
        *where, t.jobs.c.status.in_(("queued", "dispatched"))).limit(1))).first()
    if job is not None:
        return True
    turn = (await conn.execute(select(t.turns.c.id).where(
        t.turns.c.workflow_id == workflow_id, t.turns.c.status == "running",
        t.turns.c.started_at > now() - turn_timeout).limit(1))).first()
    return turn is not None


async def consent_ran(conn, wf: Any) -> bool:
    """A tool the resident agreed to passed the gate AND returned a result: the case file holds its evidence
    (the evidence middleware records successful results only, so a tool that failed does not count). The
    consent tool itself is the resident's word, not an effect."""
    used = (await conn.execute(select(t.approvals.c.tool_name, t.approvals.c.used_at).where(
        t.approvals.c.workflow_id == wf["id"], t.approvals.c.used_at.is_not(None),
        t.approvals.c.tool_name != "CaseAskConsent"))).all()
    if not used:
        return False
    seen = (await conn.execute(select(core.case_items.c.data, core.case_items.c.created_at).where(
        core.case_items.c.case_id == wf["case_id"], core.case_items.c.kind == "evidence"))).all()
    return any(data.get("tool") == tool and at >= used_at for tool, used_at in used for data, at in seen)


def operations_at_rest(ops: list, tracking: dict) -> tuple[int, int]:
    """(operations still moving, operations that cannot be found out about). An unknown operation moves
    only when the route can ask the partner what became of it (tracking status_query); otherwise a person has
    to look, until an operator has."""
    moving = lost = 0
    for status, tool, result in ops:
        if status in ("intent", "sent", "pending"):
            moving += 1
        elif status == "unknown":
            if tracking.get(tool) == "status_query":
                moving += 1
            elif not (result or {}).get("reviewed"):  # a person looked and let the workflow go on (admin_ops.resolve)
                lost += 1
    return moving, lost


async def gather(conn, wf: Any, route: Any, pending: bool) -> tuple[Facts, Any]:
    cycle = await cycle_job(conn, wf["id"])
    start = cycle["payload"].get("start_seq", 0) if cycle else 0
    said = (await conn.execute(select(t.messages.c.expects, t.messages.c.outcome).where(
        t.messages.c.workflow_id == wf["id"], t.messages.c.sender == "assistant",
        t.messages.c.sequence > start, t.messages.c.expects.is_not(None))
        .order_by(t.messages.c.sequence))).all()
    outcomes = [o for _, o in said if o]
    heard = [e for e, _ in said if e != "none"]  # a question outweighs an informing line after it
    asked = (await conn.execute(select(t.messages.c.id).where(
        t.messages.c.workflow_id == wf["id"], t.messages.c.expects == "confirmation").limit(1))).first()
    approvals = (await conn.execute(select(t.approvals.c.status).where(
        t.approvals.c.workflow_id == wf["id"]))).scalars().all()
    ops = (await conn.execute(select(t.operations.c.status, t.operations.c.tool_name, t.operations.c.result)
                              .where(t.operations.c.workflow_id == wf["id"]))).all()
    tracking = dict((await conn.execute(select(t.tools.c.name, t.tools.c.tracking).where(
        t.tools.c.route_id == wf["route_id"]))).all())
    open_, lost = operations_at_rest(ops, tracking)
    done = any(s == "completed" for s, _, _ in ops) or await consent_ran(conn, wf)
    last = (await conn.execute(select(t.turns.c.status).where(t.turns.c.workflow_id == wf["id"])
                               .order_by(t.turns.c.started_at.desc()).limit(1))).scalar()
    nudges = 0
    if cycle is not None:
        sent = (await conn.execute(select(t.jobs.c.payload).where(
            t.jobs.c.workflow_id == wf["id"], t.jobs.c.kind == "nudge"))).scalars().all()
        nudges = sum(1 for p in sent if p.get("cycle") == cycle["id"])
    unanswered = await owed(conn, wf["id"])
    return Facts(
        state=wf["state"], approvals=sum(1 for s in approvals if s == "pending"), parked=last == "parked",
        workers_pending=pending, said=heard[-1] if heard else ("none" if said else None),
        ops_open=open_, ops_lost=lost,
        acted=bool(ops or approvals or asked),  # asking for confirmation makes POST close the only way out
        done=done, failed=bool(ops) and not done,
        outcome=outcomes[-1] if outcomes else None,
        auto_close=(route["config"].get("policy") or {}).get("auto_close_read_only", True),
        nudges=nudges, owed=unanswered[0] if unanswered else None), cycle


async def settle_waiting(conn, workflow_id: str) -> None:
    """Complete every request still waiting: the workflow is at rest and no job is left for them."""
    ids = (await conn.execute(select(t.requests.c.id).where(
        t.requests.c.workflow_id == workflow_id, t.requests.c.status.in_(PENDING))
        .order_by(t.requests.c.accepted_at))).scalars().all()
    for rid in ids:
        await settle_request(conn, rid)


async def apply(rt, conn, wf: Any, route: Any, d: Decision, cycle: Any) -> str | None:
    """Do what `decide` said. Returns "nudge" or "closed" when the engine has more to do after the commit."""
    if d.kind == "stay":
        return None
    if d.kind == "nudge":
        await conn.execute(insert(t.jobs).values(
            id=new_id("job"), workflow_id=wf["id"], kind="nudge",
            request_id=cycle["request_id"] if cycle else wf["current_request_id"],
            payload={"cycle": cycle["id"] if cycle else None}, status="queued", attempts=0, created_at=now()))
        return "nudge"
    if d.kind == "close":
        await shut(rt, conn, wf, d.reason)
        return "closed"
    if d.safe_say:  # the resident is told something true and safe; the reason stays on the workflow
        await add_assistant_message(conn, wf, rules_of(route["config"]).safe_reply,
                                    await inflight_request(conn, wf["id"]))
    await transition(conn, wf, d.state, reason=d.reason)
    await settle_waiting(conn, wf["id"])
    return None


async def settle(eng, workflow_id: str) -> str | None:
    """One settle pass for a workflow. Returns what the engine should do next ("nudge", "closed") or None.

    A workflow whose authorization was withdrawn while its turn ran (`blocked_*`) is not decided on, but the
    request that was running ends as `blocked` instead of staying `running` for ever.

    A workflow in `awaiting_approval` is not decided on either (the gate already put it there, in the
    transaction that wrote the approval), but its requests end: the resident's next step is to decide. That
    includes the requests of replies queued behind the parked agent, which wait for the decision to be sent."""
    rt, db = eng.rt, eng.ctx.db
    async with db.engine.connect() as conn:
        wf = (await conn.execute(select(t.workflows).where(t.workflows.c.id == workflow_id))).mappings().first()
    if wf is None or (wf["state"] not in BUSY and wf["state"] not in BLOCKED and wf["state"] != "awaiting_approval"):
        return None
    pending = await workers_pending(rt, wf["case_id"]) if wf["state"] in BUSY else False
    async with db.engine.begin() as conn:
        await lock_conversation(conn, wf["conversation_id"])
        wf = (await conn.execute(select(t.workflows).where(t.workflows.c.id == workflow_id))).mappings().one()
        if await unfinished(conn, workflow_id, eng.settings.wf_turn_timeout_seconds,
                            held=wf["state"] == "awaiting_approval"):
            return None
        if wf["state"] in BLOCKED or wf["state"] == "awaiting_approval":
            await settle_waiting(conn, workflow_id)
            return None
        if wf["state"] not in BUSY:
            return None
        route = await route_of(conn, wf)
        facts, cycle = await gather(conn, wf, route, pending)
        return await apply(rt, conn, wf, route, decide(facts), cycle)
