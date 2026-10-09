"""Explicit consent and close; agent output never impersonates either command."""
import time

from sqlalchemy import select, update

from . import schema as s
from .service import Fault, row, stamp, uid


async def resume_after_operation(service, conn, wf, op):
    """One durable supervisor continuation after a consented operation reaches a terminal result."""
    if wf["state"] == "closed" or not op["data"].get("continuation_required") or op["data"].get("resume_request_id"):
        return False
    if op["status"] not in ("completed", "confirmed", "cancelled"):
        return False
    import json
    origin = await row(conn, s.requests, s.requests.c.id == op["data"]["request_id"])
    client = await row(conn, s.clients, s.clients.c.id == origin["client_id"])
    payload = {**origin["body"], "external_request_id": "internal:" + uid(), "workflow_id": wf["id"],
        "command_type": "workflow_reply", "message": {"text": "Continue the original plan using this verified domain operation result. "
        "Do not repeat the operation. Determine whether any further step or user confirmation is needed.\n" +
        json.dumps({"operation_id": op["id"], "status": op["status"], "result": op["data"].get("result"),
                    "provider_data": op["data"].get("provider_data"),
                    "reconciliation": op["data"].get("reconciliation")}, ensure_ascii=False), "asset_ids": []}}
    req = await service.add_request(conn, client, wf, payload, "system_continuation")
    await conn.execute(update(s.operations).where(s.operations.c.id == op["id"]).values(
        data={**op["data"], "resume_request_id": req["id"]}))
    await service.enqueue(conn, wf, req, payload={"source_operation": op["id"]})
    return True


async def complete(service, workflow_id, text, expects="none", error=None, fence=None):
    async with service.tx() as conn:
        if fence:
            await fence.check(service, conn)
        wf = await row(conn, s.workflows, s.workflows.c.id == workflow_id, lock=True)
        if not wf or wf["state"] == "closed":
            return False
        req = await row(conn, s.requests, s.requests.c.workflow_id == wf["id"],
                        s.requests.c.status == "running", lock=True)
        if not req:
            raise Fault(409, "NO_ACTIVE_REQUEST")
        pending = (await conn.execute(select(s.operations.c.status).where(s.operations.c.workflow_id == wf["id"],
                    s.operations.c.status.not_in(["completed", "confirmed", "cancelled", "failed", "rejected"])))).scalars().all()
        has_writes = (await conn.execute(select(s.operations.c.id).where(
            s.operations.c.workflow_id == wf["id"]))).first()
        if error:
            state = "needs_attention"
        elif "awaiting_approval" in pending:
            state = "awaiting_approval"
        elif any(status in ("unknown", "started") for status in pending):
            state = "needs_attention"
        elif "queued" in pending:
            state = "active"
        elif pending:
            state = "waiting_external_event"
        elif expects == "reply":
            state = "awaiting_user"
        elif expects == "confirmation" or has_writes or not wf["snapshot"]["read_only_auto_close"]:
            state = "awaiting_confirmation"
        else:
            state = "closed"
        message = {"message_id": uid(), "workflow_id": wf["id"], "sender": "assistant", "text": text,
                   "created_at": stamp(time.time())}
        await service.event(conn, wf, "assistant.message", message)
        await service.transition(conn, wf, state)
        await conn.execute(update(s.requests).where(s.requests.c.id == req["id"]).values(
            status="blocked" if error else "completed", result={"messages": [message]},
            error=error, completed=time.time()))
        await conn.execute(update(s.jobs).where(s.jobs.c.request_id == req["id"], s.jobs.c.kind == "agent").values(
            status="done", owner=None, lease_until=0))
        return True


