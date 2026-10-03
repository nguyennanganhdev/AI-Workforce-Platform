"""Knowledge learned from management's answers to residents.

When management answers a question the knowledge base could not, the question and answer
become a candidate (memory_candidates). A curator model judges it; code then decides:

  rejected  - it holds personal data, or only makes sense for that one resident
  approved  - general and low risk: usable as knowledge without anyone clicking
  pending   - it states a fee, a rule or a safety instruction: management approves with one click

Approved candidates are exported to Markdown and published by the knowledge pipeline
(scripts/export_learned_knowledge.py), so retrieval, scopes and citations stay in one place.

Safety guidance for emergency replies uses the same approval: scripts/propose_emergency_guidance.py
proposes the text of each area's own document, and only an approved text is ever sent.
"""

import hashlib
import json
import logging
import re
from typing import Annotated, Literal
from uuid import NAMESPACE_URL, UUID, uuid5

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .reception_delegation import reception_agent
from .v3_auth import scoped_connection

log = logging.getLogger(__name__)
router = APIRouter(tags=["Vinhomes V3 learned knowledge"])
Scope = Annotated[tuple[AsyncConnection, str, bool], Depends(scoped_connection, scope="function")]
TENANT = "nullif(current_setting('app.tenant_id',true),'')::uuid"
# A wrong fee, rule or safety instruction harms residents, so these never publish without a person.
RISKY = re.compile(r"\d\s*(đồng|vnđ|vnd|k\b|nghìn|triệu|%)|phí|giá |tiền|phạt|cọc|cháy|nổ|điện giật|gas|thoát hiểm|sơ tán|cấp cứu",
                   re.IGNORECASE)
# Management of the unit whose workspace owns the candidate (or of the whole tenant).
MANAGES_CANDIDATE = """(:is_admin or exists (
    select 1 from scoped_user_roles r
    join tenant_memberships m on m.id=r.membership_id and m.tenant_id=r.tenant_id
    join access_scopes s on s.id=r.scope_id and s.tenant_id=r.tenant_id
    where m.user_id=:user_id and m.status='active' and r.role_code='management' and r.tenant_id=c.tenant_id
      and r.valid_from<=now() and (r.valid_to is null or r.valid_to>now())
      and (s.kind='tenant' or (s.kind='management' and s.management_unit_id=w.management_unit_id))))"""


# Candidates management decides on: learned answers and safety guidance for emergency replies.
REVIEWABLE = "(c.evidence ? 'sessionId' or c.evidence ? 'emergencyKind')"


async def approved_guidance(db: AsyncConnection, user_id: str, kind: str) -> dict[str, object] | None:
    """The safety text management approved for this kind of emergency where the resident lives.

    Shaped as the Reception graph expects it (graph/assessment.parse_request_policy). None when
    nothing is approved, or when the resident's homes are in different areas and the advice differs.
    """
    from .v3_session import CURRENT_HOME
    homes = (await db.execute(text(f"""
        select distinct b.id as building_id,b.zone_id,b.site_id from unit_residents ur
        join units u on u.id=ur.unit_id and u.tenant_id=ur.tenant_id
        join buildings b on b.id=u.building_id and b.tenant_id=u.tenant_id
        where ur.user_id=:user and ur.tenant_id={TENANT} and {CURRENT_HOME}
    """), {"user": user_id})).mappings().all()
    if len({home["zone_id"] for home in homes}) != 1:
        return None
    row = (await db.execute(text(f"""
        select c.id,c.proposed_text,c.proposal_revision,c.proposal_hash from memory_candidates c
        join access_scopes s on s.id=c.scope_id and s.tenant_id=c.tenant_id
        where c.tenant_id={TENANT} and c.status='approved' and c.evidence->>'emergencyKind'=:kind
          and (s.kind='tenant' or (s.kind='site' and s.site_id=:site) or (s.kind='zone' and s.zone_id=:zone)
            or (s.kind='building' and s.building_id=any(cast(:buildings as uuid[]))))
        order by array_position(array['building','zone','site','tenant'],s.kind),c.updated_at desc limit 1
    """), {"kind": kind, "site": homes[0]["site_id"], "zone": homes[0]["zone_id"],
           "buildings": [home["building_id"] for home in homes]})).mappings().first()
    if row is None:
        return None
    return {"approved": True, "answer": row["proposed_text"], "retrievalRunId": f"guidance:{row['id']}",
            "citations": [{"documentId": str(row["id"]), "version": str(row["proposal_revision"]),
                           "chunkId": row["proposal_hash"]}]}


