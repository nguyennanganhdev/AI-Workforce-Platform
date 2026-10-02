"""Versioned consumer contract over the canonical business API (draft != ticket)."""

from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict
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


class KnowledgeAsk(BaseModel):
    model_config = ConfigDict(extra="forbid")
    knowledgeBaseId: UUID
    scopeId: UUID | None = None


@router.post("/internal/reception/v1/knowledge-authorization")
async def knowledge_authorization(ask: KnowledgeAsk, scope: DelegatedScope):
    db, row = scope
    grant = await db.execute(text(f"""
        select 1 from agent_knowledge_grants g join knowledge_bases k
          on k.tenant_id=g.tenant_id and k.id=g.knowledge_base_id
        where g.tenant_id={TENANT} and g.agent_id=:agent and k.id=:kb and k.status='active'
    """), {"agent": row["agent_id"], "kb": ask.knowledgeBaseId})
    if grant.first() is None:
        raise HTTPException(403, "Agent has no active knowledge grant")
    residences = (await db.execute(text(f"""
        select distinct s.id as scope_id,b.name,b.id as building_id,b.site_id,b.zone_id
        from unit_residents ur join units u on u.tenant_id=ur.tenant_id and u.id=ur.unit_id
        join buildings b on b.tenant_id=u.tenant_id and b.id=u.building_id
        join sites st on st.tenant_id=b.tenant_id and st.id=b.site_id
        join access_scopes s on s.tenant_id=b.tenant_id and s.kind='building' and s.building_id=b.id
        where ur.tenant_id={TENANT} and ur.user_id=:actor and ur.verification_status='verified'
          and ur.valid_from<=now() and (ur.valid_to is null or ur.valid_to>now())
          and u.status='active' and b.status='active' and st.status='active'
    """), {"actor": row["user_id"]})).mappings().all()
    if not residences:
        raise HTTPException(403, "Verified current residence required")
    if ask.scopeId is None and len(residences) > 1:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=409, content={"error": {"code": "scope_required",
            "message": "Chọn tòa nhà cần tra cứu.", "choices": [
                {"scopeId": str(r["scope_id"]), "label": r["name"]} for r in residences]}})
    selected = next((r for r in residences if ask.scopeId is None or r["scope_id"] == ask.scopeId), None)
    if selected is None:
        raise HTTPException(403, "Scope is not a verified residence")
    # Only physical ancestors. Management scope needs explicit coverage policy; do not assume it.
    ancestors = (await db.execute(text(f"""
        select id from access_scopes where tenant_id={TENANT} and
          (kind='tenant' or (kind='site' and site_id=:site) or (kind='zone' and zone_id=:zone))
    """), {"site": selected["site_id"], "zone": selected["zone_id"]})).scalars().all()
    return {"ok": True, "knowledgeBaseId": str(ask.knowledgeBaseId), "context": {
        "tenantId": str(row["tenant_id"]), "userId": row["user_id"], "roleCodes": ["resident"],
        "targetScopeId": str(selected["scope_id"]), "ancestorScopeIds": [str(s) for s in ancestors],
        "agentRunId": str(row["run_id"]), "principalId": str(row["principal_id"]),
        "bindingId": str(row["binding_id"])}}
