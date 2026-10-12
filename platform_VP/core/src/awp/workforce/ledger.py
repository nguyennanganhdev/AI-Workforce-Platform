"""The operation ledger: one `wf_operations` row per action a partner tool took (spec 8, P0 items 21-24).

The row is written BEFORE the call (status intent), with a client_reference derived from (workflow, tool,
arguments) alone. That key is what keeps an action from happening twice:

  * the same call again while the row is not finished, or after it finished, returns what the row says and
    does not call the partner;
  * a crash leaves the row, so a restarted process finds it instead of making a second one (the tool call
    id is not stable across a crash, so it is not part of the key);
  * a deliberate repeat is a different request: it differs in an argument, or carries an `idempotency_nonce`.

Every write takes the conversation's lock first (events.lock_conversation), like every other writer of a workflow.
The first action of a workflow also gives it its platform ticket (spec A5), in the same transaction.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Any, NamedTuple

from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError

from ..assets import stable
from . import tables as t
from .approvals import args_hash
from .common import now
from .events import emit, lock_conversation
from .partner_result import FAILED, OK, PENDING, UNKNOWN, PartnerResult
from .routecheck import block_if_moved
from .tables import new_id
from .workflows import BLOCKED, bump

log = logging.getLogger("awp.workforce")

NONCE = "idempotency_nonce"  # an argument the platform adds to an action so that a repeat can be deliberate
TERMINAL = ("completed", "failed")
STATUS_OF = {OK: "completed", PENDING: "pending", FAILED: "failed", UNKNOWN: "unknown"}
MAX_STORED_TEXT = 4000

# Operations with a live call in this process: the sweep must not mistake them for a crash's leftovers.
# Answers the partner gave that the database would not take (it was down): the sweep writes them when it can.
# Both live in the memory of the process that made the call, and the row names that process (`node`): the sweep of
# another process leaves the row alone for as long as that process lives (reconcile.one), so a live call is never taken
# for a leftover and an answer in hand is written by the process that has it. When that process dies, so does the
# answer: nobody knows what became of the request, which is what the other processes then find out the honest way.
INFLIGHT: set[str] = set()
HELD: dict[str, PartnerResult] = {}
_WRITES: set[asyncio.Task] = set()  # keeps a write that outlives its caller from being collected


class Begun(NamedTuple):
    op: Any  # the row (None when refused)
    fresh: bool  # True: the caller must make the call; False: the row is what to answer with
    refused: str | None = None


def reference_of(workflow_id: str, tool: str, ahash: str) -> str:
    return "cr_" + hashlib.sha256(f"{workflow_id}|{tool}|{ahash}".encode()).hexdigest()[:32]


def hash_of(arguments: dict) -> str:
    """A signed link to an image (CaseAssetLink) counts as the object it points at: the same request made again after a
    crash carries a link signed at another second, and must still be found to be the same request."""
    return args_hash(stable(arguments))


def stored(res: PartnerResult) -> dict:
    return {"outcome": res.outcome, "status": res.status, "error": res.error, "sent": res.sent,
            "text": res.text[:MAX_STORED_TEXT]}


async def _workflow(conn, workflow_id: str):
    return (await conn.execute(select(t.workflows).where(t.workflows.c.id == workflow_id))).mappings().one()


async def locked(conn, workflow_id: str):
    """The workflow row read under the conversation's lock."""
    conv = (await conn.execute(select(t.workflows.c.conversation_id).where(t.workflows.c.id == workflow_id))).scalar_one()
    await lock_conversation(conn, conv)
    return await _workflow(conn, workflow_id)


