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
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from agentscope.app.message_bus import MessageBusKeys
from sqlalchemy import select, update

from ..agentscope_client import AgentScopeClient, SessionBusy
from . import resume, tables as t
from .approvals import pending_count
from .common import now
from .engine import LockBusy, claim_job, finish_job
from .events import lock_conversation
from .expiry import expire
from .jobs import BUILDERS, CYCLE_KINDS, SENDER
from .leader import Leader, LeaderUnavailable, ensure_leader, leader_of
from .provider_sweep import apply_pending, stop as stop_provider_tasks
from .reconcile import reconcile
from .recover import answered, orphan_approvals, orphan_turns
from .routecheck import block_if_moved
from .settle import fail_message, mark_running, settle_request
from .settling import settle
from .workflows import BLOCKED, BUSY, transition

log = logging.getLogger("awp.workforce")

MAX_SENDS = 4  # the same message is sent this many times before the job fails
LEASE = 60.0
POLL = 0.03


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
        self._stopping = False
        self._reconciling: asyncio.Task | None = None

    # ---- how work arrives -------------------------------------------------
    def notify(self, workflow_id: str, job_id: str) -> None:
        self.kick(workflow_id)

    def on_turn(self, workflow_id: str) -> None:
        """A turn of a leader ended (Runtime.turn_hook). Ignored once another engine took our place."""
        if self.ctx.engine is self:
            self._unsettled.add(workflow_id)
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
        await orphan_turns(self)  # whatever ran in the previous process is not running now
        try:
            await orphan_approvals(self)  # and an approval nobody is parked on gets no answer through its agent
        except Exception:
            log.exception("could not reconcile the pending approvals")
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

    async def sweep(self) -> None:
        """Called every couple of seconds: pick up work whose notification was lost, give back the jobs of
        a dead dispatcher, expire what stopped moving."""
        db = self.ctx.db
        async with db.engine.connect() as conn:
            queued = (await conn.execute(select(t.jobs.c.workflow_id).where(
                t.jobs.c.status == "queued").distinct())).scalars().all()
            stale = (await conn.execute(select(t.jobs).where(
                t.jobs.c.status == "dispatched", t.jobs.c.lease_until < now()))).mappings().all()
            busy = (await conn.execute(select(t.workflows.c.id).where(t.workflows.c.state.in_(BUSY)))).scalars().all()
        for wid in queued:
            if wid not in self._tasks:
                self.kick(wid)
        for job in stale:
            if job["workflow_id"] not in self._tasks:  # nobody here is working on it
                await self._recover(job)
        await orphan_turns(self)
        has_job = {*queued, *(job["workflow_id"] for job in stale)}  # their dispatcher settles when the job is over
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

    async def _recover(self, job: Any) -> None:
        """A dispatched job whose dispatcher is gone: done when its turn ended well, else another attempt."""
        try:
            if await answered(self, job):
                async with self.ctx.db.engine.begin() as conn:
                    conv = (await conn.execute(select(t.workflows.c.conversation_id).where(
                        t.workflows.c.id == job["workflow_id"]))).scalar_one()
                    if not await lock_conversation(conn, conv, wait=False):
                        return  # in use: the next sweep finds the job again
                    await finish_job(conn, job["id"])
                self._unsettled.add(job["workflow_id"])
                self.kick(job["workflow_id"])
            else:
                await self._fail(job, JobFailed("the dispatcher is gone"))
        except Exception:
            log.exception("could not recover job %s", job["id"])

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
                    await finish_job(conn, jid)
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
                await conn.execute(update(t.jobs).where(t.jobs.c.id == jid, t.jobs.c.status == "dispatched")
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
            job = await claim_job(conn, jid, wait=False)
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
            fresh = (await conn.execute(select(t.jobs.c.status).where(t.jobs.c.id == job["id"]))).scalar()
            if fresh != "dispatched":
                return
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
        end = time.monotonic() + timeout
        while await self._locked(leader):
            if time.monotonic() > end:
                return False
            await asyncio.sleep(POLL)
        return True

    async def _acked(self, wid: str, msg_id: str) -> bool:
        async with self.ctx.db.engine.connect() as conn:
            return (await conn.execute(select(t.turns.c.id).where(
                t.turns.c.workflow_id == wid, t.turns.c.msg_id == msg_id).limit(1))).first() is not None

    async def _deliver(self, wid: str, leader: Leader, text: str, msg_id: str, sender: str, *,
                       send=None, acked=None) -> None:
        """Send until a turn carries `msg_id`. A 409 means the session is running and nothing was stored:
        wait for it to be idle and send again (not counted). A 200 that no turn follows is sent again too.
        `send` and `acked` replace the message and its acknowledgement for an event that wakes a parked agent."""
        s, sends, end = self.settings, 0, time.monotonic() + self.settings.wf_turn_timeout_seconds

        async def say() -> None:
            await self.client.say(leader.tenant, leader.agent_id, leader.session_id, text, name=sender, msg_id=msg_id)

        send, acked = send or say, acked or (lambda: self._acked(wid, msg_id))
        while True:
            if await acked():
                return
            if sends >= MAX_SENDS or time.monotonic() > end:
                raise JobFailed("the message was never taken by a turn")
            try:
                await send()
            except SessionBusy:
                await self._idle(leader, 30)
                continue
            sends += 1
            wait = time.monotonic() + s.wf_ack_seconds
            while time.monotonic() < wait:
                if await acked():
                    return
                await asyncio.sleep(POLL)

    async def _await_end(self, wid: str, job: Any, leader: Leader, also: Leader | None = None) -> None:
        """Until the session is idle and no turn is running: the turns of the job, and any turn the
        leader's team started meanwhile, are over. `also` is a specialist session the job woke."""
        start = last_lease = time.monotonic()
        stopped = False
        while True:
            if not await self._locked(leader) and not (also is not None and await self._locked(also)):
                if not await self._running(wid):
                    return
                await orphan_turns(self, wid)  # a row 'running' under an idle session is a dead run's
            if not stopped and await self._halted(wid):  # closed or blocked while its turn runs: stop paying for it
                stopped = True
                await self._stop_leader(leader)
            if time.monotonic() - start > self.settings.wf_turn_timeout_seconds:
                await self._stop_leader(leader)
                raise JobFailed("the turn ran too long")
            if time.monotonic() - last_lease > LEASE / 3:
                last_lease = time.monotonic()
                async with self.ctx.db.engine.begin() as conn:
                    await conn.execute(update(t.jobs).where(t.jobs.c.id == job["id"]).values(lease_until=now() + LEASE))
            await asyncio.sleep(POLL)

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
            if not failed:
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
