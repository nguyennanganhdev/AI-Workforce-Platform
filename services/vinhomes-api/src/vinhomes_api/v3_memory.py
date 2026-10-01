"""Admin review of proposed long-term memory content."""

from typing import Annotated, Literal
from uuid import UUID, uuid5, NAMESPACE_URL
import hashlib
import json
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .v3_auth import scoped_connection
from .v3_mutations import visible_ticket, management_access, record_event


router = APIRouter(tags=["Vinhomes V3 memory review"])
Scope = Annotated[tuple[AsyncConnection, str, bool], Depends(scoped_connection)]


def _require_admin(scope: Scope) -> None:
    if not scope[2]:
        raise HTTPException(403, "Platform admin required")


class MemoryReview(BaseModel):
    decision: Literal["approve", "reject"]
    reason: str = Field(min_length=1, max_length=2000)


@router.get("/memory/namespaces")
async def namespaces(scope: Scope, ticket_id: UUID = Query(..., alias="ticketId")) -> dict[str, object]:
    ticket = await visible_ticket(scope, ticket_id)
    if not await management_access(scope, ticket):
        raise HTTPException(403, "Responsible management required")
    result = await scope[0].execute(text("""
        select n.id,n.namespace_key,n.purpose,w.name from memory_namespaces n
        join workspaces w on w.id=n.workspace_id and w.tenant_id=n.tenant_id
        where n.kind='workspace' and n.status='active' and w.status='active'
          and w.management_unit_id=:management order by n.namespace_key
    """), {"management": ticket["management_unit_id"]})
    return {"items": [dict(row) for row in result.mappings()]}


class MemoryProposal(BaseModel):
    namespace_id: UUID
    proposed_text: str = Field(min_length=1, max_length=10000)
    reason: str = Field(min_length=1, max_length=2000)
    pii_redacted: bool = False
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=30)
    idempotency_key: str = Field(min_length=1, max_length=160)


@router.post("/tickets/{ticket_id}/memory-candidates", status_code=201)
async def propose_memory(ticket_id: UUID, body: MemoryProposal, scope: Scope) -> dict[str, object]:
    ticket = await visible_ticket(scope, ticket_id, lock=True)
    if not await management_access(scope, ticket):
        raise HTTPException(403, "Responsible management required")
    allowed = await namespaces(scope, ticket_id)
    if str(body.namespace_id) not in {str(row['id']) for row in allowed['items']}:
        raise HTTPException(403, "Memory namespace is outside the ticket workspace")
    affected_scope = await scope[0].execute(text("""
        select id from access_scopes where kind='management' and management_unit_id=:management
    """), {"management": ticket["management_unit_id"]})
    scope_id = affected_scope.scalar_one_or_none()
    if scope_id is None:
        raise HTTPException(409, "Memory scope is missing")
    for evidence_id in body.evidence_ids:
        evidence = await scope[0].execute(text("select 1 from evidence_items where id=:id and ticket_id=:ticket and status='active'"), {"id": evidence_id, "ticket": ticket_id})
        if evidence.first() is None:
            raise HTTPException(422, "Evidence does not belong to this ticket")
    redacted = re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '[email]', body.proposed_text)
    redacted = re.sub(r'(?<!\w)\+?\d[\d .()-]{7,}\d(?!\w)', '[phone]', redacted)
    evidence = {"evidenceIds": [str(item) for item in body.evidence_ids], "sourceTicketId": str(ticket_id)}
    fingerprint = hashlib.sha256(json.dumps({"text": redacted, "evidence": evidence, "reason": body.reason, "namespace": str(body.namespace_id), "piiRedacted": body.pii_redacted}, sort_keys=True).encode()).hexdigest()
    tenant = await scope[0].execute(text("select current_setting('app.tenant_id')"))
    candidate_id = uuid5(NAMESPACE_URL, f"memory:{tenant.scalar_one()}:{ticket_id}:{scope[1]}:{body.idempotency_key}")
    previous = await scope[0].execute(text("select id,status,proposal_hash from memory_candidates where id=:id"), {"id": candidate_id})
    old = previous.mappings().first()
    if old:
        if old["proposal_hash"] != fingerprint:
            raise HTTPException(409, "Memory key already used with different content")
        return dict(old)
    result = await scope[0].execute(text("""
        insert into memory_candidates(id,tenant_id,source_ticket_id,scope_id,namespace_id,proposed_text,evidence,pii_redacted,status,reason,proposal_hash)
        values (:id,nullif(current_setting('app.tenant_id',true),'')::uuid,:ticket,:scope,:namespace,:text,cast(:evidence as jsonb),:pii,'pending',:reason,:hash)
        returning id,status,proposed_text,pii_redacted,created_at
    """), {"id": candidate_id, "ticket": ticket_id, "scope": scope_id, "namespace": body.namespace_id, "text": redacted, "evidence": json.dumps(evidence), "pii": body.pii_redacted, "reason": body.reason, "hash": fingerprint})
    await record_event(scope, ticket, "memory.proposed", json.dumps({"candidateId": str(candidate_id)}))
    return dict(result.mappings().one())


@router.get("/admin/memory-candidates", summary="List proposed memory for admin review")
async def memory_candidates(scope: Scope, status: Literal["pending", "approved", "rejected"] = "pending",
                            limit: int = Query(50, ge=1, le=100)) -> dict[str, object]:
    _require_admin(scope)
    result = await scope[0].execute(text("""
        select id, source_ticket_id, scope_id, namespace_id, proposed_text,
               pii_redacted, status, reason, proposal_revision, created_at
        from memory_candidates where status=:status
          and tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
        order by created_at, id limit :limit
    """), {"status": status, "limit": limit})
    return {"items": [dict(row) for row in result.mappings()]}


@router.post("/admin/memory-candidates/{candidate_id}/review",
             summary="Approve or reject a memory candidate")
async def review_memory_candidate(candidate_id: UUID, body: MemoryReview,
                                  scope: Scope) -> dict[str, object]:
    _require_admin(scope)
    db, actor_id, _ = scope
    result = await db.execute(text("""
        select id, status, pii_redacted, proposal_revision, proposal_hash
        from memory_candidates where id=:id
          and tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
        for update
    """), {"id": candidate_id})
    candidate = result.mappings().first()
    if candidate is None:
        raise HTTPException(404, "Memory candidate not found")
    if candidate["status"] != "pending":
        raise HTTPException(409, "Memory candidate has already been reviewed")
    if body.decision == "approve" and not candidate["pii_redacted"]:
        raise HTTPException(409, "Remove personal data before approval")
    review = await db.execute(text("""
        insert into knowledge_reviews
          (tenant_id, memory_candidate_id, decision, reviewer_user_id, reason,
           reviewed_at, subject_seq, subject_hash)
        values (nullif(current_setting('app.tenant_id', true), '')::uuid,
                :candidate_id, :decision, :actor_id, :reason, now(), :revision, :hash)
        returning id, decision, reviewed_at
    """), {"candidate_id": candidate_id, "decision": body.decision,
           "actor_id": actor_id, "reason": body.reason,
           "revision": candidate["proposal_revision"], "hash": candidate["proposal_hash"]})
    await db.execute(text("""
        update memory_candidates set status=:status, updated_at=now() where id=:id
    """), {"id": candidate_id,
           "status": "approved" if body.decision == "approve" else "rejected"})
    return {"candidateId": candidate_id, **dict(review.mappings().one())}
