"""A request's result: the body of contract 9.1, built once and frozen when the request settles.

A request settles when the workflow it started has come to rest. The frozen body is what every
later POST replay and GET returns, so message ids and text never change on a replay.
Both the test engine and the real engine (S3) call `settle_request`.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select, update

from . import messages, tables as t
from .common import iso, now
from .events import BASE, last_event_id
from .workflows import BLOCKED, BUSY, next_action
from .waker import poke_on_commit

PENDING = ("accepted", "queued", "running")
TERMINAL = ("completed", "failed", "blocked")
URL_KEYS = ("status_url", "conversation_url", "event_stream_url")


def public_error(code: str, message: str) -> dict:
    return {"code": code, "message": message}


FAILURES = {
    "engine_error": "The assistant could not process this message. A person will follow up.",
    "stalled": "Nothing happened on this request for too long. A person will follow up."}


def fail_message(code: str) -> dict:
    """The public error of a request the engine could not complete."""
    return public_error(code, FAILURES[code])


def action_for(status: str, state: str) -> str:
    """The `next_action` of a request in `status` while its workflow is in `state` (contract 9.1 and
    9.3). A pending request says watch_request; a failed or blocked one never sends the client back
    to a normal step of a workflow that did not do what was asked: resolve_attention, or none."""
    if status in PENDING:
        return "watch_request"
    if status in ("failed", "blocked") and state != "closed":
        return "resolve_attention"
    return next_action(state)


async def body_of(conn, req: Any, *, status: str, error: dict | None = None,
                  completed_at: float | None = None) -> dict:
    """Contract 9.1 for `req` as the database says now. A pending request always says watch_request."""
    wf = (await conn.execute(select(t.workflows).where(t.workflows.c.id == req["workflow_id"]))).mappings().one()
    pending = status in PENDING
    cid = req["conversation_id"]
    return {
        "request_id": req["id"], "request_status": status, "external_ticket_id": wf["external_ticket_id"],
        "conversation_id": cid, "workflow_id": wf["id"], "workflow_state": wf["state"],
        "next_action": action_for(status, wf["state"]), "workflow_revision": wf["revision"],
        "ticket_id": wf["ticket_id"],
        "result": None if pending else {"messages": await messages.of_request(conn, req["id"])},
        "error": error, "accepted_at": iso(req["accepted_at"]), "completed_at": iso(completed_at),
        "status_url": f"{BASE}/requests/{req['id']}", "conversation_url": f"{BASE}/conversations/{cid}",
        "event_stream_url": f"{BASE}/conversations/{cid}/events"}


async def mark_running(conn, request_id: str) -> None:
    await conn.execute(update(t.requests).where(
        t.requests.c.id == request_id, t.requests.c.status.in_(("accepted", "queued")))
        .values(status="running"))


async def settle_request(conn, request_id: str, *, status: str | None = None,
                         error: dict | None = None) -> dict | None:
    """Complete a pending request and freeze its body; call it in the transaction that moved the
    workflow to rest. Returns the body, or None when nothing was settled (the request is already
    settled, or the workflow is still busy). `status` forces failed/blocked with a public `error`.
    """
    req = (await conn.execute(select(t.requests).where(t.requests.c.id == request_id))).mappings().first()
    if req is None or req["status"] in TERMINAL:
        return None
    wf_state = (await conn.execute(select(t.workflows.c.state).where(
        t.workflows.c.id == req["workflow_id"]))).scalar_one()
    if status is None:
        if wf_state in BUSY:
            return None
        status = "blocked" if wf_state in BLOCKED else "completed"
    stamp = now()
    body = await body_of(conn, req, status=status, error=error, completed_at=stamp)
    done = await conn.execute(update(t.requests).where(
        t.requests.c.id == request_id, t.requests.c.status.in_(PENDING)).values(
        status=status, error=error, completed_at=stamp,
        response={"body": body, "last_event_id": await last_event_id(conn, req["conversation_id"])}))
    if done.rowcount != 1:
        return None
    poke_on_commit(conn, req["conversation_id"])
    return body


def get_view(body: dict, last_event: str | None, live: Any = None) -> dict:
    """Contract 9.3: the 9.1 body without the three links, plus last_event_id. The result, the
    error and the times stay as they were frozen; `live` (the workflow row now) refreshes what
    tells the client what to do next, so a poller is never sent to a step that no longer exists."""
    out = {k: v for k, v in body.items() if k not in URL_KEYS}
    out["last_event_id"] = last_event
    if live is not None:
        out.update(workflow_state=live["state"], workflow_revision=live["revision"],
                   ticket_id=live["ticket_id"], next_action=action_for(body["request_status"], live["state"]))
    return out
