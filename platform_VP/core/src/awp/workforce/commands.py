"""POST /workforce/v1/partner/requests: start_workflow and workflow_reply (contract 9.1, 9.2).

Order of checks: credential -> operation -> schema -> idempotency -> route -> residence ->
ticket binding -> workflow state -> one transaction that writes everything -> wait for the turn.
Idempotency comes before the route (contract 9.1, 11.1): a lost answer is recovered by sending
the same request again, even after the route was remapped, provided the key still covers the
route the request ran on. The wait holds no transaction.

Lock order: a reply takes the conversation's write lock before it reads the workflow, as every
other writer does (events.lock_conversation), so the workflow cannot change under it.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
import time
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import insert, select
from sqlalchemy.exc import DBAPIError

from . import binding, tables as t, uploads
from .auth import authenticate, lacks, need, route_denied
from .common import now
from .errors import WorkforceError, failed, invalid, json_object, validated
from .events import emit, lock_conversation
from .messages import add_user_message
from .schemas import ImageRequestIn, RequestIn
from .settle import TERMINAL, body_of
from .tables import new_id
from .waker import wait, waker
from .workflows import BLOCKED, BUSY, StateConflict, retryable, transition

log = logging.getLogger("awp.workforce")
OPERATION = {"start_workflow": "submit_request", "workflow_reply": "reply"}
ATTEMPTS = 5


@dataclass
class Accepted:
    request_id: str
    conversation_id: str
    workflow_id: str
    wait_seconds: float
    job_id: str | None = None  # None when this call only found the request again


def fingerprint(b: RequestIn) -> str:
    """Idempotency compares what the command means, not how it was spelled on the wire."""
    meaning = {"command_type": b.command_type, "ref": b.external_management_ref,
               "user": b.external_user_id, "ticket": b.external_ticket_id,
               "conversation": b.external_conversation_id, "workflow": b.workflow_id,
               "residence": b.residence_id, "timezone": b.timezone,
               "message": {"type": b.message.type, "text": b.message.text}}
    if b.message.type == "image":  # (a text message keeps the fingerprint it always had)
        meaning["message"]["asset_id"] = b.message.asset_id
    raw = json.dumps(meaning, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


def parse(data: dict, text_limit: int, images: bool = False) -> RequestIn:
    """`images`: the client has the capability attach_asset (spec A3). Without it an image is what any other part
    that is not text is: unsupported (contract 6.2)."""
    msg = data.get("message")
    kind = msg.get("type") if isinstance(msg, dict) else None
    if isinstance(kind, str) and kind != "text" and not (kind == "image" and images):
        raise WorkforceError("UNSUPPORTED_MESSAGE_PART", 422,
                             "Only text messages are accepted.", {"part_type": kind[:40]})
    body = validated(data, ImageRequestIn if kind == "image" else RequestIn)
    if len(body.message.text or "") > text_limit:
        raise failed("Request does not match the schema.",
                     [{"field": "message.text", "reason": f"longer than {text_limit} characters"}])
    if body.command_type == "start_workflow" and body.workflow_id is not None:
        raise invalid("start_workflow cannot carry a workflow_id.")
    if body.command_type == "workflow_reply" and body.workflow_id is None:
        raise binding.reference_required()
    return body


async def _moved(ctx, conn, p, body, refs) -> WorkforceError | None:
    """A reply whose route has no active successor under this ref: if it names a workflow of this
    key on a suspended/replaced route, mark that workflow blocked (once) and say why."""
    bound = await binding.find_bound(conn, p.client.id, body)
    if bound is None:
        return None
    wf = bound[0]
    old = next((x for x in refs if x["id"] == wf["route_id"]), None)
    if old is None or old["status"] not in ("suspended", "replaced") or not p.covers(old["id"]):
        return None
    target = "blocked_route_changed" if old["status"] == "replaced" else "blocked_authorization"
    return await _block(conn, wf, target)


async def _fresh(conn, workflow_id: str) -> Any:
    return (await conn.execute(select(t.workflows).where(t.workflows.c.id == workflow_id))).mappings().one()


async def _block(conn, wf: Any, target: str) -> WorkforceError:
    await lock_conversation(conn, wf["conversation_id"])
    wf = await _fresh(conn, wf["id"])
    if wf["state"] != "closed" and wf["state"] != target:
        await transition(conn, wf, target, reason="route_replaced" if target == "blocked_route_changed"
                         else "route_suspended")
    return binding.route_moved(target)


async def _accept(ctx, conn, p, body: RequestIn, fp: str) -> Accepted | WorkforceError:
    client, start = p.client.id, body.command_type == "start_workflow"
    prior = await _prior(conn, client, body)
    if prior is not None:
        return await _replay(ctx, conn, p, prior, fp)
    refs = (await conn.execute(select(t.routes).where(
        t.routes.c.client_id == client, t.routes.c.external_management_ref == body.external_management_ref)
        .order_by(t.routes.c.created_at.desc()))).mappings().all()
    route = next((x for x in refs if x["status"] == "active"), None)
    if route is None or not p.covers(route["id"]):
        if route is None and not start:
            refused = await _moved(ctx, conn, p, body, refs)
            if refused is not None:
                return refused
        known = route is None and any(p.covers(x["id"]) for x in refs)
        return route_denied(**({"reason": "route_not_active"} if known else {}))
    wait_s = _wait(ctx, route)

    try:
        return await _admit(ctx, conn, p, body, fp, route, wait_s)
    except WorkforceError:
        # The checks ran on a view that a twin of this very request may have changed since the
        # lookup above (it bound the ticket, or closed the workflow): the twin's request wins, and
        # an id reused with a different body is a conflict whatever the stale view said.
        prior = await _prior(conn, client, body)
        if prior is not None:
            return await _replay(ctx, conn, p, prior, fp)
        raise


def _wait(ctx, route: Any) -> float:
    wait_s = route["config"].get("wait_seconds")
    return ctx.settings.wf_wait_seconds if wait_s is None else float(wait_s)


async def _replay(ctx, conn, p, prior: Any, fp: str) -> Accepted | WorkforceError:
    """The request that already carries this external_request_id: the caller needs a grant on the
    route it ran on (not on whatever route the ref points to now), then the body must be the same."""
    if prior["route_id"] and not p.covers(prior["route_id"]):
        return route_denied()
    if prior["fingerprint"] != fp:
        return WorkforceError("IDEMPOTENCY_CONFLICT", 409,
                              "This external_request_id was used with a different request.")
    route = (await conn.execute(select(t.routes).where(t.routes.c.id == prior["route_id"]))).mappings().first()
    wait_s = _wait(ctx, route) if route is not None else ctx.settings.wf_wait_seconds
    return Accepted(prior["id"], prior["conversation_id"], prior["workflow_id"], wait_s)


async def _prior(conn, client: str, body: RequestIn):
    return (await conn.execute(select(t.requests).where(
        t.requests.c.client_id == client,
        t.requests.c.external_request_id == body.external_request_id))).mappings().first()


async def _admit(ctx, conn, p, body: RequestIn, fp: str, route: Any, wait_s: float) -> Accepted | WorkforceError:
    """Residence, binding, state, then the one write transaction."""
    client, start, cfg = p.client.id, body.command_type == "start_workflow", route["config"]
    if start and cfg.get("residence_required"):
        if not body.residence_id:
            raise failed("residence_id is required for this route.",
                         [{"field": "residence_id", "reason": "required"}])
        res = (await conn.execute(select(t.residences).where(
            t.residences.c.client_id == client, t.residences.c.residence_id == body.residence_id,
            t.residences.c.external_user_id == body.external_user_id))).mappings().first()
        if res is None or res["status"] != "active" or res["route_id"] != route["id"]:
            return route_denied(reason="residence_not_registered")

    wf: Any
    try:
        if start:
            await binding.check_start(conn, client, route, body)
        else:
            wf, conv = await binding.check_reply(conn, client, route, body)
    except binding.RouteMoved as m:
        if not p.covers(m.workflow["route_id"]):  # a key with no grant on that route changes nothing there
            return route_denied()
        return await _block(conn, m.workflow, m.state)
    image = body.message.asset_id if body.message.type == "image" else None
    if image:  # the asset of exactly this client, resident and conversation, or nothing
        await uploads.for_message(conn, client, body.external_user_id, body.external_conversation_id, image)

    if not start:
        await lock_conversation(conn, conv["id"])
        wf = await _fresh(conn, wf["id"])  # read under the lock: it cannot change before we commit
        twin = await _prior(conn, client, body)  # a twin may have committed while we waited
        if twin is not None:
            return await _replay(ctx, conn, p, twin, fp)
        if wf["state"] == "closed":
            raise binding.closed()
        if wf["state"] in BLOCKED:
            return binding.route_moved(wf["state"])
        appr = (await conn.execute(select(t.approvals.c.id).where(  # the approvals decide, not the state's name
            t.approvals.c.workflow_id == wf["id"], t.approvals.c.status == "pending")
            .order_by(t.approvals.c.created_at))).first()
        if appr is not None or wf["state"] == "awaiting_approval":
            raise binding.approval_pending(appr[0] if appr else None)

    rid, stamp = new_id("req"), now()
    conv_id = new_id("conv") if start else conv["id"]
    wf_id = new_id("wf") if start else wf["id"]
    # The request row goes first: it is the idempotency claim, and two identical requests that
    # race here meet on its unique key (the loser re-reads and finds the winner).
    await conn.execute(insert(t.requests).values(
        id=rid, client_id=client, external_request_id=body.external_request_id,
        command_type=body.command_type, fingerprint=fp, route_id=route["id"],
        conversation_id=conv_id, workflow_id=wf_id, status="queued", accepted_at=stamp))
    if start:
        s = ctx.settings
        case_id = await ctx.rt.cases.create_case(
            tenant=p.client.tenant, domain=p.client.domain, external_ref=wf_id,
            user_id=body.external_user_id, conn=conn,
            budget_usd=s.case_budget_usd, budget_tokens=s.case_budget_tokens,
            meta={"workflow_id": wf_id, "route_id": route["id"],
                    "residence_id": body.residence_id if cfg.get("residence_required") else None,
                    "timezone": body.timezone or cfg.get("timezone")})
        await conn.execute(insert(t.conversations).values(
            id=conv_id, client_id=client, route_id=route["id"], external_user_id=body.external_user_id,
            external_conversation_id=body.external_conversation_id,
            external_ticket_id=body.external_ticket_id, last_sequence=0, purged_through=0, created_at=stamp))
        wf = dict(id=wf_id, conversation_id=conv_id, client_id=client, route_id=route["id"],
                  case_id=case_id, external_user_id=body.external_user_id,
                  external_ticket_id=body.external_ticket_id, ticket_id=None, state="accepted",
                  revision=1, expects=None, current_request_id=rid, close_reason=None,
                  attention_reason=None, last_activity_at=stamp, created_at=stamp, closed_at=None)
        await conn.execute(insert(t.workflows).values(**wf))
    ev = await emit(conn, conv_id, "request.accepted", {"request_id": rid, **({"asset_ids": [image]} if image else {})},
                    workflow=wf)
    mid = await add_user_message(conn, wf, rid, body.message.text or "", ev.sequence, [image] if image else [])
    if image:
        await uploads.bind(conn, image, conv_id)
    if not start:  # a resident's word puts a resting workflow back to work; a busy one stays as it is
        wf = await transition(conn, wf, wf["state"] if wf["state"] in BUSY else "active",
                              reason=None if wf["state"] in BUSY else "resident_reply", request_id=rid)
    job_id = new_id("job")
    await conn.execute(insert(t.jobs).values(
        id=job_id, workflow_id=wf_id, kind="resident_message", request_id=rid, status="queued",
        payload={"message_id": mid, "timezone": body.timezone or cfg.get("timezone")},
        attempts=0, created_at=stamp))
    return Accepted(rid, conv_id, wf_id, wait_s, job_id)


async def accept(ctx, p, body: RequestIn) -> Accepted:
    fp = fingerprint(body)
    for attempt in range(ATTEMPTS):
        try:
            async with ctx.db.engine.begin() as conn:
                result = await _accept(ctx, conn, p, body, fp)
            break
        except (DBAPIError, StateConflict) as e:
            # A parallel request won a unique key or changed the workflow: look again.
            if not retryable(e):
                raise
            await asyncio.sleep(0.005 * (attempt + 1) + random.random() * 0.01)
    else:
        raise WorkforceError("INTERNAL_ERROR", 503, "The request could not be recorded; retry it.",
                             retryable=True)
    if isinstance(result, WorkforceError):
        raise result
    return result


async def respond(ctx, a: Accepted) -> JSONResponse:
    """200 with the frozen result once the request settled; 202 when `wait_seconds` run out."""
    deadline = time.monotonic() + a.wait_seconds
    with waker.watch(a.conversation_id) as ev:
        while True:
            ev.clear()
            async with ctx.db.engine.connect() as conn:
                req = (await conn.execute(select(t.requests).where(
                    t.requests.c.id == a.request_id))).mappings().one()
                if req["status"] in TERMINAL:
                    return JSONResponse(req["response"]["body"], status_code=200)
                left = deadline - time.monotonic()
                if left <= 0:
                    return JSONResponse(await body_of(conn, req, status=req["status"]), status_code=202)
            await wait(ev, min(left, random.uniform(0.1, 0.25)))


def build_commands(r: APIRouter, ctx: Any) -> None:
    @r.post("/partner/requests")
    async def post_request(request: Request):
        p = await authenticate(request, "customer", None)
        data = await json_object(request)
        kind = data.get("command_type")
        if isinstance(kind, str) and kind in OPERATION:
            need(p, OPERATION[kind])
        elif not (p.operations & {"submit_request", "reply"}):
            raise lacks("submit_request")
        body = parse(data, ctx.settings.wf_text_limit, images=uploads.has_capability(p))
        a = await accept(ctx, p, body)
        if a.job_id:
            try:
                ctx.engine.notify(a.workflow_id, a.job_id)
            except Exception:
                log.exception("engine.notify failed for job %s", a.job_id)
        return await respond(ctx, a)
