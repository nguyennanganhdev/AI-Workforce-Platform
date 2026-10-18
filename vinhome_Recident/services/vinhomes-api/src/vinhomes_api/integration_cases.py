"""What a client does without a person in front of it: take cases, propose plans, follow events, read the knowledge pack.

Contract: docs/domain/HOP_DONG_TICH_HOP.md sections 5 to 7. A case is a request handed to the one client that takes
cases; this module reuses the Reception/Supervisor exchange (idempotent, paged by cursor) and adds the plan proposal.
"""

import hashlib
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import AwareDatetime, BaseModel, Field, field_validator
from sqlalchemy import text

from .integration import CURRENT, Caller, CallerDep, _tenant_db
from .v3_audit import audit
from .v3_mutations import record_event
from .v3_reception_supervisor import (
    ReceptionToSupervisorMessage,
    SupervisorToReceptionResult,
    _decode_cursor,
    _encode_cursor,
    accept_supervisor_result,
)

router = APIRouter(prefix="/integration/v1", tags=["Integration v1"])
TENANT = "nullif(current_setting('app.tenant_id',true),'')::uuid"
Key = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=160)]


def settle_seconds() -> float:
    """Events are served once they are this old, so a slow commit cannot appear behind a cursor already handed out."""
    return float(os.getenv("VINHOMES_API_EVENT_SETTLE_SECONDS", "2"))


@asynccontextmanager
async def _db(request: Request, who: Caller, *, case_taker: bool = False):
    if who.kind != "client":
        raise HTTPException(403, "Use the client's own credentials for this")
    engine, tenant = await _tenant_db(request)
    async with engine.begin() as db:
        await db.execute(text("select set_config('app.tenant_id',:tenant,true)"), {"tenant": tenant})
        if case_taker:
            ok = (await db.execute(text(f"select 1 from integration_clients where tenant_id={TENANT} and id=:id and accepts_cases and status='active'"), {"id": who.client_id})).first()
            if ok is None:
                raise HTTPException(403, "This client does not take cases")
        yield db


async def client_db(request: Request, who: CallerDep):
    async with _db(request, who) as db:
        yield db, who


async def case_db(request: Request, who: CallerDep):
    async with _db(request, who, case_taker=True) as db:
        yield db, who


ClientScope = Annotated[tuple, Depends(client_db, scope="function")]
CaseScope = Annotated[tuple, Depends(case_db, scope="function")]


async def case_of(db, client_id: str, ticket_id: UUID, *, lock: bool = False) -> dict:
    row = (await db.execute(text(f"""
        select c.*,w.management_unit_id as workspace_management_unit_id from integration_cases c
        join workspaces w on w.id=c.workspace_id and w.tenant_id=c.tenant_id
        where c.tenant_id={TENANT} and c.ticket_id=:ticket and c.client_id=:client
        order by c.ticket_generation desc, c.created_at desc limit 1 {'for update of c' if lock else ''}
    """), {"ticket": ticket_id, "client": client_id})).mappings().first()
    if row is None:
        raise HTTPException(404, "No such case for this client")
    return dict(row)


# ---------- the inbox and the results ----------


@router.get("/cases/inbox")
async def inbox(scope: CaseScope, cursor: str | None = Query(default=None, max_length=512), limit: int = Query(50, ge=1, le=100)):
    db, who = scope
    after_at, after_id = _decode_cursor(cursor)
    rows = (await db.execute(text(f"""
        select m.id,m.payload,m.created_at from vh_reception_supervisor_messages m
        join integration_cases c on c.id=m.team_id and c.tenant_id=m.tenant_id
        where m.tenant_id={TENANT} and c.client_id=:client and m.direction='reception_to_supervisor'
          and (cast(:after_at as timestamptz) is null or (m.created_at,m.id)>(cast(:after_at as timestamptz),cast(:after_id as uuid)))
        order by m.created_at,m.id limit :limit
    """), {"client": who.client_id, "after_at": after_at, "after_id": after_id, "limit": limit + 1})).mappings().all()
    chosen = rows[:limit]
    return {"items": [ReceptionToSupervisorMessage.model_validate(r["payload"]).model_dump(mode="json", exclude_unset=True) for r in chosen],
            "next_cursor": _encode_cursor(dict(chosen[-1])) if chosen else cursor}


