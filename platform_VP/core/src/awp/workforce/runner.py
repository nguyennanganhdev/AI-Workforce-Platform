"""WorkflowEngine: runs the jobs of every workflow on its long-lived leader and settles the results.

One dispatcher task per workflow, started on demand (`notify`, a turn that ended, the periodic sweep) and
gone when there is nothing left to do. In it:

  job      claim (one dispatched job per workflow, in the conversation's lock order), make the leader
           exist, build the message for the job's kind, send it with say() under the job's id, wait until
           a wf_turns row carries that id (a 200 from /chat alone does not say the message arrived: send
           it again, same id, when it does not), wait until its turns ended AND the session is idle, then
           mark the job done and settle.
  settle   `settling.settle`, also whenever a turn the engine did not start (a worker's report waking the
           leader) has ended: the model's answer to the resident is never read from the stream, only
           what CaseSay and CaseFinalize wrote to the database counts.

A failed attempt is repeated up to `wf_job_attempts`, then the workflow needs attention (engine_error)
and the request fails with a public error, except that an attempt which failed after the leader had spoken
is not repeated (the resident already read it). Closing a workflow, or blocking it, while its turn runs
interrupts the turn.

Nothing waits for a timer when bookkeeping fails: the sweep settles every busy workflow with no dispatcher,
closes turn rows left running under an idle session, and finishes a dispatched job whose turn ended (`recover.py`).

Several processes run this engine on one database (`nodes.py`). A job is claimed by one of them (`lease_owner`), its
lease is renewed by that process's heartbeat while its dispatcher lives, and another process touches it only after the
lease ran out. A turn may run in another process than its job's dispatcher: all a dispatcher waits for is read from
the database and the shared session lock, never from memory.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from agentscope.app.message_bus import MessageBusKeys
from sqlalchemy import select, update

from ..agentscope_client import AgentScopeClient, SessionBusy
from ..evals import sandbox
from . import nodes, resume, tables as t
from .approvals import pending_count
from .common import now
from .engine import LockBusy, claim_job, finish_job
from .events import lock_conversation
from .expiry import expire
from .jobs import BUILDERS, CYCLE_KINDS, SENDER
from .leader import Leader, LeaderUnavailable, ensure_leader, leader_of
from .provider_sweep import apply_pending, stop as stop_provider_tasks
from .reconcile import reconcile
from .recover import orphan_approvals, orphan_parks, orphan_turns, recover_job
from .routecheck import block_if_moved
from .settle import fail_message, mark_running, settle_request
from .settling import settle
from .workflows import BLOCKED, BUSY, transition

log = logging.getLogger("awp.workforce")

MAX_SENDS = 4  # the same message is sent this many times before the job fails
UNREADY = 30.0  # seconds an agent may be "not parked" without having taken the event that should wake it
UNREADY_POLL = 0.2
POLL = 0.03
SLOW_POLL = 0.25  # what the waits below slow down to: a turn of a real model takes seconds, and every look is a query
HALT_EVERY = 0.5  # how often a running turn's workflow is checked for having been closed or blocked meanwhile


QUICK = 1.0  # seconds a wait keeps looking every POLL before it slows down


class Pace:
    """The pause between two looks at something that usually changes at once and sometimes takes minutes: POLL for the
    first second, then longer, up to SLOW_POLL. Twenty turns waited for at a fixed 30 ms were over a thousand queries a
    second that did nothing but ask (found by the load test, P5c); what answers within a second is as quick as before."""

    def __init__(self) -> None:
        self.reset()

    def next(self) -> float:
        if time.monotonic() - self.since < QUICK:
            return POLL
        now_, self.pause = self.pause, min(self.pause * 1.5, SLOW_POLL)
        return now_

    def reset(self) -> None:
        self.since, self.pause = time.monotonic(), POLL


class JobFailed(Exception):
    def __init__(self, why: str, retry: bool = True) -> None:
        super().__init__(why)
        self.retry = retry


class WorkflowEngine:
    def __init__(self, ctx, client: AgentScopeClient) -> None:
        self.ctx, self.client = ctx, client
        self.rt, self.settings = ctx.rt, ctx.settings
        self._tasks: dict[str, asyncio.Task] = {}
        self._again: set[str] = set()
        self._unsettled: set[str] = set()
        self._ended: dict[str, asyncio.Event] = {}  # workflow -> set when a turn of it ended in this process
        self._stopping = False
        self._reconciling: asyncio.Task | None = None
        self.node = getattr(self.rt, "node", "") or nodes.new_node()  # this process, in job leases and lock values
        self.lease = max(float(self.settings.wf_lease_seconds), 0.2)
        self._beat: asyncio.Task | None = None

    # ---- how work arrives -------------------------------------------------
    def notify(self, workflow_id: str, job_id: str) -> None:
        self.kick(workflow_id)

    def on_turn(self, workflow_id: str) -> None:
        """A turn of a leader ended (Runtime.turn_hook). Ignored once another engine took our place."""
        if self.ctx.engine is self:
            self._unsettled.add(workflow_id)
            ended = self._ended.get(workflow_id)
            if ended is not None:
                ended.set()  # whoever waits for this turn looks now, not at its next poll
            self.kick(workflow_id)

    def kick(self, workflow_id: str) -> None:
        if self._stopping:
            return
        task = self._tasks.get(workflow_id)
        if task is not None and not task.done():
            self._again.add(workflow_id)  # it will look once more before it ends
            return
        self._tasks[workflow_id] = asyncio.get_running_loop().create_task(self._drive(workflow_id))

    async def start(self) -> None:
        """At startup: pick up what a previous run left (queued jobs, jobs whose lease ran out)."""
        self._stopping = False
        await nodes.enter(self.ctx.db, self.node, self.lease, bool(getattr(self.rt, "shared_bus", False)))
        if self._beat is None or self._beat.done():
            self._beat = asyncio.get_running_loop().create_task(nodes.heartbeat(self))
        await orphan_turns(self)  # whatever ran in a process that is gone is not running now
        try:
            await orphan_approvals(self)  # and an approval nobody is parked on gets no answer through its agent
            await orphan_parks(self)  # nor does an agent that died after it was handed its answer
        except Exception:
            log.exception("could not reconcile the approvals")
        await self.sweep()

    async def stop(self) -> None:
        self._stopping = True
        tasks = list(self._tasks.values())
        if self._reconciling is not None:
            tasks.append(self._reconciling)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()
        await stop_provider_tasks()
        if self._beat is not None:
            self._beat.cancel()
            await asyncio.gather(self._beat, return_exceptions=True)
            self._beat = None
            try:
                await nodes.leave(self.ctx.db, self.node)  # a clean stop leaves nothing to wait for
            except Exception:
                log.exception("could not remove the mark of this process")

    async def sweep(self) -> None:
        """Called every couple of seconds: pick up work whose notification was lost, give back the jobs of
        a dead dispatcher, expire what stopped moving."""
        db = self.ctx.db
        await nodes.bury(self)  # first: the session locks of a dead process make its sessions look busy to all below
        async with db.engine.connect() as conn:
            queued = (await conn.execute(select(t.jobs.c.workflow_id).where(
                t.jobs.c.status == "queued").distinct())).scalars().all()
            held = (await conn.execute(select(t.jobs).where(t.jobs.c.status == "dispatched"))).mappings().all()
            busy = (await conn.execute(select(t.workflows.c.id).where(t.workflows.c.state.in_(BUSY)))).scalars().all()
        await orphan_turns(self)
        for wid in queued:
            if wid not in self._tasks:
                self.kick(wid)
        for job in held:  # a lease that ran out: the dispatcher died, here or with its whole process
            if (job["lease_until"] or 0) < now() and job["workflow_id"] not in self._tasks:
                await recover_job(self, job)
        has_job = {*queued, *(job["workflow_id"] for job in held)}  # their dispatcher settles when the job is over
        async with db.engine.connect() as conn:
            busy = [*busy, *await resume.needing_work(conn)]
        for wid in dict.fromkeys(busy):  # settle is idempotent; this is what saves a workflow whose settle failed or was lost
            if wid not in self._tasks and wid not in has_job:
                self._unsettled.add(wid)
                self.kick(wid)
        await expire(self)
        await apply_pending(self.ctx)  # provider events that wait: new, quarantined (an operation may match now), held
        if self._reconciling is None or self._reconciling.done():  # in the background: a slow partner must not hold the sweep
            self._reconciling = asyncio.get_running_loop().create_task(self._reconcile())

    async def _reconcile(self) -> None:
        try:
            await reconcile(self)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("operation reconcile failed")

    # ---- the dispatcher of one workflow -------------------------------------
    async def _drive(self, wid: str) -> None:
        me = asyncio.current_task()
        try:
            while True:
                self._again.discard(wid)
                if not await self._step(wid) and wid not in self._again:
                    break
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("workflow %s: the dispatcher stopped", wid)
        finally:
            if self._tasks.get(wid) is me:
                del self._tasks[wid]
                self._ended.pop(wid, None)

    async def _step(self, wid: str) -> bool:
        """Do one thing; True when something was done, so the dispatcher looks again."""
        if await resume.unpark(self, wid):  # a closed workflow leaves no session parked on an approval
            return True
        async with self.ctx.db.engine.connect() as conn:
            queued = (await conn.execute(select(t.jobs.c.id, t.jobs.c.kind).where(
                t.jobs.c.workflow_id == wid, t.jobs.c.status == "queued")
                .order_by(t.jobs.c.created_at, t.jobs.c.id))).all()
            parked = await resume.parked(conn, wid)
        # An agent parked on an approval takes nothing but its answer (a message sent to it is lost, P0), so the
        # answer goes first and everything else waits until the agent is awake.
        jid = next((j for j, kind in queued if kind == "approval_resume"), None)
        if jid is None and queued and not parked:
            jid = queued[0][0]
        if jid is not None:
            return await self._run_job(wid, jid)
        if wid in self._unsettled:
            return await self._settled(wid)
        return False

    async def _settled(self, wid: str) -> bool:
        """Settle, and keep the hint when it fails: a turn that ends meanwhile adds it again, so none is lost."""
        self._unsettled.discard(wid)
        try:
            return await self._settle(wid)
        except asyncio.CancelledError:
            raise
        except Exception:
            self._unsettled.add(wid)
            raise

    async def _settle(self, wid: str) -> bool:
        async with self.ctx.db.engine.connect() as conn:
            wf = (await conn.execute(select(t.workflows).where(t.workflows.c.id == wid))).mappings().one()
        leader = await leader_of(self.rt, wf["case_id"])
        if leader is None:
            return False
        await self._idle(leader, self.settings.wf_turn_timeout_seconds)
        what = await settle(self, wid)
        if what == "closed":
            await self._stop_leader(leader)
        return what == "nudge"

    # ---- one job ------------------------------------------------------------
    async def _run_job(self, wid: str, jid: str) -> bool:
        if await sandbox.elsewhere(self.rt, wid):  # an evaluation's workflow belongs to the process that runs it
            return False
        try:
            claimed = await self._claim(jid)
        except LockBusy:  # a reply or a close is in the middle of its transaction: look again in a moment, holding nothing
            await asyncio.sleep(POLL)
            return True
        if claimed is None:
            return False
        try:
            return await self._do_job(wid, jid, *claimed)
        except asyncio.CancelledError:
            # A stopped engine hands the job back at once, not after its lease, wherever the stop caught it: also in
            # the bookkeeping after the turn (a job that is done by then is not touched).
            await asyncio.shield(self._release(jid))
            raise

    async def _do_job(self, wid: str, jid: str, job: dict, wf: dict) -> bool:
        try:
            leader = await ensure_leader(self.rt, self.client, wf)
            if job["kind"] == "approval_resume":
                await resume.run(self, wid, job, leader)
            else:
                text = await BUILDERS[job["kind"]](self, job, wf)
                msg_id = job["id"] if job["attempts"] <= 1 else f"{job['id']}.{job['attempts']}"
                await self._deliver(wid, leader, text, msg_id, SENDER.get(job["kind"], "resident"))
                await self._await_end(wid, job, leader)
                await self._check_turn(wid, msg_id)
        except JobFailed as e:
            await self._failed(job, e)
            return True
        except LeaderUnavailable as e:
            await self._failed(job, JobFailed(str(e), retry=False))
            return True
        except Exception as e:
            log.exception("job %s failed", jid)
            await self._failed(job, JobFailed(repr(e)))
            return True
        for attempt in range(3):  # the turn is over and answered: only the bookkeeping is left, and it may hiccup
            try:
                async with self.ctx.db.engine.begin() as conn:
                    await lock_conversation(conn, wf["conversation_id"])
                    await finish_job(conn, jid, owner=self.node)  # (not ours any more: another process finished it)
                break
            except Exception:
                log.exception("job %s: could not mark it done (try %s)", jid, attempt + 1)
                await asyncio.sleep(0.1 * (attempt + 1))
        else:  # the next sweep finds the job with no lease, sees its ended turn and finishes it: no second send
            await self._release(jid)
            return True
        return await self._settled(wid)

    async def _release(self, jid: str) -> None:
        try:
            async with self.ctx.db.engine.begin() as conn:
                await conn.execute(update(t.jobs).where(
                    t.jobs.c.id == jid, t.jobs.c.status == "dispatched", t.jobs.c.lease_owner == self.node)
                    .values(lease_until=0))
        except Exception:
            log.exception("could not release job %s", jid)

    async def _failed(self, job: Any, why: JobFailed) -> None:
        """`_fail`, and if even that cannot be written the lease recovers the job later."""
        try:
            await self._fail(job, why)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("job %s: could not record its failure", job["id"])

    async def _claim(self, jid: str) -> tuple[dict, dict] | None:
        async with self.ctx.db.engine.begin() as conn:
            job = await claim_job(conn, jid, wait=False, owner=self.node, lease=self.lease)
            if job is None:
                return None
            job = dict(job)
            wf = dict((await conn.execute(select(t.workflows).where(
                t.workflows.c.id == job["workflow_id"]))).mappings().one())
            if wf["state"] != "closed" and wf["state"] not in BLOCKED:
                wf = await block_if_moved(conn, wf) or wf  # a suspended or replaced route lets nothing start by itself
            if wf["state"] == "closed" or wf["state"] in BLOCKED:  # nothing may run for it any more
                await finish_job(conn, jid, "failed")
                if job["request_id"]:
                    await settle_request(conn, job["request_id"])
                return None
            if job["request_id"]:
                await mark_running(conn, job["request_id"])
            waits = wf["state"] == "awaiting_approval" and await pending_count(conn, wf["id"])
            if wf["state"] != "active" and not waits:  # another approval still asks the resident: that is the state
                wf = await transition(conn, wf, "active")
            if job["kind"] in CYCLE_KINDS and "start_seq" not in job["payload"]:
                seq = (await conn.execute(select(t.conversations.c.last_sequence).where(
                    t.conversations.c.id == wf["conversation_id"]))).scalar_one()
                job["payload"] = {**job["payload"], "start_seq": seq}  # the chain of this job starts here
                await conn.execute(update(t.jobs).where(t.jobs.c.id == jid).values(payload=job["payload"]))
            return job, wf

    async def _fail(self, job: Any, why: JobFailed) -> None:
        """Give the job another attempt, or end it: the workflow needs attention and the request fails."""
        log.warning("job %s failed (attempt %s): %s", job["id"], job["attempts"], why)
        async with self.ctx.db.engine.begin() as conn:
            wf = (await conn.execute(select(t.workflows).where(t.workflows.c.id == job["workflow_id"]))).mappings().one()
            await lock_conversation(conn, wf["conversation_id"])
            wf = (await conn.execute(select(t.workflows).where(t.workflows.c.id == wf["id"]))).mappings().one()
            fresh = (await conn.execute(select(t.jobs.c.status, t.jobs.c.lease_owner).where(
                t.jobs.c.id == job["id"]))).first()
            if fresh is None or fresh[0] != "dispatched" or fresh[1] != job["lease_owner"]:
                return  # it ended, or another process holds it by now
            if why.retry and job["attempts"] < self.settings.wf_job_attempts and wf["state"] != "closed":
                await conn.execute(update(t.jobs).where(t.jobs.c.id == job["id"]).values(
                    status="queued", lease_owner=None, lease_until=None))
                return
            await finish_job(conn, job["id"], "failed")
            if wf["state"] != "closed" and wf["state"] not in BLOCKED:
                await transition(conn, wf, "needs_attention", reason="engine_error")
            if job["request_id"]:
                await settle_request(conn, job["request_id"], status="failed", error=fail_message("engine_error"))

    # ---- talking to the session ---------------------------------------------
    async def _locked(self, leader: Leader) -> bool:
        return await self.rt.bus.is_locked(MessageBusKeys.session_lock(leader.session_id))

    async def _idle(self, leader: Leader, timeout: float) -> bool:
        end, pace = time.monotonic() + timeout, Pace()
        while await self._locked(leader):
            if time.monotonic() > end:
                return False
            await asyncio.sleep(pace.next())
        return True

    async def _acked(self, wid: str, msg_id: str) -> bool:
        async with self.ctx.db.engine.connect() as conn:
            return (await conn.execute(select(t.turns.c.id).where(
                t.turns.c.workflow_id == wid, t.turns.c.msg_id == msg_id).limit(1))).first() is not None

    async def _deliver(self, wid: str, leader: Leader, text: str, msg_id: str, sender: str, *,
                       send=None, acked=None, ready=None) -> None:
        """Send until a turn carries `msg_id`. A 409 means the session is running and nothing was stored:
        wait for it to be idle and send again (not counted). A 200 that no turn follows is sent again too.
        `send` and `acked` replace the message and its acknowledgement for an event that wakes a parked agent.

        `ready`: asked before every send; False means "not now" (look again in a moment). A message is safe to send
        twice (while its run lives the second gets a 409, P0). An event that wakes a parked agent is not: it goes
        through a queue, a second copy is taken after the first, finds the agent no longer waiting and fails its run.
        Under load the acknowledgement of the first copy can take longer than AWP_WF_ACK_SECONDS, so such an event is
        only sent while its agent is parked (resume.wake): not while its session runs (the first copy is being taken,
        or the turn that asked is still ending) and not once it rests. An agent that stays "not parked" without the
        acknowledgement for `UNREADY` seconds is not going to take the event: the attempt fails."""
        s, sends, end = self.settings, 0, time.monotonic() + self.settings.wf_turn_timeout_seconds
        unready: float | None = None

        async def say() -> None:
            await self.client.say(leader.tenant, leader.agent_id, leader.session_id, text, name=sender, msg_id=msg_id)

        send, acked = send or say, acked or (lambda: self._acked(wid, msg_id))
        while True:
            if await acked():
                return
            if sends >= MAX_SENDS or time.monotonic() > end:
                raise JobFailed("the message was never taken by a turn")
            if ready is not None and not await ready():
                unready = unready or time.monotonic()
                if time.monotonic() - unready > max(UNREADY, 3 * s.wf_ack_seconds):
                    raise JobFailed("the agent is not waiting for this event")
                await asyncio.sleep(UNREADY_POLL)
                continue
            unready = None
            try:
                await send()
            except SessionBusy:
                await self._idle(leader, 30)
                continue
            sends += 1
            wait, pace = time.monotonic() + s.wf_ack_seconds, Pace()
            while time.monotonic() < wait:
                if await acked():
                    return
                await asyncio.sleep(pace.next())

    async def _await_end(self, wid: str, job: Any, leader: Leader, also: Leader | None = None) -> None:
        """Until the session is idle and no turn is running: the turns of the job, and any turn the
        leader's team started meanwhile, are over. `also` is a specialist session the job woke."""
        start = time.monotonic()  # (the job's lease is renewed by this process's heartbeat while this task lives)
        stopped, looked, pace = False, 0.0, Pace()
        ended = self._ended.setdefault(wid, asyncio.Event())  # set by on_turn: a turn of this workflow ended here
        while True:
            ended.clear()
            if not await self._locked(leader) and not (also is not None and await self._locked(also)):
                if not await self._running(wid):
                    return
                await orphan_turns(self, wid)  # a row 'running' under an idle session is a dead run's
            if not stopped and time.monotonic() - looked >= HALT_EVERY:
                looked = time.monotonic()
                if await self._halted(wid):  # closed or blocked while its turn runs: stop paying for it
                    stopped = True
                    await self._stop_leader(leader)
            if time.monotonic() - start > self.settings.wf_turn_timeout_seconds:
                await self._stop_leader(leader)
                raise JobFailed("the turn ran too long")
            # The end of a turn in this process is told (on_turn); the session's lock goes a moment later, so the
            # looks after it are quick again. A turn that runs in another process of the fleet is found by looking.
            try:
                await asyncio.wait_for(ended.wait(), pace.next())
                pace.reset()
            except asyncio.TimeoutError:
                pass

    async def _running(self, wid: str) -> bool:
        async with self.ctx.db.engine.connect() as conn:
            return (await conn.execute(select(t.turns.c.id).where(
                t.turns.c.workflow_id == wid, t.turns.c.status == "running",
                t.turns.c.started_at > now() - self.settings.wf_turn_timeout_seconds).limit(1))).first() is not None

    async def _halted(self, wid: str) -> bool:
        async with self.ctx.db.engine.connect() as conn:
            state = (await conn.execute(select(t.workflows.c.state).where(t.workflows.c.id == wid))).scalar()
        return state == "closed" or state in BLOCKED

    async def _check_turn(self, wid: str, msg_id: str) -> None:
        """The turn this attempt started: if it raised (the model failed) the attempt failed, unless the
        leader had already spoken: its words are out, and another attempt would say them again."""
        async with self.ctx.db.engine.connect() as conn:
            rows = (await conn.execute(select(t.turns.c.status, t.turns.c.started_at).where(
                t.turns.c.workflow_id == wid, t.turns.c.msg_id == msg_id))).all()
            failed = [at for status, at in rows if status == "error"]
            # A turn of this very message that ended well is the attempt's outcome. A second run under the same id
            # that failed is a second copy of the message or event that found its work already done: it proves nothing.
            if not failed or any(status in ("completed", "parked") for status, _ in rows):
                return
            spoke = (await conn.execute(select(t.messages.c.id).where(
                t.messages.c.workflow_id == wid, t.messages.c.sender == "assistant",
                t.messages.c.created_at >= min(failed)).limit(1))).first()
        if spoke is None:
            raise JobFailed("the turn ended with an error")
        log.warning("workflow %s: the turn failed after the leader spoke; what it said stands", wid)

    async def _stop_leader(self, leader: Leader) -> None:
        try:
            await self.client.interrupt(leader.tenant, leader.agent_id, leader.session_id)
        except Exception:
            log.exception("could not interrupt session %s", leader.session_id)