async def begin(db, workflow_id: str, route_id: str, tool: str, model_args: dict) -> Begun:
    """Insert the intent row, or find the one that already stands for this call (one transaction)."""
    ahash = hash_of(model_args)
    ref = reference_of(workflow_id, tool, ahash)
    async with db.engine.begin() as conn:
        wf = await locked(conn, workflow_id)
        if wf["state"] == "closed" or wf["state"] in BLOCKED or await block_if_moved(conn, wf) is not None:
            return Begun(None, False, "The workflow is closed or blocked. Nothing was sent; stop working on it.")
        found = (await conn.execute(select(t.operations).where(
            t.operations.c.workflow_id == workflow_id, t.operations.c.tool_name == tool,
            t.operations.c.args_hash == ahash))).mappings().first()
        if found is not None:
            if found["status"] == "failed" and (found["result"] or {}).get("sent") is False:
                # It provably never reached the partner (it could not connect, or was refused at the door):
                # trying again is not a second effect.
                await conn.execute(update(t.operations).where(
                    t.operations.c.id == found["id"], t.operations.c.status == "failed")
                    .values(status="intent", updated_at=now()))
                found = (await conn.execute(select(t.operations).where(t.operations.c.id == found["id"]))).mappings().one()
                return Begun(found, True)
            return Begun(found, False)
        if NONCE not in model_args:  # "do not retry" holds for a reworded request too, not only for the identical one
            lost = (await conn.execute(select(t.operations.c.result).where(
                t.operations.c.workflow_id == workflow_id, t.operations.c.tool_name == tool,
                t.operations.c.status == "unknown"))).scalars().all()
            if any(not (r or {}).get("reviewed") for r in lost):
                return Begun(None, False, "Not sent: an earlier request with this tool has an outcome nobody knows yet, "
                                          "and this one may repeat it. Do not send another; a person will settle it.")
        stamp = now()
        integration = (await conn.execute(select(t.tools.c.integration_id).where(  # whose events will follow it (T2)
            t.tools.c.route_id == route_id, t.tools.c.name == tool))).scalar()
        row = dict(id=new_id("op"), workflow_id=workflow_id, route_id=route_id, tool_name=tool, args_hash=ahash,
                   client_reference=ref, status="intent", arguments=model_args, created_at=stamp, updated_at=stamp,
                   integration_id=integration)
        try:
            async with conn.begin_nested():
                await conn.execute(insert(t.operations).values(**row))
        except IntegrityError:  # cannot happen under the lock; if it does, the winner's row is the answer
            found = (await conn.execute(select(t.operations).where(
                t.operations.c.client_reference == ref))).mappings().first()
            return Begun(found, False)
        if wf["ticket_id"] is None:  # the first action of the workflow makes its ticket (A5)
            ticket = new_id("tkt")
            await conn.execute(update(t.workflows).where(t.workflows.c.id == workflow_id).values(ticket_id=ticket))
            await emit(conn, wf["conversation_id"], "ticket.created", {"ticket_id": ticket, "status": "open"},
                       workflow={**dict(wf), "ticket_id": ticket})
        return Begun({**row, "result": None, "external_job_id": None, "normalized_status": None}, True)


async def mark_sent(db, op_id: str, node: str | None = None) -> bool:
    """intent -> sent, just before the call leaves, by the process `node`. False when the row is not an intent any more."""
    async with db.engine.begin() as conn:
        done = await conn.execute(update(t.operations).where(
            t.operations.c.id == op_id, t.operations.c.status == "intent")
            .values(status="sent", node=node, updated_at=now()))
    return done.rowcount == 1


async def touch(db, op_id: str, status: str, expect: tuple[str, ...], *, before: float | None = None,
                node: str | None = None) -> bool:
    """Take an operation for a retry or a status query: set `status` and the clock, only from `expect`, and only while
    its workflow is open and its route active (stop tracking calls nothing at the partner, a suspended route does
    nothing by itself). The check is part of the claim, so a close that lands between two rows of one pass stops the
    second. `before`: only a row nobody touched since then, so of two processes that saw the same row one takes it.
    `node` becomes the process that holds it."""
    live = select(t.workflows.c.id).select_from(t.workflows.join(t.routes, t.routes.c.id == t.workflows.c.route_id)).where(
        t.workflows.c.state.notin_(("closed", *BLOCKED)), t.routes.c.status == "active")
    where = [t.operations.c.id == op_id, t.operations.c.status.in_(expect), t.operations.c.workflow_id.in_(live)]
    if before is not None:
        where.append(t.operations.c.updated_at < before)
    values = {"status": status, "updated_at": now(), **({"node": node} if node else {})}
    async with db.engine.begin() as conn:
        done = await conn.execute(update(t.operations).where(*where).values(**values))
    return done.rowcount == 1