@router.get("/cases/{ticket_id}")
async def case(ticket_id: UUID, scope: CaseScope):
    db, who = scope
    found = await case_of(db, who.client_id, ticket_id)
    ticket = (await db.execute(text(f"""
        select t.id,t.code,t.status,t.version,t.priority,t.severity,t.is_emergency,t.request_kind,t.title,t.category_id,t.management_unit_id,
               t.response_due_at,t.resolution_due_at,t.reopen_count,u.code as unit_code
        from tickets t left join units u on u.id=t.unit_id and u.tenant_id=t.tenant_id where t.tenant_id={TENANT} and t.id=:id
    """), {"id": ticket_id})).mappings().one()
    plan = (await db.execute(text(f"""
        select id,status,version,title,proposal,proposed_by_client_id,created_at from vh_ticket_plans
        where tenant_id={TENANT} and ticket_id=:id order by created_at desc limit 1
    """), {"id": ticket_id})).mappings().first()
    return {"case_id": found["id"], "status": found["status"], "ticket_generation": found["ticket_generation"],
            "ticket": dict(ticket), "plan": dict(plan) if plan else None}


@router.post("/cases/{ticket_id}/results", status_code=201)
async def result(ticket_id: UUID, body: SupervisorToReceptionResult, scope: CaseScope, key: Key):
    db, who = scope
    found = await case_of(db, who.client_id, ticket_id, lock=True)
    if body.team_id != found["id"] or body.ticket_id != ticket_id:
        raise HTTPException(409, "The result names a different case")
    CURRENT.set({"delegation_id": None, "client_id": who.client_id, "user_id": None, "correlation_id": None, "idempotency_key": key, "tool": "staff.case.result", "level": "propose"})
    return await accept_supervisor_result(db, body, found, agent_id=who.client_id)


# ---------- proposing a plan ----------


class PlanProposal(BaseModel):
    ticket_version: int = Field(ge=0)
    summary: str = Field(min_length=1, max_length=300)
    steps: list[str] = Field(min_length=1, max_length=4)
    performer_staff_id: UUID | None = None
    appointment_at: AwareDatetime | None = None
    estimated_amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=2)
    estimated_duration_min: int | None = Field(default=None, ge=1, le=10080)
    cost_bearer: Literal["management", "resident", "warranty", "contractor"] = "resident"
    requires_outage: bool = False

    @field_validator("summary")
    @classmethod
    def summary_text(cls, value):
        if not value.strip():
            raise ValueError("The plan needs a summary")
        return value.strip()

    @field_validator("steps")
    @classmethod
    def step_text(cls, values):
        if any(not v.strip() or len(v.strip()) > 2000 for v in values) or len("\n".join(values)) > 1900:
            raise ValueError("Each step needs text; all steps together at most 1900 characters")
        return [v.strip() for v in values]


