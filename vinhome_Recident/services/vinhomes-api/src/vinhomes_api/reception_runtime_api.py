"""Versioned consumer contract over the canonical business API (draft != ticket)."""

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from .reception_delegation import DelegatedScope, TENANT
from .v3_reception_operations import OperationCall, execute, reconcile

router = APIRouter(tags=["Reception runtime v1"])


async def _bound_call(call, scope):
    db, row = scope
    context = {"tenantId": str(row["tenant_id"]), "principalId": str(row["principal_id"]),
               "bindingId": str(row["binding_id"]), "runId": str(row["run_id"])}
    if any(k in call.context and call.context[k] != v for k, v in context.items()):
        raise HTTPException(403, "Operation context differs from delegated authority")
    channel = call.input.get("channel_id")
    if channel is not None and channel != row["channel_id"]:
        raise HTTPException(403, "Channel differs from delegated binding")
    ticket = call.input.get("ticket_id")
    message = call.input.get("message") or call.input.get("schema_v2")
    if isinstance(message, dict):
        if ticket is not None and str(ticket) != str(message.get("ticket_id")):
            raise HTTPException(403, "Conflicting ticket context")
        ticket = message.get("ticket_id")
    if ticket is not None:
        # The existing resident API also checks ticket ownership. Add the narrower run boundary:
        # only tickets opened from this conversation.
        allowed = await db.execute(text(f"select 1 from tickets where tenant_id={TENANT} and channel_id=:channel and id=cast(:ticket as uuid)"),
                                   {"channel": row["channel_id"], "ticket": str(ticket)})
        if allowed.first() is None:
            raise HTTPException(403, "Ticket differs from delegated binding")
    # Internal legacy identity means user id. The v1 response carries the canonical principal id.
    return call.model_copy(update={"context": {**call.context, **context, "principalId": row["user_id"]}}), context


@router.post("/internal/reception/v1/execute")
async def execute_v1(call: OperationCall, scope: DelegatedScope):
    bound, context = await _bound_call(call, scope)
    result = await execute(bound, (scope[0], scope[1]["user_id"]))
    return {"contractVersion": "reception.v1", "operation": call.operation,
            "status": "completed", "context": context, "result": result}


@router.post("/internal/reception/v1/reconcile")
async def reconcile_v1(call: OperationCall, scope: DelegatedScope):
    bound, context = await _bound_call(call, scope)
    result = await reconcile(bound, (scope[0], scope[1]["user_id"]))
    return {"contractVersion": "reception.v1", "context": context, **result}