async def keep(db, op_id: str, res: PartnerResult, *, expect: tuple[str, ...] | None = None) -> Any:
    """`finish`, for an answer in hand that must not be lost: a failed write is tried twice more, and an answer the
    database would not take is held in memory for the sweep (a process that dies first knows nothing, which is the
    honest `unknown`). Returns the row, or None when it could not be written."""
    for attempt in range(3):
        try:
            row = await finish(db, op_id, res, expect=expect)
            HELD.pop(op_id, None)
            return row
        except Exception:
            log.exception("could not record the result of operation %s (try %s)", op_id, attempt + 1)
            await asyncio.sleep(0.2)
    HELD[op_id] = res
    return None


async def record(db, op_id: str, res: PartnerResult, wait: float, *, expect: tuple[str, ...] | None = None) -> Any:
    """Write an answer in hand, waiting at most `wait` seconds for it. The write itself is not cancelled by a
    deadline or by the cancellation of the caller: it goes on in the background. Returns the row if it got there in time."""
    task = asyncio.ensure_future(keep(db, op_id, res, expect=expect))
    _WRITES.add(task)
    task.add_done_callback(_WRITES.discard)
    try:
        return await asyncio.wait_for(asyncio.shield(task), wait)
    except TimeoutError:
        return None


async def finish(db, op_id: str, res: PartnerResult, *, wake: bool = False,
                 expect: tuple[str, ...] | None = None) -> Any:
    """Write what became of an operation. A finished one (completed, failed) never changes, and with `expect`
    only an operation in one of those statuses does (a late timeout must not undo an answer that got in first).
    A change of status is a public event and a new revision of the workflow, unless the workflow is closed;
    `wake` also tells the leader (the sweep found the news, no turn of the leader is running to read it)."""
    status = STATUS_OF[res.outcome]
    async with db.engine.begin() as conn:
        wid = (await conn.execute(select(t.operations.c.workflow_id).where(t.operations.c.id == op_id))).scalar_one()
        wf = await locked(conn, wid)
        op = (await conn.execute(select(t.operations).where(t.operations.c.id == op_id))).mappings().one()
        if op["status"] in TERMINAL or (expect is not None and op["status"] not in expect):
            return op
        normalized = res.status or op["normalized_status"]
        job = res.external_job_id or op["external_job_id"]
        if op["last_rank"] is not None and status in ("pending", "unknown"):
            # A provider event got here first (the early event): it knows more than a reply that only says
            # "accepted" or that was lost, so the answer adds the job id and the text, never a step back.
            status, normalized, job = op["status"], op["normalized_status"], op["external_job_id"] or res.external_job_id
        changed = status != op["status"]
        await conn.execute(update(t.operations).where(t.operations.c.id == op_id).values(
            status=status, updated_at=now(), result=stored(res), normalized_status=normalized, external_job_id=job))
        op = (await conn.execute(select(t.operations).where(t.operations.c.id == op_id))).mappings().one()
        if wf["state"] == "closed" or wf["state"] in BLOCKED:
            return op
        if changed and status != "intent":
            payload = {"operation_id": op_id, "status": status, "tool": op["tool_name"],
                       "client_reference": op["client_reference"]}
            if op["external_job_id"]:
                payload["external_job_id"] = op["external_job_id"]
            await emit(conn, wf["conversation_id"], "operation.status_changed", payload, workflow=await bump(conn, wf))
        if wake and status in TERMINAL:
            await conn.execute(insert(t.jobs).values(
                id=new_id("job"), workflow_id=wid, kind="provider_wake", request_id=None, status="queued",
                payload={"operation_id": op_id, "status": status, "text": res.text[:MAX_STORED_TEXT],
                         "external_job_id": op["external_job_id"]}, attempts=0, created_at=now()))
        return op