@router.post("/cases/{ticket_id}/plans", status_code=201)
async def propose_plan(ticket_id: UUID, body: PlanProposal, scope: CaseScope, key: Key):
    """The client proposes; management decides, then the resident, through the routes that already exist."""
    db, who = scope
    await case_of(db, who.client_id, ticket_id, lock=True)
    CURRENT.set({"delegation_id": None, "client_id": who.client_id, "user_id": None, "correlation_id": None, "idempotency_key": key, "tool": "staff.plans.propose", "level": "propose"})
    ticket = (await db.execute(text(f"select * from tickets where tenant_id={TENANT} and id=:id for update"), {"id": ticket_id})).mappings().one()
    fingerprint = hashlib.sha256(json.dumps(body.model_dump(mode="json", exclude={"ticket_version"}), sort_keys=True).encode()).hexdigest()
    old = (await db.execute(text(f"select * from vh_ticket_plans where tenant_id={TENANT} and ticket_id=:id and idempotency_key=:key"), {"id": ticket_id, "key": key})).mappings().first()
    if old:
        if old["request_hash"] != fingerprint or old["proposed_by_client_id"] != who.client_id:
            raise HTTPException(409, "That Idempotency-Key was used for a different plan")
        return dict(old)
    if ticket["version"] != body.ticket_version or ticket["status"] in ("closed", "cancelled", "resolved"):
        raise HTTPException(409, "The request changed or is final")
    if ticket["category_id"] is None:
        raise HTTPException(422, "The request must be classified before a plan can be proposed")
    if (await db.execute(text(f"select 1 from vh_ticket_plans where tenant_id={TENANT} and ticket_id=:id and status in ('management_pending','resident_pending')"), {"id": ticket_id})).first():
        raise HTTPException(409, "Decide the plan already waiting first")
    if body.appointment_at and body.appointment_at <= datetime.now(timezone.utc):
        raise HTTPException(422, "The appointment must be in the future")
    if body.performer_staff_id:
        staff = (await db.execute(text(f"""
            select sp.id from staff_profiles sp join users u on u.id=sp.user_id and u.status='active'
            where sp.id=:staff and sp.tenant_id={TENANT} and sp.active and sp.management_unit_id=:unit
              and exists(select 1 from staff_specialties ss where ss.staff_id=sp.id and ss.tenant_id=sp.tenant_id and ss.category_id=:category and ss.active)
              and exists(select 1 from staff_shifts sh where sh.staff_id=sp.id and sh.tenant_id=sp.tenant_id and sh.status='available'
                         and sh.starts_at<=coalesce(cast(:at as timestamptz),now()) and sh.ends_at>coalesce(cast(:at as timestamptz),now()))
        """), {"staff": body.performer_staff_id, "unit": ticket["management_unit_id"], "category": ticket["category_id"], "at": body.appointment_at})).first()
        if staff is None:
            raise HTTPException(422, "The performer must belong to the unit, have the specialty and be on shift then")
    proposal = {"summary": body.summary, "steps": body.steps, "performer_staff_id": str(body.performer_staff_id) if body.performer_staff_id else None,
                "appointment_at": body.appointment_at.isoformat() if body.appointment_at else None,
                "estimated_duration_min": body.estimated_duration_min, "cost_bearer": body.cost_bearer, "requires_outage": body.requires_outage}
    executable = [{"category_id": str(ticket["category_id"]), "description": "\n".join(f"{i}. {line}" for i, line in enumerate(body.steps, 1))}]
    plan = (await db.execute(text(f"""
        insert into vh_ticket_plans(tenant_id,ticket_id,proposed_by,proposed_by_client_id,title,steps,estimated_amount,status,idempotency_key,request_hash,proposal)
        values({TENANT},:ticket,null,:client,:title,cast(:steps as jsonb),:amount,'management_pending',:key,:hash,cast(:proposal as jsonb)) returning *
    """), {"ticket": ticket_id, "client": who.client_id, "title": body.summary, "steps": json.dumps(executable, ensure_ascii=False),
           "amount": body.estimated_amount, "key": key, "hash": fingerprint, "proposal": json.dumps(proposal, ensure_ascii=False)})).mappings().one()
    await record_event((db, None, False), dict(ticket), "plan.proposed", json.dumps({"planId": str(plan["id"]), "proposedBy": who.client_id}))
    await audit(db, None, "plan.proposed", "ticket_plan", str(plan["id"]), {"ticketId": str(ticket_id), "client": who.client_id})
    return dict(plan)


# ---------- following what happens ----------


def _pattern(topic: str) -> str:
    topic = topic.strip()
    return topic[:-1] + "%" if topic.endswith("*") else topic


@router.get("/events")
async def events(scope: ClientScope, after: int = Query(0, ge=0), topics: str | None = Query(default=None, max_length=500), limit: int = Query(100, ge=1, le=100)):
    db, _ = scope
    patterns = [_pattern(t) for t in topics.split(",") if t.strip()] if topics else None
    rows = (await db.execute(text(f"""
        select seq,event_id,topic,payload,schema_version,created_at from event_outbox
        where tenant_id={TENANT} and seq>:after and (cast(:patterns as text[]) is null or topic like any(cast(:patterns as text[])))
          and available_at<=clock_timestamp()-make_interval(secs=>:settle)
        order by seq limit :limit
    """), {"after": after, "patterns": patterns, "limit": limit, "settle": settle_seconds()})).mappings().all()
    return {"items": [{"seq": r["seq"], "event_id": r["event_id"], "topic": r["topic"], "occurred_at": r["created_at"],
                       "schema_version": r["schema_version"], "payload": r["payload"]} for r in rows],
            "next_cursor": str(rows[-1]["seq"]) if rows else str(after)}


# ---------- what the domain knows, for the client to learn ----------

DOC_KIND = {"fee_table": "fee_table", "faq": "faq"}


