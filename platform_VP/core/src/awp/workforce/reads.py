"""The read side of the customer API: request, conversation snapshot, event history (contract 9.3-9.5).

Every GET names the user it reads for. The query value is checked against the audience stored
with the conversation and is never a grant by itself; a mismatch answers 404, like a missing id.
"""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select

from . import tables as t
from .auth import PartnerPrincipal, need, require
from .common import iso
from .errors import WorkforceError, failed, field_errors
from .events import DEFAULT_LIMIT, MAX_LIMIT, history, last_event_id
from .messages import public_message
from .schemas import ExtId
from .settle import TERMINAL, body_of, get_view
from .workflows import next_action

PAGE = 200
_user = TypeAdapter(ExtId)


def not_found() -> WorkforceError:
    return WorkforceError("NOT_FOUND", 404, "No such resource for this caller.")


def audience(external_user_id: str | None) -> str:
    """The `external_user_id` query value: required, and shaped like any partner id."""
    try:
        if external_user_id is None:
            raise ValueError("required")
        return _user.validate_python(external_user_id)
    except (ValidationError, ValueError) as e:
        errs = e.errors() if isinstance(e, ValidationError) else [{"msg": "required"}]
        raise failed("external_user_id is required.", field_errors(
            [{**x, "loc": ("external_user_id",)} for x in errs]))


async def own_conversation(conn, p: PartnerPrincipal, conversation_id: str, user: str) -> Any:
    conv = (await conn.execute(select(t.conversations).where(
        t.conversations.c.id == conversation_id, t.conversations.c.client_id == p.client.id))).mappings().first()
    if conv is None or conv["external_user_id"] != user or not p.covers(conv["route_id"]):
        raise not_found()
    return conv


def _close_view(req: Any, body: dict, last: str | None) -> dict:
    """A close command read through GET request: contract 9.3 fields."""
    return {"request_id": body["request_id"], "request_status": body["request_status"],
            "external_ticket_id": body["external_ticket_id"], "conversation_id": body["conversation_id"],
            "workflow_id": body["workflow_id"], "workflow_state": body["state"],
            "next_action": body["next_action"], "ticket_id": body["ticket_id"],
            "accepted_at": iso(req["accepted_at"]), "completed_at": body["closed_at"],
            "last_event_id": last, "workflow_revision": body["revision"], "result": None, "error": None}


def _approval(a: Any) -> dict:
    return {"approval_id": a["id"], "workflow_id": a["workflow_id"], "status": a["status"],
            "tool_name": a["tool_name"], "summary": a["summary"], "arguments_hash": a["arguments_hash"],
            "quote_ref": a["quote_ref"], "expected_revision": a["workflow_revision"],
            "expires_at": iso(a["expires_at"])}


