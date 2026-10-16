"""POST /partner/approvals/{approval_id}/decision (contract 9.8): the resident's consent, or refusal.

The answer is 202: the decision is recorded and the agent that asked is woken later (job approval_resume), so
the result of the work it then does reaches the partner as events, history and `GET request`, attributed to
the request this call created. In ONE transaction: the request row (the idempotency claim, shared with
requests and close), the approval row, `approval.resolved`, the workflow (active again, revision+1) and the
job. The event that wakes the agent is built later from the stored row; nothing in the body but the checks
is used.

Checks, in this order (a refusal leaves nothing behind, so the same request id can be sent again):
  credential/operation -> schema 422 -> approval in the caller's client 404 -> key covers the route 403 ->
  idempotency (the stored 202, or 409 IDEMPOTENCY_CONFLICT) -> audience 403 -> user/ticket/conversation/workflow
  binding 409 WORKFLOW_BINDING_MISMATCH -> route suspended/replaced 403 ROUTE_NOT_AUTHORIZED (the workflow is blocked,
  as for a reply) -> (under the conversation's lock) workflow closed 409 WORKFLOW_CLOSED ->
  approval no longer pending 409 APPROVAL_NOT_PENDING -> past expires_at 409 APPROVAL_EXPIRED ->
  409 ARGUMENTS_HASH_MISMATCH -> 409 QUOTE_MISMATCH -> 409 REVISION_CONFLICT.
The hash and the quote are checked before the revision: they say the partner shows something other than what
the resident was asked, which a fresh snapshot does not cure.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import random
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import insert, select
from sqlalchemy.exc import DBAPIError

from . import binding, tables as t
from .approvals import resolve
from .auth import authenticate, route_denied
from .commands import _block
from .common import iso, now
from .errors import WorkforceError, json_object, validated
from .events import lock_conversation
from .onboarding import revision_conflict
from .reads import not_found
from .schemas import DecisionIn
from .tables import new_id
from .workflows import BLOCKED, StateConflict, retryable

ATTEMPTS = 5
STATUS = {"approve": "approved", "reject": "rejected"}


def fingerprint(approval_id: str, b: DecisionIn) -> str:
    meaning = {"command_type": "submit_consent", "approval": approval_id, "user": b.external_user_id,
               "ticket": b.external_ticket_id, "conversation": b.external_conversation_id,
               "workflow": b.workflow_id, "decision": b.decision, "expected_revision": b.expected_revision,
               "arguments_hash": b.arguments_hash, "quote_ref": b.quote_ref}
    raw = json.dumps(meaning, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


def conflict(code: str, message: str, **details) -> WorkforceError:
    return WorkforceError(code, 409, message, details)


def accepted(approval: Any, wf: Any, accepted_at: float) -> dict:
    return {"approval_id": approval["id"], "status": approval["status"],
            "external_ticket_id": wf["external_ticket_id"], "workflow_id": wf["id"], "accepted_at": iso(accepted_at)}


async def _prior(conn, client: str, b: DecisionIn):
    return (await conn.execute(select(t.requests).where(
        t.requests.c.client_id == client, t.requests.c.external_request_id == b.external_request_id))).mappings().first()


def _stored(prior: Any, fp: str, approval: Any, wf: Any) -> tuple[dict | WorkforceError, str | None]:
    if prior["fingerprint"] != fp:
        return WorkforceError("IDEMPOTENCY_CONFLICT", 409, "This external_request_id was used with a different request."), None
    return accepted(approval, wf, prior["accepted_at"]), None


async def _decide(conn, p, approval_id: str, b: DecisionIn, fp: str) -> tuple[dict | WorkforceError, str | None]:
    """(the 202 body or the refusal, the job to tell the engine about)."""
    client = p.client.id
    appr = (await conn.execute(select(t.approvals).where(
        t.approvals.c.id == approval_id, t.approvals.c.client_id == client))).mappings().first()
    if appr is None:
        return not_found(), None
    wf = (await conn.execute(select(t.workflows).where(t.workflows.c.id == appr["workflow_id"]))).mappings().one()
    if not p.covers(wf["route_id"]):
        return route_denied(), None
    prior = await _prior(conn, client, b)
    if prior is not None:  # before any state check: a retry of a decision that worked is not "not pending"
        return _stored(prior, fp, appr, wf)

    refused = await _apply(conn, p, appr, wf, b, fp)
    if isinstance(refused[0], WorkforceError):
        prior = await _prior(conn, client, b)  # a twin may have committed since the lookup above: its result wins
        if prior is not None:
            return _stored(prior, fp, (await conn.execute(select(t.approvals).where(
                t.approvals.c.id == approval_id))).mappings().one(), wf)
    return refused


async def _apply(conn, p, appr: Any, wf: Any, b: DecisionIn, fp: str) -> tuple[dict | WorkforceError, str | None]:
    conv = (await conn.execute(select(t.conversations).where(t.conversations.c.id == wf["conversation_id"]))).mappings().one()
    route = (await conn.execute(select(t.routes).where(t.routes.c.id == wf["route_id"]))).mappings().one()
    if appr["external_user_id"] != b.external_user_id:  # another resident's approval, whatever else is true
        return WorkforceError("PERMISSION_DENIED", 403, "This approval belongs to another user.",
                              {"reason": "audience_mismatch"}), None
    if binding.needs_ticket(route) and not b.external_ticket_id:
        return binding.ticket_required(), None
    if (wf["id"] != b.workflow_id or wf["external_ticket_id"] != b.external_ticket_id
            or conv["external_conversation_id"] != b.external_conversation_id):
        return binding.mismatch(), None  # a mix-up of chats (A's approval used for B): nothing is decided
    if wf["state"] != "closed" and route["status"] in ("suspended", "replaced"):  # as for a reply (S2): the workflow is blocked, once, and refused
        return await _block(conn, wf, "blocked_route_changed" if route["status"] == "replaced" else "blocked_authorization"), None
    await lock_conversation(conn, conv["id"])  # first lock, as for every writer; then read what we decide on
    wf = (await conn.execute(select(t.workflows).where(t.workflows.c.id == wf["id"]))).mappings().one()
    appr = (await conn.execute(select(t.approvals).where(t.approvals.c.id == appr["id"]))).mappings().one()
    if wf["state"] == "closed":
        return binding.closed(), None
    if wf["state"] in BLOCKED:
        return binding.route_moved(wf["state"]), None
    if appr["status"] != "pending":
        return conflict("APPROVAL_NOT_PENDING", "This approval was already decided or withdrawn.",
                        status=appr["status"]), None
    if appr["expires_at"] is not None and appr["expires_at"] <= now():
        return conflict("APPROVAL_EXPIRED", "This approval has expired."), None
    if b.arguments_hash != appr["arguments_hash"]:
        return conflict("ARGUMENTS_HASH_MISMATCH", "The arguments are not the ones the resident was asked about."), None
    if (b.quote_ref or None) != (appr["quote_ref"] or None):
        return conflict("QUOTE_MISMATCH", "The quote is not the one the resident was asked about."), None
    if b.expected_revision != wf["revision"]:
        return revision_conflict(wf["revision"]), None

    rid, stamp = new_id("req"), now()
    await conn.execute(insert(t.requests).values(  # the claim: a parallel twin meets this unique key
        id=rid, client_id=p.client.id, external_request_id=b.external_request_id, command_type="submit_consent",
        fingerprint=fp, route_id=wf["route_id"], conversation_id=conv["id"], workflow_id=wf["id"],
        status="queued", accepted_at=stamp))
    _, job = await resolve(conn, wf, appr, STATUS[b.decision], request_id=rid, reason="approval_decided")
    return accepted({**appr, "status": STATUS[b.decision]}, wf, stamp), job


def build_decision(r: APIRouter, ctx: Any) -> None:
    @r.post("/partner/approvals/{approval_id}/decision")
    async def decision(approval_id: str, request: Request):
        p = await authenticate(request, "customer", "submit_consent")
        b = validated(await json_object(request), DecisionIn)
        fp = fingerprint(approval_id, b)
        for attempt in range(ATTEMPTS):
            try:
                async with ctx.db.engine.begin() as conn:
                    result, job = await _decide(conn, p, approval_id, b, fp)
                break
            except (DBAPIError, StateConflict) as e:
                if not retryable(e):
                    raise
                await asyncio.sleep(0.005 * (attempt + 1) + random.random() * 0.01)
        else:
            raise WorkforceError("INTERNAL_ERROR", 503, "The decision could not be recorded; retry it.",
                                 retryable=True)
        if isinstance(result, WorkforceError):
            raise result
        if job is not None:
            try:
                ctx.engine.notify(result["workflow_id"], job)
            except Exception:
                pass  # the sweep finds the queued job
        return JSONResponse(result, status_code=202)