async def close(service, client, workflow_id, command):
    payload = {**command.model_dump(mode="json"), "resource": workflow_id}
    async with service.tx() as conn:
        await row(conn, s.clients, s.clients.c.id == client["id"], lock=True)
        old = await service.replay(conn, client, command.external_request_id, payload)
        if old:
            return old["result"]
        wf, conv = await service.binding(conn, client, workflow_id, command.external_user_id,
                                        command.external_ticket_id, command.external_conversation_id)
        if wf["state"] == "closed":
            raise Fault(409, "WORKFLOW_CLOSED")
        if wf["revision"] != command.expected_revision:
            raise Fault(409, "REVISION_CONFLICT")
        pending = (await conn.execute(select(s.operations.c.id).where(s.operations.c.workflow_id == wf["id"],
            s.operations.c.status.not_in(["completed", "confirmed", "failed", "cancelled", "rejected"])))).first()
        busy = (await conn.execute(select(s.requests.c.id).where(s.requests.c.workflow_id == wf["id"],
            s.requests.c.status.in_(["accepted", "queued", "running"])))).first()
        if (pending or busy) and not (command.stop_tracking_only and command.reason == "resident_requested_stop_tracking"):
            raise Fault(409, "WORKFLOW_NOT_READY_TO_CLOSE")
        req = await service.add_request(conn, client, wf, payload, "close", "completed")
        await service.transition(conn, wf, "closed", reason=command.reason)
        await conn.execute(update(s.jobs).where(s.jobs.c.workflow_id == wf["id"], s.jobs.c.status != "done").values(
            status="cancelled", generation=s.jobs.c.generation + 1, owner=None, lease_until=0))
        await conn.execute(update(s.requests).where(s.requests.c.workflow_id == wf["id"],
            s.requests.c.status.in_(["queued", "running", "accepted"])).values(status="blocked", completed=time.time(),
                error={"code": "WORKFLOW_CLOSED", "retryable": False}))
        if wf["case_id"]:
            from ..db import cases
            await conn.execute(update(cases).where(cases.c.id == wf["case_id"]).values(status="finalized", updated_at=time.time()))
        await conn.execute(update(s.approvals).where(s.approvals.c.workflow_id == wf["id"],
            s.approvals.c.status == "pending").values(status="cancelled", revision=s.approvals.c.revision + 1))
        result = {"request_id": req["id"], "request_status": "completed", "external_ticket_id": command.external_ticket_id,
            "conversation_id": conv["id"], "workflow_id": wf["id"], "ticket_id": None,
            "state": "closed", "workflow_state": "closed", "next_action": "none",
            "revision": wf["revision"], "workflow_revision": wf["revision"], "reason": command.reason,
            "closed_at": stamp(wf["closed_at"])}
        await conn.execute(update(s.requests).where(s.requests.c.id == req["id"]).values(result=result, completed=time.time()))
        return result


async def decide(service, client, approval_id, command):
    payload = {**command.model_dump(mode="json"), "resource": approval_id}
    async with service.tx() as conn:
        await row(conn, s.clients, s.clients.c.id == client["id"], lock=True)
        old = await service.replay(conn, client, command.external_request_id, payload)
        if old:
            return old["result"]
        wf, _conv = await service.binding(conn, client, command.workflow_id, command.external_user_id,
                                         command.external_ticket_id, command.external_conversation_id)
        approval = await row(conn, s.approvals, s.approvals.c.id == approval_id,
                             s.approvals.c.workflow_id == wf["id"], lock=True)
        if not approval:
            raise Fault(404, "NOT_FOUND")
        if wf["state"] == "closed" or approval["status"] != "pending":
            raise Fault(409, "APPROVAL_NOT_PENDING")
        if approval["expires"] <= time.time():
            raise Fault(409, "APPROVAL_EXPIRED")
        if (approval["revision"], approval["arguments_hash"], approval["quote_ref"]) != (
                command.expected_revision, command.arguments_hash, command.quote_ref):
            raise Fault(409, "APPROVAL_ARGUMENTS_CONFLICT")
        req = await service.add_request(conn, client, wf, payload, "approval", "completed")
        status = "approved" if command.decision == "approve" else "rejected"
        await conn.execute(update(s.approvals).where(s.approvals.c.id == approval_id).values(
            status=status, revision=approval["revision"] + 1))
        await conn.execute(update(s.operations).where(s.operations.c.id == approval["operation_id"]).values(
            status="queued" if status == "approved" else "rejected"))
        await service.transition(conn, wf, "active" if status == "approved" else "awaiting_user")
        await service.event(conn, wf, "approval.resolved", {"approval_id": approval_id, "status": status})
        result = {"request_id": req["id"], "approval_id": approval_id, "status": status,
            "external_ticket_id": command.external_ticket_id, "workflow_id": wf["id"],
            "workflow_state": wf["state"], "next_action": service.next_action(wf),
            "accepted_at": stamp(time.time())}
        await conn.execute(update(s.requests).where(s.requests.c.id == req["id"]).values(result=result, completed=time.time()))
        if status == "approved":
            await service.enqueue(conn, wf, req, "operation", {"operation_id": approval["operation_id"]})
        return result
