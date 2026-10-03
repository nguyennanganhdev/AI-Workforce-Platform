"""Human review workflow for policy-bound V3 triage decisions."""

import json
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .v3_auth import scoped_connection
from .v3_mutations import record_event, visible_ticket

router = APIRouter(tags=["Vinhomes V3 triage"])
Scope = Annotated[tuple[AsyncConnection, str, bool], Depends(scoped_connection, scope="function")]


async def can_review(scope: Scope, required_scope_id: UUID) -> bool:
    if scope[2]:
        return True
    grant = await scope[0].execute(text("""
        select 1 from scoped_user_roles r
        join tenant_memberships m on m.id=r.membership_id and m.tenant_id=r.tenant_id
        join access_scopes s on s.id=r.scope_id and s.tenant_id=r.tenant_id
        join access_scopes target on target.id=:scope_id and target.tenant_id=r.tenant_id
        left join buildings b on b.id=target.building_id and b.tenant_id=r.tenant_id
        where m.user_id=:user_id
          and m.status='active' and r.role_code='management'
          and r.valid_from<=now() and (r.valid_to is null or r.valid_to>now())
          and (s.kind='tenant' or s.id=target.id
               or (s.kind='site' and s.site_id=b.site_id)
               or (s.kind='zone' and s.zone_id=b.zone_id))
        limit 1
    """), {"scope_id": required_scope_id, "user_id": scope[1]})
    return grant.first() is not None


class TriageProposal(BaseModel):
    assessment_id: UUID
    severity: Literal["unknown", "minor", "moderate", "major", "critical", "not_applicable"]
    priority: Literal["low", "normal", "high", "critical"]
    is_emergency: bool = False
    reason: str = Field(min_length=1)
    review_reason: Literal["unknown_facts", "conflict", "downgrade",
                           "emergency_override", "overdue_review"] = "unknown_facts"
    ticket_version: int = Field(ge=0)
    idempotency_key: str = Field(min_length=1, max_length=200)


@router.post("/tickets/{ticket_id}/triage-decisions", status_code=201,
             summary="Submit a policy-bound triage proposal for human review")
