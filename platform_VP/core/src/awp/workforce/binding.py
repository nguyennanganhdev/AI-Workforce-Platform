"""Ticket and conversation binding (contract 6.3, 9.1.1): who may talk to which workflow.

The partner supplies a (user, ticket, conversation, workflow) tuple on every command and the
platform never guesses: a tuple that does not match what was stored is refused and nothing runs.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select

from . import tables as t
from .auth import route_denied
from .errors import WorkforceError


def ticket_required() -> WorkforceError:
    return WorkforceError("EXTERNAL_TICKET_REQUIRED", 422,
                          "This route needs the external_ticket_id of the chat.")


def ticket_bound(workflow_id: str | None) -> WorkforceError:
    return WorkforceError("TICKET_ALREADY_BOUND", 409,
                          "This external ticket already has a workflow; send workflow_reply.",
                          {"workflow_id": workflow_id} if workflow_id else {})


def conversation_bound() -> WorkforceError:
    return WorkforceError("CONVERSATION_ALREADY_BOUND", 409,
                          "This external conversation is already bound to a workflow; use a new one.")


def mismatch() -> WorkforceError:
    return WorkforceError("WORKFLOW_BINDING_MISMATCH", 409,
                          "User, ticket, conversation and workflow do not belong together.")


def reference_required() -> WorkforceError:
    return WorkforceError("WORKFLOW_REFERENCE_REQUIRED", 422, "workflow_reply needs the workflow_id.")


def closed() -> WorkforceError:
    return WorkforceError("WORKFLOW_CLOSED", 409, "This workflow is closed.")


def approval_pending(approval_id: str | None) -> WorkforceError:
    return WorkforceError("APPROVAL_PENDING", 409, "An approval decision is waiting; answer it first.",
                          {"approval_id": approval_id} if approval_id else {})


def route_moved(state: str) -> WorkforceError:
    """The route the workflow runs on was suspended or replaced: the partner cannot go on with it."""
    why = "route_replaced" if state == "blocked_route_changed" else "route_suspended"
    return route_denied(reason=why)


class RouteMoved(Exception):
    """The workflow's own route is suspended/replaced. The service marks the workflow `state`
    (committing it) and then refuses the command."""

    def __init__(self, workflow: Any, state: str) -> None:
        super().__init__(state)
        self.workflow, self.state = workflow, state


def needs_ticket(route: Any) -> bool:
    return route["config"].get("ticket_binding_mode", "required") == "required"


async def check_start(conn, client_id: str, route: Any, body: Any) -> None:
    if needs_ticket(route) and not body.external_ticket_id:
        raise ticket_required()
    if body.external_ticket_id:
        await _ticket_free(conn, client_id, body)
    taken = (await conn.execute(select(t.conversations.c.id, t.conversations.c.external_ticket_id).where(
        t.conversations.c.client_id == client_id,
        t.conversations.c.external_conversation_id == body.external_conversation_id))).first()
    if taken is not None:
        if body.external_ticket_id and taken[1] == body.external_ticket_id:
            await _ticket_free(conn, client_id, body)  # same ticket: it was bound a moment ago
        raise conversation_bound()


async def _ticket_free(conn, client_id: str, body: Any) -> None:
    found = (await conn.execute(select(t.workflows.c.id, t.workflows.c.external_user_id).where(
        t.workflows.c.client_id == client_id,
        t.workflows.c.external_ticket_id == body.external_ticket_id))).first()
    if found is not None:  # the workflow id only goes back to the user it belongs to
        raise ticket_bound(found[0] if found[1] == body.external_user_id else None)


async def find_bound(conn, client_id: str, body: Any) -> tuple[Any, Any] | None:
    """(workflow, conversation) when `body` names a workflow of this client whose stored user,
    ticket and conversation are exactly the ones sent; None otherwise."""
    wf = (await conn.execute(select(t.workflows).where(
        t.workflows.c.id == body.workflow_id, t.workflows.c.client_id == client_id))).mappings().first()
    if wf is None:
        return None
    conv = (await conn.execute(select(t.conversations).where(
        t.conversations.c.id == wf["conversation_id"]))).mappings().one()
    same = (wf["external_user_id"] == body.external_user_id
            and wf["external_ticket_id"] == body.external_ticket_id
            and conv["external_conversation_id"] == body.external_conversation_id)
    return (wf, conv) if same else None


async def check_reply(conn, client_id: str, route: Any, body: Any) -> tuple[Any, Any]:
    if needs_ticket(route) and not body.external_ticket_id:
        raise ticket_required()
    bound = await find_bound(conn, client_id, body)
    if bound is None:
        raise mismatch()
    wf, conv = bound
    if wf["route_id"] != route["id"]:
        old = (await conn.execute(select(t.routes.c.status).where(t.routes.c.id == wf["route_id"]))).scalar_one()
        if wf["state"] != "closed" and old in ("replaced", "suspended"):
            raise RouteMoved(wf, "blocked_route_changed" if old == "replaced" else "blocked_authorization")
        if wf["state"] != "closed":
            raise mismatch()  # the ref sent points at another office than the workflow's
    return wf, conv
