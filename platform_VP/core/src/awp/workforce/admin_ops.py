"""Admin: what the platform is doing for the tenant's partners (spec 7.4): workflows, operations, approvals,
and the one write an operator has, `resolve` for a workflow that needs attention.

Everything is read through the admin's tenant (another tenant's rows answer 404), and for a manager's key through
that manager's routes (M6): another manager's workflow, operation, approval or receipt is a 404 or simply not listed,
and so is its `resolve`. Nothing here shows a secret, a header, a prompt, or the text of a chat; an operation shows
the partner's own answer and its ids.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import insert, select, update

from . import tables as t
from .adminkit import Scope, first, scope_of, tenant_clients
from .close import shut
from .common import iso, now
from .events import lock_conversation
from .schemas import ResolveIn
from .tables import new_id
from .workflows import StateConflict, next_action, transition

PAGE = 50
MAX_PAGE = 200
CLOSED_BY_OPERATOR = "operator_closed"


def workflow_out(w: Any) -> dict:
    return {"workflow_id": w["id"], "client_id": w["client_id"], "route_id": w["route_id"],
            "conversation_id": w["conversation_id"], "external_user_id": w["external_user_id"],
            "external_ticket_id": w["external_ticket_id"], "ticket_id": w["ticket_id"], "state": w["state"],
            "next_action": next_action(w["state"]), "revision": w["revision"],
            "attention_reason": w["attention_reason"], "close_reason": w["close_reason"],
            "created_at": iso(w["created_at"]), "last_activity_at": iso(w["last_activity_at"]),
            "closed_at": iso(w["closed_at"])}


def operation_out(o: Any) -> dict:
    result = o["result"] or {}
    return {"operation_id": o["id"], "workflow_id": o["workflow_id"], "route_id": o["route_id"],
            "tool": o["tool_name"], "status": o["status"], "partner_status": o["normalized_status"],
            "client_reference": o["client_reference"], "external_job_id": o["external_job_id"],
            "args_hash": o["args_hash"], "outcome": result.get("outcome"), "error": result.get("error"),
            "sent": result.get("sent"), "reviewed": bool(result.get("reviewed")), "text": result.get("text"),
            "created_at": iso(o["created_at"]), "updated_at": iso(o["updated_at"])}


def receipt_out(x: Any) -> dict:
    """A provider event as the operator sees it: what it was and what became of it. Not its data (a provider's own text)."""
    return {"receipt_id": x["receipt_id"], "integration_id": x["integration_id"], "external_event_id": x["external_event_id"],
            "event_type": x["event_type"], "ingestion_status": x["ingestion_status"],
            "normalized_status": x["normalized_status"], "operation_id": x["operation_id"], "workflow_id": x["workflow_id"],
            "provider_version": x["provider_version"], "error": x["error"], "note": x["note"],
            "received_at": iso(x["received_at"]), "applied_at": iso(x["applied_at"])}


def approval_out(a: Any) -> dict:
    return {"approval_id": a["id"], "workflow_id": a["workflow_id"], "tool": a["tool_name"], "status": a["status"],
            "summary": a["summary"], "arguments_hash": a["arguments_hash"], "quote_ref": a["quote_ref"],
            "workflow_revision": a["workflow_revision"], "expires_at": iso(a["expires_at"]),
            "decided_at": iso(a["decided_at"]), "created_at": iso(a["created_at"])}


def build_admin_ops(r: APIRouter, ctx: Any) -> None:
    db = ctx.db

    def mine(who: Scope):
        own = t.workflows.c.client_id.in_(tenant_clients(who.tenant))
        return own & t.workflows.c.route_id.in_(who.routes()) if who.manager_id else own

    async def workflow_of(conn, who: Scope, workflow_id: str) -> Any:
        return await first(conn, select(t.workflows).where(t.workflows.c.id == workflow_id, mine(who)), "workflow")

    @r.get("/workflows")
    async def list_workflows(request: Request, client_id: str | None = None, route_id: str | None = None,
                             state: str | None = None, limit: int = Query(PAGE, ge=1, le=MAX_PAGE)):
        who = scope_of(request)
        q = select(t.workflows).where(mine(who))
        for column, value in ((t.workflows.c.client_id, client_id), (t.workflows.c.route_id, route_id),
                              (t.workflows.c.state, state)):
            if value:
                q = q.where(column == value)
        async with db.engine.connect() as conn:
            rows = (await conn.execute(q.order_by(t.workflows.c.created_at.desc()).limit(limit))).mappings().all()
        return {"workflows": [workflow_out(w) for w in rows]}

    @r.get("/workflows/{workflow_id}")
    async def read_workflow(workflow_id: str, request: Request):
        who = scope_of(request)
        async with db.engine.connect() as conn:
            return workflow_out(await workflow_of(conn, who, workflow_id))

    @r.get("/operations")
    async def list_operations(request: Request, workflow_id: str | None = None, status: str | None = None,
                              limit: int = Query(PAGE, ge=1, le=MAX_PAGE)):
        who = scope_of(request)
        q = select(t.operations).where(t.operations.c.workflow_id.in_(select(t.workflows.c.id).where(mine(who))))
        if workflow_id:
            q = q.where(t.operations.c.workflow_id == workflow_id)
        if status:
            q = q.where(t.operations.c.status == status)
        async with db.engine.connect() as conn:
            rows = (await conn.execute(q.order_by(t.operations.c.created_at.desc()).limit(limit))).mappings().all()
        return {"operations": [operation_out(o) for o in rows]}

    @r.get("/operations/{operation_id}")
    async def read_operation(operation_id: str, request: Request):
        who = scope_of(request)
        async with db.engine.connect() as conn:
            return operation_out(await first(conn, select(t.operations).where(
                t.operations.c.id == operation_id,
                t.operations.c.workflow_id.in_(select(t.workflows.c.id).where(mine(who)))), "operation"))

    @r.get("/approvals")
    async def list_approvals(request: Request, workflow_id: str | None = None, status: str | None = None,
                             limit: int = Query(PAGE, ge=1, le=MAX_PAGE)):
        who = scope_of(request)
        q = select(t.approvals).where(t.approvals.c.workflow_id.in_(select(t.workflows.c.id).where(mine(who))))
        if workflow_id:
            q = q.where(t.approvals.c.workflow_id == workflow_id)
        if status:
            q = q.where(t.approvals.c.status == status)
        async with db.engine.connect() as conn:
            rows = (await conn.execute(q.order_by(t.approvals.c.created_at.desc()).limit(limit))).mappings().all()
        return {"approvals": [approval_out(a) for a in rows]}

    def own_receipts(who: Scope):
        """A manager sees the receipts of its own workflows; an event that matched no workflow yet is the admin's to see."""
        own = t.provider_inbox.c.integration_id.in_(select(t.integrations.c.id).where(
            t.integrations.c.client_id.in_(tenant_clients(who.tenant))))
        return own & t.provider_inbox.c.workflow_id.in_(select(t.workflows.c.id).where(mine(who))) if who.manager_id else own

    @r.get("/receipts")
    async def list_receipts(request: Request, integration_id: str | None = None, status: str | None = None,
                            workflow_id: str | None = None, limit: int = Query(PAGE, ge=1, le=MAX_PAGE)):
        who = scope_of(request)
        q = select(t.provider_inbox).where(own_receipts(who))
        for column, value in ((t.provider_inbox.c.integration_id, integration_id),
                              (t.provider_inbox.c.ingestion_status, status), (t.provider_inbox.c.workflow_id, workflow_id)):
            if value:
                q = q.where(column == value)
        async with db.engine.connect() as conn:
            rows = (await conn.execute(q.order_by(t.provider_inbox.c.received_at.desc()).limit(limit))).mappings().all()
        return {"receipts": [receipt_out(x) for x in rows]}

    @r.get("/receipts/{receipt_id}")
    async def read_receipt(receipt_id: str, request: Request):
        who = scope_of(request)
        async with db.engine.connect() as conn:
            return receipt_out(await first(conn, select(t.provider_inbox).where(
                t.provider_inbox.c.receipt_id == receipt_id, own_receipts(who)), "receipt"))

    @r.post("/workflows/{workflow_id}/resolve")
    async def resolve(workflow_id: str, body: ResolveIn, request: Request):
        """A person looked at a workflow that needs attention. `close` ends it (and stops tracking whatever was
        open; nothing is called at the partner). `resume` lets the leader go on: unknown operations a person has
        seen no longer hold the workflow, and the leader is told to continue."""
        who = scope_of(request)
        async with db.engine.begin() as conn:
            wf = await workflow_of(conn, who, workflow_id)
            await lock_conversation(conn, wf["conversation_id"])
            wf = await workflow_of(conn, who, workflow_id)
            if wf["state"] != "needs_attention":
                raise HTTPException(409, f"the workflow is {wf['state']}; only needs_attention can be resolved")
            try:
                if body.action == "close":
                    done = await shut(ctx.rt, conn, wf, CLOSED_BY_OPERATOR)
                else:
                    seen = (await conn.execute(select(t.operations).where(
                        t.operations.c.workflow_id == workflow_id, t.operations.c.status == "unknown"))).mappings().all()
                    for op in seen:
                        await conn.execute(update(t.operations).where(t.operations.c.id == op["id"]).values(
                            result={**(op["result"] or {}), "reviewed": True}))
                    done = await transition(conn, wf, "active", reason="operator_resumed")
                    await conn.execute(insert(t.jobs).values(
                        id=new_id("job"), workflow_id=workflow_id, kind="operator", request_id=None, status="queued",
                        payload={}, attempts=0, created_at=now()))
            except StateConflict:
                raise HTTPException(409, "the workflow changed; read it again")
        kick = getattr(ctx.engine, "kick", None)
        if kick is not None:
            kick(workflow_id)
        return workflow_out({**dict(wf), **done})