async def propose_triage(ticket_id: UUID, body: TriageProposal,
                         scope: Scope) -> dict[str, object]:
    if body.is_emergency and body.priority != "critical":
        raise HTTPException(422, "Emergency triage must have critical priority")
    ticket = await visible_ticket(scope, ticket_id, lock=True)
    existing = await scope[0].execute(text("""
        select id from ticket_triage_decisions
        where ticket_id=:ticket_id and idempotency_key=:key
    """), {"ticket_id": ticket_id, "key": body.idempotency_key})
    replay = existing.scalar_one_or_none()
    if replay is not None:
        return {"decisionId": replay, "ticketId": ticket_id, "replayed": True}
    if ticket["version"] != body.ticket_version:
        raise HTTPException(409, "Ticket version changed; reload before triage")
    assessment = await scope[0].execute(text("""
        select id from ticket_assessments
        where id=:id and ticket_id=:ticket_id and ticket_generation=:generation
    """), {"id": body.assessment_id, "ticket_id": ticket_id,
           "generation": ticket["reopen_count"]})
    if assessment.first() is None:
        raise HTTPException(422, "Current-generation assessment is required")
    binding = await scope[0].execute(text("""
        select b.id, b.scope_id, b.policy_version_id, p.review_timeout_seconds
        from triage_policy_bindings b
        join triage_policy_versions p on p.id=b.policy_version_id and p.tenant_id=b.tenant_id
        join access_scopes s on s.id=b.scope_id and s.tenant_id=b.tenant_id
        where b.domain_id=:domain_id and b.request_kind=:request_kind
          and (b.category_id is null or b.category_id=cast(:category_id as uuid))
          and b.status='active' and p.status='published'
          and b.valid_from<=now() and (b.valid_to is null or b.valid_to>now())
          and (s.kind='tenant' or (s.kind='site' and s.site_id=:site_id)
               or (s.kind='building' and s.building_id=:building_id))
        order by case s.kind when 'building' then 3 when 'site' then 2 else 1 end desc,
                 case when b.category_id is null then 0 else 1 end desc,
                 b.valid_from desc limit 1
    """), {"domain_id": ticket["domain_id"], "request_kind": ticket["request_kind"],
           "category_id": ticket["category_id"], "site_id": ticket["site_id"],
           "building_id": ticket["building_id"]})
    policy = binding.mappings().first()
    if policy is None:
        raise HTTPException(409, "No published triage policy is active for this ticket")
    seq_result = await scope[0].execute(text("""
        select coalesce(max(decision_seq),0)+1 from ticket_triage_decisions
        where ticket_id=:ticket_id
    """), {"ticket_id": ticket_id})
    seq = seq_result.scalar_one()
    decision = await scope[0].execute(text("""
        insert into ticket_triage_decisions
          (tenant_id,ticket_id,ticket_generation,decision_seq,assessment_id,
           policy_binding_id,policy_version_id,previous_applied_id,outcome,
           decision_mode,severity,priority,is_emergency,evaluation_trace,
           reason,basis_ticket_version,decided_at,idempotency_key)
        values (nullif(current_setting('app.tenant_id',true),'')::uuid,
          :ticket_id,:generation,:seq,:assessment_id,:binding_id,:policy_version_id,
          :previous_id,'review_required','provisional',:severity,:priority,
          :is_emergency,cast(:trace as jsonb),:reason,:version,now(),:key)
        returning id
    """), {"ticket_id": ticket_id, "generation": ticket["reopen_count"],
           "seq": seq, "assessment_id": body.assessment_id,
           "binding_id": policy["id"], "policy_version_id": policy["policy_version_id"],
           "previous_id": ticket["current_triage_decision_id"],
           "severity": body.severity, "priority": body.priority,
           "is_emergency": body.is_emergency,
           "trace": json.dumps({"source": "human_proposal"}),
           "reason": body.reason, "version": ticket["version"],
           "key": body.idempotency_key})
    decision_id = decision.scalar_one()
    review = await scope[0].execute(text("""
        insert into ticket_triage_reviews
          (tenant_id,ticket_id,ticket_generation,assessment_id,pending_decision_id,
           required_scope_id,reason_code,status,due_at)
        values (nullif(current_setting('app.tenant_id',true),'')::uuid,
          :ticket_id,:generation,:assessment_id,:decision_id,:scope_id,
          :reason_code,'pending',now()+make_interval(secs=>:timeout))
        returning id
    """), {"ticket_id": ticket_id, "generation": ticket["reopen_count"],
           "assessment_id": body.assessment_id, "decision_id": decision_id,
           "scope_id": policy["scope_id"], "timeout": policy["review_timeout_seconds"],
           "reason_code": body.review_reason})
    review_id = review.scalar_one()
    await scope[0].execute(text("""
        update tickets set triage_status='review_required' where id=:id
    """), {"id": ticket_id})
    await record_event(scope, ticket, "triage.review_requested",
                       json.dumps({"decisionId": str(decision_id), "reviewId": str(review_id)}))
    return {"decisionId": decision_id, "reviewId": review_id, "status": "review_required"}


class TriageReviewDecision(BaseModel):
    approve: bool
    note: str = Field(min_length=1)
    ticket_version: int = Field(ge=0)


@router.get("/triage-reviews", summary="Pending triage reviews")
async def list_triage_reviews(scope: Scope) -> dict[str, object]:
    from .v3_auth import TICKET_VISIBILITY
    result = await scope[0].execute(text(f"""
        select r.id, r.ticket_id, r.assessment_id, r.pending_decision_id,
               r.required_scope_id, r.status, r.due_at, t.code as ticket_code
        from ticket_triage_reviews r
        join tickets t on t.id=r.ticket_id and t.tenant_id=r.tenant_id
        where r.status='pending' and {TICKET_VISIBILITY}
          and (:is_admin or exists (
            select 1 from scoped_user_roles sr
            join tenant_memberships m on m.id=sr.membership_id and m.tenant_id=sr.tenant_id
            join access_scopes s on s.id=sr.scope_id and s.tenant_id=sr.tenant_id
            join access_scopes target on target.id=r.required_scope_id and target.tenant_id=sr.tenant_id
            left join buildings b on b.id=target.building_id and b.tenant_id=sr.tenant_id
            where m.user_id=:user_id
              and m.status='active' and sr.role_code='management'
              and sr.valid_from<=now() and (sr.valid_to is null or sr.valid_to>now())
              and (s.kind='tenant' or s.id=target.id
                   or (s.kind='site' and s.site_id=b.site_id)
                   or (s.kind='zone' and s.zone_id=b.zone_id))))
        order by r.due_at limit 100
    """), {"user_id": scope[1], "is_admin": scope[2]})
    return {"items": [dict(row) for row in result.mappings().all()]}