async def propose_from_answer(db: AsyncConnection, session_id: UUID, workspace_id: object, scope_id: object,
                              question: str, answer: str, answered_by: str) -> UUID | None:
    """Record the answered question as a candidate. None when the workspace keeps no memory."""
    namespace = (await db.execute(text(f"""
        select id from memory_namespaces where tenant_id={TENANT} and kind='workspace'
          and workspace_id=:workspace and status='active' order by created_at limit 1
    """), {"workspace": workspace_id})).scalar_one_or_none()
    if namespace is None or scope_id is None:
        return None
    tenant = (await db.execute(text("select current_setting('app.tenant_id')"))).scalar_one()
    candidate_id = uuid5(NAMESPACE_URL, f"learned-answer:{tenant}:{session_id}")
    evidence = {"sessionId": str(session_id), "question": question, "answer": answer, "answeredBy": answered_by}
    await db.execute(text(f"""
        insert into memory_candidates(id,tenant_id,scope_id,namespace_id,proposed_text,evidence,pii_redacted,
          status,proposed_by_agent_id,reason,proposal_hash)
        values (:id,{TENANT},:scope,:namespace,:text,cast(:evidence as jsonb),false,'pending',:agent,
          'Câu trả lời của Ban quản lý cho câu hỏi kho tri thức chưa có.',:hash)
        on conflict (id) do nothing
    """), {"id": candidate_id, "scope": scope_id, "namespace": namespace, "agent": await reception_agent(db),
           "text": f"Hỏi: {question}\nĐáp: {answer}", "evidence": json.dumps(evidence, ensure_ascii=False),
           "hash": hashlib.sha256(json.dumps(evidence, sort_keys=True).encode()).hexdigest()})
    return candidate_id


def decide(verdict: dict, question: str, answer: str) -> tuple[str, str]:
    """(status, reason) for a judged candidate. Code has the last word on risk."""
    if verdict.get("personal_data") is True:
        return "rejected", "Chứa thông tin cá nhân."
    if verdict.get("generalizable") is not True:
        return "rejected", "Chỉ đúng cho riêng trường hợp của một cư dân."
    if verdict.get("risk") != "none" or RISKY.search(question + " " + answer):
        return "pending", "Nêu phí, quy định hoặc hướng dẫn an toàn: cần Ban quản lý duyệt."
    return "approved", "Tự động duyệt: câu trả lời chung, rủi ro thấp."


async def _review(db: AsyncConnection, candidate_id: UUID, status: str, reviewer: str, reason: str,
                  cleaned: tuple[str, str] | None = None) -> None:
    candidate = (await db.execute(text(f"""
        select proposal_revision,proposal_hash from memory_candidates
        where id=:id and tenant_id={TENANT} and status='pending' for update
    """), {"id": candidate_id})).mappings().first()
    if candidate is None:
        return
    if cleaned:
        # The curator's wording drops the asker's details; the original stays in the evidence.
        await db.execute(text("""
            update memory_candidates set proposed_text=:text,
              evidence=evidence||jsonb_build_object('question',cast(:q as text),'answer',cast(:a as text)) where id=:id
        """), {"id": candidate_id, "text": f"Hỏi: {cleaned[0]}\nĐáp: {cleaned[1]}", "q": cleaned[0], "a": cleaned[1]})
    if status == "pending":
        await db.execute(text("update memory_candidates set reason=:reason where id=:id"), {"id": candidate_id, "reason": reason})
        return
    await db.execute(text(f"""
        insert into knowledge_reviews(tenant_id,memory_candidate_id,decision,reviewer_user_id,reason,reviewed_at,subject_seq,subject_hash)
        values ({TENANT},:id,:decision,:reviewer,:reason,now(),:revision,:hash)
    """), {"id": candidate_id, "decision": "approve" if status == "approved" else "reject", "reviewer": reviewer,
           "reason": reason, "revision": candidate["proposal_revision"], "hash": candidate["proposal_hash"]})
    await db.execute(text("update memory_candidates set status=:status,pii_redacted=:clean,reason=:reason,updated_at=now() where id=:id"),
                     {"id": candidate_id, "status": status, "clean": status == "approved", "reason": reason})


