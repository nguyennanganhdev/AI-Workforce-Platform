"""A scripted stand-in for the real engine (slice S3), used only by tests.

It takes the queued jobs the way the real engine will and writes its outcome through the
production functions (`add_assistant_message`, `transition`, `settle_request`), so the tests
exercise the real message, event, state and settle code. Only the "agent" is fake: what it
says and where the workflow ends up comes from a `Plan`.
"""
from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from typing import Callable

from sqlalchemy import select

from awp.workforce import tables as t
from awp.workforce.engine import claim_job, finish_job
from awp.workforce.events import lock_conversation
from awp.workforce.messages import add_assistant_message
from awp.workforce.settle import mark_running, settle_request
from awp.workforce.workflows import IllegalTransition, StateConflict, transition


HOLD_CEILING = 40  # seconds a held turn waits for its gate


@dataclass
class Plan:
    say: tuple[str, ...] = ("Noted.",)
    state: str = "awaiting_user"
    reason: str | None = None
    delay: float = 0.0  # seconds between taking the job and finishing the turn
    hold: "threading.Event | None" = None  # the turn does not finish until the test sets this (a gate, not a clock)
    fail: dict | None = None  # settle the request as failed with this public error
    emit_after: tuple = ()
    start_active: bool = True  # accepted -> active, as the real engine does when a turn begins


@dataclass
class TestEngine:
    __test__ = False
    ctx: object
    plan: "Plan | Callable[[str], Plan]" = field(default_factory=Plan)
    seen: list[tuple[str, str]] = field(default_factory=list)  # (job id, resident text)
    errors: list[Exception] = field(default_factory=list)
    paused: bool = False  # while set, notified jobs stay queued
    _locks: dict = field(default_factory=dict)
    _tasks: set = field(default_factory=set)

    def notify(self, workflow_id: str, job_id: str) -> None:
        if self.paused:
            return
        task = asyncio.get_running_loop().create_task(self.run(workflow_id, job_id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def run(self, workflow_id: str, job_id: str) -> None:
        lock = self._locks.setdefault(workflow_id, asyncio.Lock())
        async with lock:  # one turn at a time per workflow
            try:
                await self._turn(job_id)
            except (IllegalTransition, StateConflict) as e:  # e.g. the workflow was closed meanwhile
                self.errors.append(e)
                async with self.ctx.db.engine.begin() as conn:
                    await finish_job(conn, job_id, "failed")

    async def _turn(self, job_id: str) -> None:
        db = self.ctx.db
        async with db.engine.begin() as conn:
            job = await claim_job(conn, job_id)
            if job is None:
                return
            await mark_running(conn, job["request_id"])
            text = (await conn.execute(select(t.messages.c.text).where(
                t.messages.c.id == job["payload"]["message_id"]))).scalar_one()
            wf = (await conn.execute(select(t.workflows).where(t.workflows.c.id == job["workflow_id"]))).mappings().one()
            conv_id = wf["conversation_id"]
            plan = self.plan(text) if callable(self.plan) else self.plan
            self.seen.append((job_id, text))
            if plan.start_active and wf["state"] == "accepted":
                await transition(conn, wf, "active")
        if plan.delay:
            await asyncio.sleep(plan.delay)
        if plan.hold is not None:
            for _ in range(HOLD_CEILING * 100):  # a test that forgets to open the gate fails instead of hanging
                if plan.hold.is_set():
                    break
                await asyncio.sleep(0.01)
        async with db.engine.begin() as conn:
            await lock_conversation(conn, conv_id)  # first lock of every writer; then read the workflow
            wf = (await conn.execute(select(t.workflows).where(t.workflows.c.id == job["workflow_id"]))).mappings().one()
            for line in plan.say:
                await add_assistant_message(conn, wf, line, job["request_id"])
            await transition(conn, wf, plan.state, reason=plan.reason, emit_after=plan.emit_after)
            if plan.fail:
                await settle_request(conn, job["request_id"], status="failed", error=plan.fail)
            else:
                await settle_request(conn, job["request_id"])
            await finish_job(conn, job["id"])
