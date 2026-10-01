"""Admin review of proposed long-term memory content."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .v3_auth import scoped_connection


router = APIRouter(tags=["Vinhomes V3 memory review"])
Scope = Annotated[tuple[AsyncConnection, str, bool], Depends(scoped_connection, scope="function")]


def _require_admin(scope: Scope) -> None:
    if not scope[2]:
        raise HTTPException(403, "Platform admin required")


class MemoryReview(BaseModel):
    decision: Literal["approve", "reject"]
    reason: str = Field(min_length=1, max_length=2000)


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