@router.get("/knowledge/pack")
async def knowledge_pack(scope: ClientScope, audience: Literal["resident", "staff", "management"] = "resident", since: str | None = Query(default=None, max_length=100)):
    db, who = scope
    persona = "resident" if audience == "resident" else "staff"
    allowed = (await db.execute(text(f"select levels from integration_clients where tenant_id={TENANT} and id=:id"), {"id": who.client_id})).scalar_one()
    if not allowed.get(persona):
        raise HTTPException(403, "This client may not read that audience's knowledge")
    def zone_scope(column: str) -> str:
        return f"jsonb_build_object('zone_codes', coalesce((select jsonb_agg(z.code) from zones z where z.id={column} and z.tenant_id=d.tenant_id), '[]'::jsonb))"

    docs = []
    for row in (await db.execute(text(f"""
        select 'handbook:'||d.id as id,'handbook' as kind,d.title,d.body_md,d.language,d.audience,d.effective_from::text as effective_from,d.effective_to::text as effective_to,
               {zone_scope('d.zone_id')} as scope,'handbook_articles/'||d.id as source
        from handbook_articles d where d.tenant_id={TENANT} and d.status='published' and :aud=any(d.audience)
          and d.effective_from<=current_date and (d.effective_to is null or d.effective_to>=current_date) order by d.id
    """), {"aud": audience})).mappings():
        docs.append(dict(row))
    for row in (await db.execute(text(f"""
        select 'policy:'||d.id as id,d.kind as raw_kind,d.title,d.body_md,d.language,d.audience,d.effective_from::text as effective_from,d.effective_to::text as effective_to,
               {zone_scope('d.zone_id')} || jsonb_build_object('unit_kinds', case when d.unit_kind is null then '[]'::jsonb else jsonb_build_array(d.unit_kind) end) as scope,
               'policy_documents/'||d.id as source
        from policy_documents d where d.tenant_id={TENANT} and :aud=any(d.audience)
          and d.effective_from<=current_date and (d.effective_to is null or d.effective_to>=current_date) order by d.id
    """), {"aud": audience})).mappings():
        item = dict(row)
        item["kind"] = DOC_KIND.get(item.pop("raw_kind"), "policy")
        docs.append(item)
    if audience in ("resident", "staff", "management"):
        for row in (await db.execute(text(f"""
            select 'announcement:'||a.id as id,'announcement' as kind,a.title,a.body_md,'vi' as language,
                   a.published_at::text as effective_from,coalesce(a.expire_at,a.effective_to)::text as effective_to,
                   jsonb_build_object('zone_ids', to_jsonb(a.zone_ids), 'building_ids', to_jsonb(a.building_ids)) as scope,
                   'announcements/'||a.id as source
            from announcements a where a.tenant_id={TENANT} and a.status='published' and a.published_at<=now() and (a.expire_at is null or a.expire_at>now()) order by a.id
        """))).mappings():
            item = dict(row)
            item["audience"] = ["resident", "staff", "management"]
            docs.append(item)
    for item in docs:
        material = json.dumps([item["title"], item["body_md"], item["scope"], item["audience"], item["effective_from"], item["effective_to"]], sort_keys=True, ensure_ascii=False)
        item["checksum"] = "sha256:" + hashlib.sha256(material.encode()).hexdigest()
    version = "sha256:" + hashlib.sha256("|".join(sorted(f"{d['id']}={d['checksum']}" for d in docs)).encode()).hexdigest()
    base = {"version": version, "generated_at": datetime.now(timezone.utc).isoformat(), "audience": audience}
    if since == version:
        return {**base, "unchanged": True, "documents": []}
    return {**base, "unchanged": False, "documents": docs}


@router.get("/openapi.json", include_in_schema=False)
async def openapi_slice(request: Request, who: CallerDep):
    """The part of the API a client may use, for generating a client library."""
    from .integration import TOOLS
    spec = request.app.openapi()
    wanted = {(t.method.lower(), t.path) for t in TOOLS}
    paths = {}
    for path, item in spec["paths"].items():
        kept = {m: op for m, op in item.items() if path.startswith("/integration/v1") or (m, path) in wanted}
        if kept:
            paths[path] = kept
    return {"openapi": spec["openapi"], "info": {**spec["info"], "title": "Vinhomes integration API v1"}, "paths": paths, "components": spec.get("components", {})}