async def snapshot(conn, conv: Any, user: str, before: str | None) -> dict:
    """One consistent picture. Every change to a workflow, message or approval commits together
    with a public event, so the log's last sequence is a version stamp: read it before and after,
    and read again if it moved (no lock is held, on SQLite or Postgres)."""
    cid = conv["id"]
    start = None
    if before is not None:
        start = (await conn.execute(select(t.messages.c.sequence).where(
            t.messages.c.id == before, t.messages.c.conversation_id == cid))).scalar()
        if start is None:
            raise failed("Cursor is not a message of this conversation.",
                         [{"field": "messages_before", "reason": "unknown message"}])
    for attempt in range(8):
        stamp = (await conn.execute(select(t.conversations.c.last_sequence).where(
            t.conversations.c.id == cid))).scalar_one()
        wfs = (await conn.execute(select(t.workflows).where(t.workflows.c.conversation_id == cid)
                                  .order_by(t.workflows.c.created_at))).mappings().all()
        q = select(t.messages).where(t.messages.c.conversation_id == cid)
        if start is not None:
            q = q.where(t.messages.c.sequence < start)
        msgs = (await conn.execute(q.order_by(t.messages.c.sequence.desc()).limit(PAGE + 1))).mappings().all()
        apps = (await conn.execute(select(t.approvals).where(
            t.approvals.c.conversation_id == cid, t.approvals.c.status == "pending",
            t.approvals.c.external_user_id == user).order_by(t.approvals.c.created_at))).mappings().all()
        cursor = await last_event_id(conn, cid)
        again = (await conn.execute(select(t.conversations.c.last_sequence).where(
            t.conversations.c.id == cid))).scalar_one()
        if again == stamp:
            break
        await asyncio.sleep(0.005 * (attempt + 1))
    else:  # never hand out a picture whose cursor is ahead of its data: the client would miss events
        raise WorkforceError("INTERNAL_ERROR", 503, "The conversation is changing too fast to read; retry.",
                             retryable=True)
    return {
        "conversation_id": cid, "external_ticket_id": conv["external_ticket_id"],
        "external_conversation_id": conv["external_conversation_id"],
        "external_user_id": conv["external_user_id"],
        "workflows": [{"workflow_id": w["id"], "external_ticket_id": w["external_ticket_id"],
                       "ticket_id": w["ticket_id"], "state": w["state"],
                       "next_action": next_action(w["state"]), "revision": w["revision"]} for w in wfs],
        "messages": [public_message(m) for m in reversed(msgs[:PAGE])],
        "has_more_messages": len(msgs) > PAGE,
        "approvals": [_approval(a) for a in apps],
        "snapshot_cursor": cursor}


def build_reads(r: APIRouter, ctx: Any) -> None:
    db = ctx.db

    @r.get("/partner/requests/{request_id}")
    async def get_request(request_id: str, external_user_id: str | None = Query(None),
                          p: PartnerPrincipal = Depends(require("read_result"))):
        user = audience(external_user_id)
        async with db.engine.connect() as conn:
            req = (await conn.execute(select(t.requests).where(
                t.requests.c.id == request_id, t.requests.c.client_id == p.client.id))).mappings().first()
            if req is None or not req["conversation_id"] or not p.covers(req["route_id"]):
                raise not_found()
            await own_conversation(conn, p, req["conversation_id"], user)
            if req["status"] in TERMINAL:
                frozen = req["response"]
                if req["command_type"] == "close_workflow":
                    return _close_view(req, frozen["body"], frozen["last_event_id"])
                wf = (await conn.execute(select(t.workflows).where(
                    t.workflows.c.id == req["workflow_id"]))).mappings().one()
                return get_view(frozen["body"], await last_event_id(conn, req["conversation_id"]), wf)
            body = await body_of(conn, req, status=req["status"])
            return get_view(body, await last_event_id(conn, req["conversation_id"]))

    @r.get("/partner/conversations/{conversation_id}")
    async def get_conversation(conversation_id: str, external_user_id: str | None = Query(None),
                               messages_before: str | None = Query(None, max_length=200),
                               p: PartnerPrincipal = Depends(require("read_result"))):
        user = audience(external_user_id)
        async with db.engine.connect() as conn:
            conv = await own_conversation(conn, p, conversation_id, user)
            return await snapshot(conn, conv, user, messages_before)

    @r.get("/partner/conversations/{conversation_id}/event-history")
    async def get_history(conversation_id: str, external_user_id: str | None = Query(None),
                          after_cursor: str | None = Query(None, max_length=200),
                          limit: int = Query(DEFAULT_LIMIT),
                          p: PartnerPrincipal = Depends(require("read_result"))):
        need(p, "receive_events")
        user = audience(external_user_id)
        if limit < 1:
            raise failed("limit must be at least 1.", [{"field": "limit", "reason": "too small"}])
        async with db.engine.connect() as conn:
            conv = await own_conversation(conn, p, conversation_id, user)
            return await history(conn, conv, after_cursor or None, min(limit, MAX_LIMIT))
