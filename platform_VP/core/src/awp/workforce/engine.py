"""The seam between the request service and whatever runs the agents.

The service writes a `wf_jobs` row (kind resident_message) and tells the engine after the
commit. The engine takes the job, runs the turn, and writes its outcome through the shared
functions: `messages.add_assistant_message`, `workflows.transition` and `settle.settle_request`,
all in one transaction. Slice S3 supplies the real engine; tests supply a scripted one.
Until an engine is attached, jobs wait in the table and the POST answers 202.

Lock order: every engine transaction starts with `claim_job` or `events.lock_conversation`, so it
takes the conversation's write lock before any other row, as the command service and close do.
"""
from __future__ import annotations

from typing import Any, Protocol

from sqlalchemy import exists, select, update
from sqlalchemy.exc import IntegrityError

from . import tables as t
from .common import now
from .events import lock_conversation


class LockBusy(Exception):
    """The conversation is locked by another transaction and the caller chose not to wait (`claim_job(wait=False)`)."""


class Engine(Protocol):
    """What the service needs of an engine: `notify`. The real engine (runner.WorkflowEngine) also has
    `start`, `sweep` and `stop`, which the app's lifespan calls when they exist."""

    def notify(self, workflow_id: str, job_id: str) -> None:
        """A job was queued and committed. Must return at once and must not raise."""


class NullEngine:
    def notify(self, workflow_id: str, job_id: str) -> None:
        return None


async def claim_job(conn, job_id: str, *, wait: bool = True, owner: str | None = None, lease: float = 60.0) -> Any:
    """Queued -> dispatched, once. None when someone else took it, it was cancelled, or another job
    of the same workflow is still dispatched (the turn after it picks this one up).

    It is the first call of an engine transaction, so it takes the conversation's write lock
    (events.lock_conversation): every transaction of a turn then locks in the order the command
    service and close use. Whatever the engine does later in that transaction comes after it.

    `wait=False` (PostgreSQL: SKIP LOCKED on the conversation row) raises LockBusy instead of queueing behind a
    transaction that holds the conversation: the dispatcher tries again in a moment, with no connection held meanwhile.

    `owner` is the process that takes the job and `lease` how long the claim stands unless that process renews it
    (nodes.beat): a job whose lease ran out belongs to a process that died, and the sweep of any other gives it back.
    """
    sibling = t.jobs.alias("sibling")
    conv = (await conn.execute(select(t.workflows.c.conversation_id).select_from(
        t.jobs.join(t.workflows, t.workflows.c.id == t.jobs.c.workflow_id))
        .where(t.jobs.c.id == job_id))).scalar()
    if conv is None:
        return None
    if not await lock_conversation(conn, conv, wait=wait):
        raise LockBusy(conv)
    busy = exists().where(sibling.c.workflow_id == t.jobs.c.workflow_id, sibling.c.status == "dispatched")
    try:
        async with conn.begin_nested():  # a lost race on the unique index must not poison the transaction
            done = await conn.execute(
                update(t.jobs).where(t.jobs.c.id == job_id, t.jobs.c.status == "queued", ~busy)
                .values(status="dispatched", attempts=t.jobs.c.attempts + 1, lease_owner=owner, lease_until=now() + lease))
    except IntegrityError:
        return None
    if done.rowcount != 1:
        return None
    return (await conn.execute(select(t.jobs).where(t.jobs.c.id == job_id))).mappings().one()


async def finish_job(conn, job_id: str, status: str = "done", *, owner: str | None = None) -> bool:
    """With `owner`: only the job that process still holds (one that was taken from it after its lease ran out is
    somebody else's by now). False when nothing was written."""
    where = [t.jobs.c.id == job_id]
    if owner is not None:
        where += [t.jobs.c.status == "dispatched", t.jobs.c.lease_owner == owner]
    done = await conn.execute(update(t.jobs).where(*where).values(status=status, lease_owner=None, lease_until=None))
    return done.rowcount == 1
