"""POST /partner/workflows/{id}/close (contract 9.9): the only way a resident's confirmation ends a workflow.

State, revision, the workflow.closed event, the case and the stored result commit together.
The idempotency claim is the request row written in the same transaction, so a refused close
(wrong revision, not ready) leaves nothing behind and the caller may try again with the same id.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import random
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, insert, select, update
from sqlalchemy.exc import DBAPIError

from . import binding, tables as t
from .auth import authenticate, need, route_denied
from .common import iso, now
from .errors import WorkforceError, json_object, validated
from .reads import not_found
from .events import emit, last_event_id, lock_conversation
from .onboarding import revision_conflict
from .schemas import STOP_TRACKING, CloseIn
from .settle import PENDING, settle_request
from .tables import new_id
from .workflows import StateConflict, next_action, retryable, transition

ATTEMPTS = 5
OPEN_OPERATION = ("intent", "sent", "pending", "unknown")  # not completed and not failed


def fingerprint(workflow_id: str, b: CloseIn) -> str:
    meaning = {"command_type": "close_workflow", "workflow": workflow_id, "user": b.external_user_id,
               "ticket": b.external_ticket_id, "conversation": b.external_conversation_id,
               "expected_revision": b.expected_revision, "reason": b.reason,
               "stop_tracking_only": b.stop_tracking_only}
    raw = json.dumps(meaning, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


def not_ready(open_operations: int) -> WorkforceError:
    return WorkforceError("WORKFLOW_NOT_READY_TO_CLOSE", 409,
                          "An outside operation is still running; stop tracking it explicitly to close.",
                          {"open_operations": open_operations})


async def _close(ctx, conn, p, workflow_id: str, b: CloseIn, fp: str) -> dict | WorkforceError:
    client = p.client.id
    wf = (await conn.execute(select(t.workflows).where(
        t.workflows.c.id == workflow_id, t.workflows.c.client_id == client))).mappings().first()
    if wf is None:  # unknown, or another client's: the same 404 either way (contract 6.3)
        return not_found()
    if not p.covers(wf["route_id"]):
        return route_denied()
    prior = await _prior(conn, client, b)
    if prior is not None:  # before the revision check, so a retry of a close that worked is not a conflict
        if prior["fingerprint"] != fp:
            return WorkforceError("IDEMPOTENCY_CONFLICT", 409,
                                  "This external_request_id was used with a different request.")
        return prior["response"]["body"]

    refused = await _apply(ctx, conn, p, wf, b, fp)
    if isinstance(refused, WorkforceError):
        # A twin of this request may have closed the workflow after the lookup above: its result
        # wins, and an id reused with another body is a conflict, not whatever the stale view said.
        prior = await _prior(conn, client, b)
        if prior is not None:
            if prior["fingerprint"] != fp:
                return WorkforceError("IDEMPOTENCY_CONFLICT", 409,
                                      "This external_request_id was used with a different request.")
            return prior["response"]["body"]
    return refused


async def _prior(conn, client: str, b: CloseIn):
    return (await conn.execute(select(t.requests).where(
        t.requests.c.client_id == client, t.requests.c.external_request_id == b.external_request_id))
        ).mappings().first()


async def shut(rt, conn, wf: Any, reason: str) -> dict:
    """Close `wf` and everything that hangs on it, in the caller's transaction (which already holds
    the conversation's write lock and read `wf` under it): the state, the case, the jobs still queued,
    the approvals still pending and the requests still waiting. Used by POST close and by the engine's
    auto-close of a read-only answer."""
    stamp, workflow_id = now(), wf["id"]
    pending = (await conn.execute(select(t.approvals.c.id).where(
        t.approvals.c.workflow_id == workflow_id, t.approvals.c.status == "pending"))).scalars().all()
    for appr in pending:  # before the close: a client that stops reading at workflow.closed has seen them end
        await conn.execute(update(t.approvals).where(t.approvals.c.id == appr).values(
            status="cancelled", decided_at=stamp))
        await emit(conn, wf["conversation_id"], "approval.resolved",
                   {"approval_id": appr, "status": "cancelled"}, workflow=wf)
    closed = await transition(conn, wf, "closed", reason=reason)
    if wf["case_id"]:
        await rt.cases.update_case(wf["case_id"], conn=conn, status="closed",
                                   result={"closed_by": "workflow", "reason": reason})
    # What was still waiting on this workflow ends with it: no turn will run for a closed one.
    await conn.execute(update(t.jobs).where(t.jobs.c.workflow_id == workflow_id, t.jobs.c.status == "queued")
                       .values(status="failed"))
    waiting = (await conn.execute(select(t.requests.c.id).where(
        t.requests.c.workflow_id == workflow_id, t.requests.c.status.in_(PENDING)))).scalars().all()
    for other in waiting:
        await settle_request(conn, other)
    return closed


async def _apply(ctx, conn, p, wf: Any, b: CloseIn, fp: str) -> dict | WorkforceError:
    workflow_id, client = wf["id"], p.client.id
    conv = (await conn.execute(select(t.conversations).where(
        t.conversations.c.id == wf["conversation_id"]))).mappings().one()
    route = (await conn.execute(select(t.routes).where(t.routes.c.id == wf["route_id"]))).mappings().one()
    if binding.needs_ticket(route) and not b.external_ticket_id:
        return binding.ticket_required()
    if (wf["external_user_id"] != b.external_user_id or wf["external_ticket_id"] != b.external_ticket_id
            or conv["external_conversation_id"] != b.external_conversation_id):
        return binding.mismatch()
    await lock_conversation(conn, conv["id"])  # first lock, as for every writer; then read the workflow
    wf = (await conn.execute(select(t.workflows).where(t.workflows.c.id == workflow_id))).mappings().one()
    if wf["state"] == "closed":
        return binding.closed()
    if b.expected_revision != wf["revision"]:
        return revision_conflict(wf["revision"])
    open_ops = (await conn.execute(select(func.count()).select_from(t.operations).where(
        t.operations.c.workflow_id == workflow_id, t.operations.c.status.in_(OPEN_OPERATION)))).scalar_one()
    if open_ops and not (b.stop_tracking_only and b.reason == STOP_TRACKING):
        return not_ready(open_ops)

    rid, stamp = new_id("req"), now()
    await conn.execute(insert(t.requests).values(  # the claim: a parallel twin meets this unique key
        id=rid, client_id=client, external_request_id=b.external_request_id,
        command_type="close_workflow", fingerprint=fp, route_id=wf["route_id"],
        conversation_id=conv["id"], workflow_id=workflow_id, status="completed", accepted_at=stamp,
        completed_at=stamp))
    closed = await shut(ctx.rt, conn, wf, b.reason)
    body = {"request_id": rid, "request_status": "completed", "external_ticket_id": wf["external_ticket_id"],
            "conversation_id": conv["id"], "workflow_id": workflow_id, "ticket_id": wf["ticket_id"],
            "state": "closed", "next_action": next_action("closed"), "revision": closed["revision"],
            "reason": b.reason, "closed_at": iso(closed["closed_at"])}
    await conn.execute(update(t.requests).where(t.requests.c.id == rid).values(
        response={"body": body, "last_event_id": await last_event_id(conn, conv["id"])}))
    return body


def build_close(r: APIRouter, ctx: Any) -> None:
    @r.post("/partner/workflows/{workflow_id}/close")
    async def close(workflow_id: str, request: Request):
        p = await authenticate(request, "customer", "close_workflow")
        b = validated(await json_object(request), CloseIn)
        fp = fingerprint(workflow_id, b)
        for attempt in range(ATTEMPTS):
            try:
                async with ctx.db.engine.begin() as conn:
                    result = await _close(ctx, conn, p, workflow_id, b, fp)
                break
            except (DBAPIError, StateConflict) as e:
                if not retryable(e):
                    raise
                await asyncio.sleep(0.005 * (attempt + 1) + random.random() * 0.01)
        else:
            raise WorkforceError("INTERNAL_ERROR", 503, "The close could not be recorded; retry it.",
                                 retryable=True)
        if isinstance(result, WorkforceError):
            raise result
        kick = getattr(ctx.engine, "kick", None)  # an agent parked on an approval the close cancelled is woken to end
        if kick is not None:
            kick(result["workflow_id"])
        return JSONResponse(result, status_code=200)