async def curate(app, actor_id: str, candidate_id: UUID, question: str, answer: str) -> None:
    """After the answer is committed: ask the curator and apply the decision. Failure leaves it pending."""
    settings = app.state.settings
    if not settings.reception_url:
        return
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(f"{settings.reception_url}/v1/curations",
                                         headers={"Authorization": f"Bearer {settings.reception_service_token}"},
                                         json={"question": question, "answer": answer})
        response.raise_for_status()
        verdict = response.json()
        status, reason = decide(verdict, verdict.get("question") or question, verdict.get("answer") or answer)
        cleaned = (verdict["question"], verdict["answer"]) if status != "rejected" and isinstance(
            verdict.get("question"), str) and isinstance(verdict.get("answer"), str) else None
        async with app.state.engine.begin() as db:
            await db.execute(text("select set_config('app.tenant_id', :tenant, true), set_config('app.user_id', :user, true)"),
                             {"tenant": str(settings.tenant_id), "user": actor_id})
            await _review(db, candidate_id, status, actor_id, reason, cleaned)
    except Exception:  # noqa: BLE001 - an unjudged candidate simply waits for a person
        log.warning("Curator did not judge candidate %s", candidate_id)


@router.get("/knowledge/candidates", summary="Learned answers and safety guidance waiting for management's approval")
async def candidates(scope: Scope) -> dict[str, object]:
    rows = await scope[0].execute(text(f"""
        select c.id,c.status,c.reason,c.created_at,c.evidence->>'question' as question,c.evidence->>'answer' as answer
        from memory_candidates c
        join memory_namespaces n on n.id=c.namespace_id and n.tenant_id=c.tenant_id
        join workspaces w on w.id=n.workspace_id and w.tenant_id=n.tenant_id
        where c.tenant_id={TENANT} and c.status='pending' and {REVIEWABLE} and {MANAGES_CANDIDATE}
        order by c.created_at limit 100
    """), {"user_id": scope[1], "is_admin": scope[2]})
    return {"items": [dict(row) for row in rows.mappings()]}


class Decision(BaseModel):
    decision: Literal["approve", "reject"]


@router.post("/knowledge/candidates/{candidate_id}/decision", summary="Management approves or rejects a candidate")
async def decide_candidate(candidate_id: UUID, body: Decision, scope: Scope) -> dict[str, object]:
    allowed = (await scope[0].execute(text(f"""
        select c.status from memory_candidates c
        join memory_namespaces n on n.id=c.namespace_id and n.tenant_id=c.tenant_id
        join workspaces w on w.id=n.workspace_id and w.tenant_id=n.tenant_id
        where c.id=:id and c.tenant_id={TENANT} and {REVIEWABLE} and {MANAGES_CANDIDATE}
    """), {"id": candidate_id, "user_id": scope[1], "is_admin": scope[2]})).scalar_one_or_none()
    if allowed is None:
        raise HTTPException(403, "Management grant for this knowledge is required")
    status = "approved" if body.decision == "approve" else "rejected"
    if allowed != "pending":
        if allowed != status:
            raise HTTPException(409, "This candidate was already decided")
        return {"id": str(candidate_id), "status": allowed}
    await _review(scope[0], candidate_id, status, scope[1], "Ban quản lý duyệt." if status == "approved" else "Ban quản lý từ chối.")
    return {"id": str(candidate_id), "status": status}