@router.post("/triage-reviews/{review_id}/decision", summary="Approve or reject a triage proposal")
async def decide_triage_review(review_id: UUID, body: TriageReviewDecision,
                               scope: Scope) -> dict[str, object]:
    found = await scope[0].execute(text("""
        select ticket_id from ticket_triage_reviews where id=:id
    """), {"id": review_id})
    ticket_id = found.scalar_one_or_none()
    if ticket_id is None:
        raise HTTPException(404, "Triage review not found")
    ticket = await visible_ticket(scope, ticket_id, lock=True)
    if ticket["version"] != body.ticket_version:
        raise HTTPException(409, "Ticket version changed; reload before review")
    result = await scope[0].execute(text("""
        select r.*, d.policy_binding_id, d.policy_version_id,
               d.severity, d.priority, d.is_emergency, d.reason
        from ticket_triage_reviews r
        join ticket_triage_decisions d on d.id=r.pending_decision_id and d.tenant_id=r.tenant_id
        where r.id=:id for update of r
    """), {"id": review_id})
    review = result.mappings().one()
    if review["status"] != "pending" or review["due_at"] <= __import__("datetime").datetime.now(review["due_at"].tzinfo):
        raise HTTPException(409, "Triage review expired or already decided")
    if not await can_review(scope, review["required_scope_id"]):
        raise HTTPException(403, "Management grant for this review scope is required")
    if review["ticket_generation"] != ticket["reopen_count"]:
        raise HTTPException(409, "Ticket generation changed; review is stale")
    applied_id = None
    if body.approve:
        seq_result = await scope[0].execute(text("""
            select coalesce(max(decision_seq),0)+1 from ticket_triage_decisions
            where ticket_id=:ticket_id
        """), {"ticket_id": ticket_id})
        seq = seq_result.scalar_one()
        applied = await scope[0].execute(text("""
            insert into ticket_triage_decisions
              (tenant_id,ticket_id,ticket_generation,decision_seq,assessment_id,
               policy_binding_id,policy_version_id,previous_applied_id,review_id,
               outcome,decision_mode,severity,priority,is_emergency,evaluation_trace,
               reason,basis_ticket_version,applied_ticket_version,decided_at,
               approved_by,idempotency_key)
            values (nullif(current_setting('app.tenant_id',true),'')::uuid,
              :ticket_id,:generation,:seq,:assessment_id,:binding_id,:policy_version_id,
              :previous_id,:review_id,'applied','human_confirmed',
              :severity,:priority,:is_emergency,cast(:trace as jsonb),
              :reason,:version,:applied_version,now(),:user_id,:key)
            returning id
        """), {"ticket_id": ticket_id, "generation": ticket["reopen_count"],
               "seq": seq, "assessment_id": review["assessment_id"],
               "binding_id": review["policy_binding_id"],
               "policy_version_id": review["policy_version_id"],
               "previous_id": ticket["current_triage_decision_id"],
               "review_id": review_id, "severity": review["severity"],
               "priority": review["priority"], "is_emergency": review["is_emergency"],
               "trace": json.dumps({"source": "human_review"}),
               "reason": body.note, "version": ticket["version"],
               "applied_version": ticket["version"] + 1,
               "user_id": scope[1], "key": f"review:{review_id}"})
        applied_id = applied.scalar_one()
        await scope[0].execute(text("""
            update tickets set severity=:severity,priority=:priority,
              is_emergency=:is_emergency,triage_status='confirmed',
              current_triage_decision_id=:decision_id where id=:ticket_id
        """), {"ticket_id": ticket_id, "severity": review["severity"],
               "priority": review["priority"], "is_emergency": review["is_emergency"],
               "decision_id": applied_id})
    else:
        await scope[0].execute(text("""
            update tickets set triage_status='pending' where id=:ticket_id
        """), {"ticket_id": ticket_id})
    await scope[0].execute(text("""
        update ticket_triage_reviews set status=:status,decided_by=:user_id,
          decided_at=now(),decision_note=:note,result_decision_id=:decision_id,
          version=version+1,updated_at=now() where id=:id
    """), {"id": review_id, "status": "approved" if body.approve else "rejected",
           "user_id": scope[1], "note": body.note, "decision_id": applied_id})
    await record_event(scope, ticket, "triage.review_resolved",
                       json.dumps({"reviewId": str(review_id), "approved": body.approve,
                                   "decisionId": str(applied_id) if applied_id else None}))
    return {"reviewId": review_id, "status": "approved" if body.approve else "rejected",
            "decisionId": applied_id}
