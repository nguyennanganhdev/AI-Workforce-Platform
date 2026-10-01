"""Transactional commands for the V3 ticket and work-order workflow."""

import json
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .v3_auth import TICKET_VISIBILITY, scoped_connection

router = APIRouter(tags=["Vinhomes V3 commands"])
Scope = Annotated[tuple[AsyncConnection, str, bool], Depends(scoped_connection, scope="function")]


def actor_params(scope: Scope) -> dict[str, object]:
    return {"user_id": scope[1], "is_admin": scope[2]}


async def visible_ticket(scope: Scope, ticket_id: UUID, *, lock: bool = False) -> dict[str, object]:
    result = await scope[0].execute(text(f"""
        select t.id, t.status, t.version, t.last_event_seq, t.domain_id,
               t.building_id, t.site_id, t.zone_id, t.management_unit_id,
               t.category_id, t.triage_status, t.request_kind, t.reopen_count,
               t.current_triage_decision_id
        from tickets t where t.id=:ticket_id and {TICKET_VISIBILITY}
        {"for update of t" if lock else ""}
    """), {**actor_params(scope), "ticket_id": ticket_id})
    row = result.mappings().first()
    if row is None:
        raise HTTPException(404, "Ticket not found or outside your scope")
    return dict(row)


async def management_access(scope: Scope, ticket: dict[str, object]) -> bool:
    if scope[2]:
        return True
    grant = await scope[0].execute(text("""
        select 1 from scoped_user_roles r
        join tenant_memberships m on m.id=r.membership_id and m.tenant_id=r.tenant_id
        join access_scopes s on s.id=r.scope_id and s.tenant_id=r.tenant_id
        where m.user_id=:user_id and m.status='active' and r.role_code='management'
          and r.valid_from<=now() and (r.valid_to is null or r.valid_to>now())
          and (s.kind='tenant'
            or (s.kind='management' and s.management_unit_id=cast(:unit_id as uuid))
            or (s.kind='site' and s.site_id=cast(:site_id as uuid))
            or (s.kind='zone' and s.zone_id=cast(:zone_id as uuid))
            or (s.kind='building' and s.building_id=cast(:building_id as uuid)))
        limit 1
    """), {"user_id": scope[1], "unit_id": ticket["management_unit_id"],
           "site_id": ticket["site_id"], "zone_id": ticket["zone_id"],
           "building_id": ticket["building_id"]})
    return grant.first() is not None


async def record_event(scope: Scope, ticket: dict[str, object], event_type: str,
                       payload: str, *, to_status: str | None = None, idempotency_key: str | None = None) -> UUID:
    seq = ticket["last_event_seq"] + 1
    event_id = uuid4()
    inserted = await scope[0].execute(text("""
        insert into ticket_events
          (tenant_id, ticket_id, seq, event_type, actor_kind, actor_user_id,
           idempotency_key, correlation_id, payload, occurred_at, from_status, to_status)
        values (nullif(current_setting('app.tenant_id', true), '')::uuid,
          :ticket_id, :seq, :event_type, 'human', :user_id,
          :event_key, :correlation_id, cast(:payload as jsonb), now(), :from_status, :to_status)
        returning id
    """), {"ticket_id": ticket["id"], "seq": seq, "event_type": event_type,
           "user_id": scope[1], "event_key": idempotency_key or str(event_id),
           "correlation_id": event_id, "payload": payload,
           "from_status": ticket["status"], "to_status": to_status})
    await scope[0].execute(text("""
        update tickets set last_event_seq=:seq, version=version+1, updated_at=now()
        where id=:ticket_id
    """), {"ticket_id": ticket["id"], "seq": seq})
    return inserted.scalar_one()


class TicketChange(BaseModel):
    version: int = Field(ge=0)
    status: Literal["open", "triaging", "assigned", "in_progress", "resolved", "closed", "cancelled"]
    reason: str = Field(min_length=1, max_length=2000)


TICKET_TRANSITIONS = {
    "open": {"triaging", "cancelled"},
    "triaging": {"assigned", "cancelled"},
    "assigned": {"in_progress", "cancelled"},
    "in_progress": {"resolved", "cancelled"},
    "resolved": {"closed"},
}


class TicketCreate(BaseModel):
    domain_id: UUID
    building_id: UUID
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1)
    contact_name: str = Field(min_length=1)
    contact_phone: str = Field(min_length=1)
    request_kind: Literal["incident", "service_request"] = "incident"
    category_id: UUID | None = None


@router.post("/tickets", status_code=201, summary="Create a V3 ticket")
async def create_ticket(body: TicketCreate, scope: Scope) -> dict[str, object]:
    location = await scope[0].execute(text("""
        select b.id, b.site_id, b.zone_id, b.name as building_name
        from buildings b join sites s on s.id=b.site_id and s.tenant_id=b.tenant_id
        join domains d on d.id=s.domain_id and d.tenant_id=b.tenant_id
        where b.id=:building_id and d.id=:domain_id
          and b.status='active' and s.status='active' and d.status='active'
          and b.tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
    """), {"building_id": body.building_id, "domain_id": body.domain_id})
    place = location.mappings().first()
    if place is None:
        raise HTTPException(404, "Building not found in this domain")
    if not scope[2]:
        access = await scope[0].execute(text("""
            select 1 from scoped_user_roles r
            join tenant_memberships m on m.id=r.membership_id and m.tenant_id=r.tenant_id
            join access_scopes s on s.id=r.scope_id and s.tenant_id=r.tenant_id
            where m.user_id=:user_id and m.status='active'
              and r.role_code in ('management','staff')
              and r.valid_from<=now() and (r.valid_to is null or r.valid_to>now())
              and (s.kind='tenant' or (s.kind='site' and s.site_id=:site_id)
                   or (s.kind='zone' and s.zone_id=cast(:zone_id as uuid))
                   or (s.kind='building' and s.building_id=:building_id)) limit 1
        """), {"user_id": scope[1], "site_id": place["site_id"],
               "zone_id": place["zone_id"], "building_id": body.building_id})
        if access.first() is None:
            raise HTTPException(403, "Building is outside your operations scope")
    if body.category_id is not None:
        category = await scope[0].execute(text("""
            select 1 from service_categories where id=:id and enabled
        """), {"id": body.category_id})
        if category.first() is None:
            raise HTTPException(422, "Service category is unavailable")
    from .v3_routes import resolve_management_unit
    management = await resolve_management_unit(
        scope, body.building_id, body.domain_id, body.category_id
    )
    new_id = uuid4()
    channel_id = f"vh-ticket-{new_id}"
    await scope[0].execute(text("""
        insert into channels (id, tenant_id, name, description, kind, created_by)
        values (:id, nullif(current_setting('app.tenant_id', true), '')::uuid,
                :name, 'Vinhomes ticket reception', 'reception', :user_id)
    """), {"id": channel_id, "name": body.title, "user_id": scope[1]})
    created = await scope[0].execute(text("""
        insert into tickets
          (id, tenant_id, code, requester_user_id, channel_id, domain_id,
           site_id, zone_id, building_id, management_unit_id, category_id,
           title, description,
           priority, status, contact_name, contact_phone, address_snapshot,
           request_kind)
        values (:id, nullif(current_setting('app.tenant_id', true), '')::uuid,
          :code, :user_id, :channel_id, :domain_id,
          :site_id, :zone_id, :building_id, :management_unit_id, :category_id,
          :title, :description,
          'normal', 'open', :contact_name, :contact_phone,
          cast(:address as jsonb), :request_kind)
        returning id, code, status, version
    """), {"id": new_id, "code": f"VH-{new_id.hex[:12].upper()}",
           "user_id": scope[1], "channel_id": channel_id, "domain_id": body.domain_id,
           "site_id": place["site_id"], "zone_id": place["zone_id"],
           "building_id": body.building_id, "category_id": body.category_id,
           "management_unit_id": management["managementUnitId"],
           "title": body.title, "description": body.description,
           "contact_name": body.contact_name, "contact_phone": body.contact_phone,
           "address": json.dumps({"building": place["building_name"]}),
           "request_kind": body.request_kind})
    ticket = dict(created.mappings().one())
    await record_event(scope, {**ticket, "last_event_seq": 0}, "ticket.created",
                       json.dumps({"source": "operations_api"}), to_status="open")
    ticket["version"] = 1
    return ticket


@router.patch("/tickets/{ticket_id}/status", summary="Change ticket status with version check")
async def change_ticket_status(ticket_id: UUID, body: TicketChange, scope: Scope) -> dict[str, object]:
    ticket = await visible_ticket(scope, ticket_id, lock=True)
    if not await management_access(scope, ticket):
        raise HTTPException(403, "Management grant for this ticket is required")
    if ticket["version"] != body.version:
        raise HTTPException(409, "Ticket version changed; reload before updating")
    if body.status in {"resolved", "closed"}:
        raise HTTPException(409, "Completion requires all QC results and the resident decision")
    if body.status not in TICKET_TRANSITIONS.get(ticket["status"], set()):
        raise HTTPException(409, "Invalid ticket status transition")
    await scope[0].execute(text("""
        update tickets set status=:status,
          resolved_at=case when :status='resolved' then now() else resolved_at end,
          closed_at=case when :status='closed' then now() else closed_at end
        where id=:ticket_id
    """), {"ticket_id": ticket_id, "status": body.status})
    await record_event(scope, ticket, "ticket.status_changed",
                       json.dumps({"reason": body.reason}), to_status=body.status)
    return {"id": ticket_id, "status": body.status, "version": body.version + 1}


class AssessmentCreate(BaseModel):
    stage: Literal["intake", "specialist", "onsite", "reassessment"]
    severity: Literal["unknown", "minor", "moderate", "major", "critical", "not_applicable"]
    urgency: Literal["unknown", "routine", "soon", "immediate"]
    rationale: str = Field(min_length=1)
    facts: dict[str, object] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=1, max_length=200)
    version: int = Field(ge=0)


@router.post("/tickets/{ticket_id}/assessments", status_code=201,
             summary="Submit a human triage assessment")
async def create_assessment(ticket_id: UUID, body: AssessmentCreate, scope: Scope) -> dict[str, object]:
    ticket = await visible_ticket(scope, ticket_id, lock=True)
    existing = await scope[0].execute(text("""
        select id from ticket_assessments where ticket_id=:ticket_id and idempotency_key=:key
    """), {"ticket_id": ticket_id, "key": body.idempotency_key})
    old = existing.scalar_one_or_none()
    if old is not None:
        return {"id": old, "ticketId": ticket_id, "replayed": True}
    if ticket["version"] != body.version:
        raise HTTPException(409, "Ticket version changed; reload before assessing")
    result = await scope[0].execute(text("""
        insert into ticket_assessments
          (tenant_id, ticket_id, ticket_generation, basis_ticket_version,
           stage, assessor_kind, assessor_user_id, input_schema_version,
           facts, proposed_severity, proposed_urgency, rationale,
           observed_at, submitted_at, idempotency_key)
        values (nullif(current_setting('app.tenant_id', true), '')::uuid,
          :ticket_id, :generation, :version, :stage, 'human', :user_id, 'v3',
          cast(:facts as jsonb), :severity, :urgency, :rationale,
          now(), now(), :key)
        returning id
    """), {"ticket_id": ticket_id, "version": body.version,
           "generation": ticket["reopen_count"], "stage": body.stage,
           "user_id": scope[1], "facts": json.dumps(body.facts), "severity": body.severity,
           "urgency": body.urgency, "rationale": body.rationale,
           "key": body.idempotency_key})
    assessment_id = result.scalar_one()
    await record_event(scope, ticket, "ticket.assessed",
                       json.dumps({"assessmentId": str(assessment_id)}))
    return {"id": assessment_id, "ticketId": ticket_id, "version": body.version + 1}


class WorkOrderCreate(BaseModel):
    category_id: UUID
    required_specialty_id: UUID
    description: str = Field(min_length=1)
    ticket_version: int = Field(ge=0)


@router.post("/tickets/{ticket_id}/work-orders", status_code=201,
             summary="Create a work order for a visible ticket")
async def create_work_order(ticket_id: UUID, body: WorkOrderCreate, scope: Scope) -> dict[str, object]:
    ticket = await visible_ticket(scope, ticket_id, lock=True)
    if ticket["version"] != body.ticket_version:
        raise HTTPException(409, "Ticket version changed; reload before creating work order")
    if not await management_access(scope, ticket):
        raise HTTPException(403, "Responsible management required")
    if ticket["status"] not in {"open", "triaging"}:
        raise HTTPException(409, "Ticket is not awaiting work dispatch")
    category = await scope[0].execute(text("""
        select 1 from service_categories where id=:category_id and enabled
    """), {"category_id": body.category_id})
    if category.first() is None:
        raise HTTPException(422, "Service category is unavailable")
    result = await scope[0].execute(text("""
        insert into work_orders
          (tenant_id, ticket_id, category_id, required_specialty_id, description, status)
        values (nullif(current_setting('app.tenant_id', true), '')::uuid,
          :ticket_id, :category_id, :specialty_id, :description, 'queued')
        returning id, ticket_id, status, version
    """), {"ticket_id": ticket_id, "category_id": body.category_id,
           "specialty_id": body.required_specialty_id, "description": body.description})
    order = dict(result.mappings().one())
    await record_event(scope, ticket, "work_order.created",
                       json.dumps({"workOrderId": str(order["id"])}), to_status="assigned")
    await scope[0].execute(text("update tickets set status='assigned' where id=:id"), {"id": ticket["id"]})
    return order


class WorkOrderTransition(BaseModel):
    version: int = Field(ge=0)
    status: Literal["offered", "accepted", "en_route", "arrived", "awaiting_approval",
                    "in_progress", "completed", "rejected", "cancelled"]
    note: str = Field(min_length=1, max_length=2000)


class RepairProposal(BaseModel):
    version: int = Field(ge=0)
    note: str = Field(min_length=8, max_length=2000)


@router.post("/work-orders/{work_order_id}/repair-proposal", status_code=201)
async def propose_repair(work_order_id: UUID, body: RepairProposal, scope: Scope):
    from .v3_specialized import work_ticket, can_work_order
    ticket = await work_ticket(scope, work_order_id, lock=True)
    if not await can_work_order(scope, work_order_id, ticket):
        raise HTTPException(403, "Accepted assignment required")
    order = (await scope[0].execute(text("select status,version from work_orders where id=:id for update"), {"id": work_order_id})).mappings().one()
    if order["version"] != body.version or order["status"] != "arrived":
        raise HTTPException(409, "Proposal requires the current arrived work order")
    approval = await scope[0].execute(text("""
        insert into work_approvals(tenant_id,work_order_id,kind,requested_to_user_id,request_detail,status,request_hash)
        select tenant_id,:order,'customer_repair',requester_user_id,
          jsonb_build_object('note',cast(:note as text)),'pending',:hash from tickets where id=:ticket
        returning id,status
    """), {"order": work_order_id, "ticket": ticket["id"], "note": body.note, "hash": str(uuid4())})
    await scope[0].execute(text("update work_orders set status='awaiting_approval',version=version+1,updated_at=now() where id=:id"), {"id": work_order_id})
    await record_event(scope, ticket, "work_order.repair_proposed", json.dumps({"workOrderId": str(work_order_id)}))
    return dict(approval.mappings().one())


ALLOWED_TRANSITIONS = {
    "queued": {"offered", "cancelled"}, "offered": {"accepted", "rejected", "cancelled"},
    "accepted": {"en_route", "cancelled"}, "en_route": {"arrived", "cancelled"},
    "arrived": {"in_progress", "awaiting_approval"},
    "awaiting_approval": {"in_progress", "cancelled"},
    "in_progress": {"completed", "awaiting_approval"},
}


@router.patch("/work-orders/{work_order_id}/status", summary="Transition a work order")
async def change_work_order_status(work_order_id: UUID, body: WorkOrderTransition,
                                   scope: Scope) -> dict[str, object]:
    result = await scope[0].execute(text(f"""
        select w.id, w.ticket_id, w.version, w.status from work_orders w
        join tickets t on t.id=w.ticket_id and t.tenant_id=w.tenant_id
        where w.id=:work_order_id and {TICKET_VISIBILITY}
    """), {**actor_params(scope), "work_order_id": work_order_id})
    order = result.mappings().first()
    if order is None:
        raise HTTPException(404, "Work order not found")
    if not scope[2]:
        allowed = await scope[0].execute(text("""
            select 1 from work_assignments a
            join staff_profiles sp on sp.id=a.staff_id and sp.tenant_id=a.tenant_id
            where a.work_order_id=:id and sp.user_id=:user_id
              and a.status='accepted' limit 1
        """), {"id": work_order_id, "user_id": scope[1]})
        if allowed.first() is None:
            raise HTTPException(403, "Accepted assignment or administrator required")
    ticket = await visible_ticket(scope, order["ticket_id"], lock=True)
    locked = await scope[0].execute(text("""
        select status, version from work_orders where id=:id for update
    """), {"id": work_order_id})
    current = locked.mappings().one()
    if current["version"] != body.version:
        raise HTTPException(409, "Work order version changed; reload before updating")
    if body.status not in ALLOWED_TRANSITIONS.get(current["status"], set()):
        raise HTTPException(409, "Invalid work order status transition")
    if body.status == "in_progress":
        consent = await scope[0].execute(text("""
            select status from work_approvals where work_order_id=:id and kind='customer_repair'
            order by created_at desc,id desc limit 1
        """), {"id": work_order_id})
        if consent.scalar_one_or_none() != "approved":
            raise HTTPException(409, "Resident must approve the repair proposal before work starts")
    if body.status == "completed":
        water = await scope[0].execute(text("""
            select 1 from service_interruptions si join work_approvals wa on wa.id=si.approval_id and wa.tenant_id=si.tenant_id
            where wa.work_order_id=:id and si.status not in ('restored','cancelled') limit 1
        """), {"id": work_order_id})
        if water.first() is not None:
            raise HTTPException(409, "Restore water before completing work")
        evidence = await scope[0].execute(text("""
            select 1 from evidence_items where work_order_id=:id and status='active' and purpose in ('after','verification') limit 1
        """), {"id": work_order_id})
        if evidence.first() is None:
            raise HTTPException(409, "Attach completion evidence before completing work")
    updated = await scope[0].execute(text("""
        update work_orders set status=:status, version=version+1, updated_at=now(),
          arrived_at=case when :status='arrived' then now() else arrived_at end,
          started_at=case when :status='in_progress' then now() else started_at end,
          completed_at=case when :status='completed' then now() else completed_at end
        where id=:id returning id, status, version
    """), {"id": work_order_id, "status": body.status})
    if body.status in {"completed", "cancelled"}:
        await scope[0].execute(text("""
            update work_assignments set status=:status,ended_at=now(),updated_at=now()
            where work_order_id=:id and status in ('accepted','offered')
        """), {"id": work_order_id, "status": body.status})
    await record_event(scope, ticket, "work_order.status_changed",
                       json.dumps({"workOrderId": str(work_order_id), "status": body.status,
                                   "note": body.note}))
    if body.status == "in_progress":
        await scope[0].execute(text("update tickets set status='in_progress' where id=:id"), {"id": ticket["id"]})
    return dict(updated.mappings().one())


class AssignmentCreate(BaseModel):
    staff_id: UUID
    offer_expires_at: datetime
    work_order_version: int = Field(ge=0)


@router.post("/work-orders/{work_order_id}/assignments", status_code=201,
             summary="Offer a work order to an active staff member")
async def create_assignment(work_order_id: UUID, body: AssignmentCreate,
                            scope: Scope) -> dict[str, object]:
    result = await scope[0].execute(text("""
        select w.id, w.ticket_id, w.version, w.category_id from work_orders w
        where w.id=:id
    """), {"id": work_order_id})
    order = result.mappings().first()
    if order is None:
        raise HTTPException(404, "Work order not found")
    ticket = await visible_ticket(scope, order["ticket_id"], lock=True)
    if not await management_access(scope, ticket):
        raise HTTPException(403, "Responsible management required for dispatch")
    locked_order = await scope[0].execute(text("""
        select version, status from work_orders where id=:id for update
    """), {"id": work_order_id})
    current_order = locked_order.mappings().one()
    if current_order["version"] != body.work_order_version:
        raise HTTPException(409, "Work order version changed; reload before dispatch")
    if current_order["status"] not in {"queued", "offered"}:
        raise HTTPException(409, "Work order cannot be dispatched in its current status")
    if body.offer_expires_at.tzinfo is None:
        raise HTTPException(422, "offer_expires_at must include a timezone")
    if body.offer_expires_at <= datetime.now(body.offer_expires_at.tzinfo):
        raise HTTPException(422, "offer_expires_at must be in the future")
    active_offer = await scope[0].execute(text("""
        select 1 from work_assignments where work_order_id=:id
          and (status='accepted' or (status='offered' and offer_expires_at>now())) limit 1
    """), {"id": work_order_id})
    if active_offer.first() is not None:
        raise HTTPException(409, "Work order already has an active assignment")
    staff = await scope[0].execute(text("""
        select sp.max_concurrent_jobs from staff_profiles sp
        where sp.id=:staff_id and sp.active and sp.availability='available'
          and sp.management_unit_id=cast(:management_unit_id as uuid)
          and exists (select 1 from staff_specialties ss where ss.staff_id=sp.id
            and ss.tenant_id=sp.tenant_id and ss.category_id=:category_id and ss.active)
          and exists (select 1 from staff_shifts sh where sh.staff_id=sp.id
            and sh.tenant_id=sp.tenant_id and sh.status='available' and sh.starts_at<=now() and sh.ends_at>now())
        for update of sp
    """), {"staff_id": body.staff_id, "category_id": order["category_id"],
           "management_unit_id": ticket["management_unit_id"]})
    staff_row = staff.mappings().first()
    if staff_row is None:
        raise HTTPException(422, "Staff member is inactive or lacks this specialty")
    load = await scope[0].execute(text("""
        select count(*) from work_assignments a join work_orders w on w.id=a.work_order_id and w.tenant_id=a.tenant_id
        where a.staff_id=:staff_id and w.status not in ('completed','cancelled','rejected')
          and (a.status='accepted' or (a.status='offered' and a.offer_expires_at>now()))
    """), {"staff_id": body.staff_id})
    if load.scalar_one() >= staff_row["max_concurrent_jobs"]:
        raise HTTPException(409, "Staff is busy; work remains queued")
    created = await scope[0].execute(text("""
        insert into work_assignments
          (tenant_id, work_order_id, staff_id, assigned_by_user_id, status,
           offered_at, offer_expires_at)
        values (nullif(current_setting('app.tenant_id', true), '')::uuid,
          :work_order_id, :staff_id, :user_id, 'offered', now(), :expires_at)
        returning id, work_order_id, staff_id, status
    """), {"work_order_id": work_order_id, "staff_id": body.staff_id,
           "user_id": scope[1], "expires_at": body.offer_expires_at})
    assignment = dict(created.mappings().one())
    await scope[0].execute(text("""
        update work_orders set status='offered', version=version+1, updated_at=now()
        where id=:id
    """), {"id": work_order_id})
    await record_event(scope, ticket, "work_order.offered",
                       json.dumps({"assignmentId": str(assignment["id"])}))
    return assignment


class AssignmentResponse(BaseModel):
    status: Literal["accepted", "rejected"]
    eta_at: datetime | None = None
    rejection_reason: str | None = None


@router.post("/assignments/{assignment_id}/response", summary="Accept or reject an assignment")
async def respond_assignment(assignment_id: UUID, body: AssignmentResponse,
                             scope: Scope) -> dict[str, object]:
    found = await scope[0].execute(text("""
        select a.id, a.work_order_id, a.status, a.offer_expires_at,
               sp.user_id as staff_user_id, w.ticket_id
        from work_assignments a
        join staff_profiles sp on sp.id=a.staff_id and sp.tenant_id=a.tenant_id
        join work_orders w on w.id=a.work_order_id and w.tenant_id=a.tenant_id
        where a.id=:id
    """), {"id": assignment_id})
    assignment = found.mappings().first()
    if assignment is None:
        raise HTTPException(404, "Assignment not found")
    if assignment["staff_user_id"] != scope[1]:
        raise HTTPException(403, "Only the assigned staff member can respond")
    ticket = await visible_ticket(scope, assignment["ticket_id"], lock=True)
    locked = await scope[0].execute(text("""
        select status, offer_expires_at from work_assignments where id=:id for update
    """), {"id": assignment_id})
    current = locked.mappings().one()
    if current["status"] != "offered" or current["offer_expires_at"] <= datetime.now(current["offer_expires_at"].tzinfo):
        raise HTTPException(409, "Assignment offer expired or already answered")
    if body.status == "accepted" and body.eta_at is None:
        raise HTTPException(422, "eta_at is required when accepting")
    if body.eta_at is not None and body.eta_at.tzinfo is None:
        raise HTTPException(422, "eta_at must include a timezone")
    if body.status == "rejected" and not body.rejection_reason:
        raise HTTPException(422, "rejection_reason is required when rejecting")
    updated = await scope[0].execute(text("""
        update work_assignments set status=:status,
          accepted_at=case when :status='accepted' then now() else null end,
          eta_at=:eta_at, rejection_reason=:reason,
          ended_at=case when :status='rejected' then now() else null end,
          updated_at=now()
        where id=:id returning id, work_order_id, status, accepted_at, eta_at
    """), {"id": assignment_id, "status": body.status, "eta_at": body.eta_at,
           "reason": body.rejection_reason})
    await scope[0].execute(text("""
        update work_orders set status=case when :status='accepted' then 'accepted' else 'queued' end,
          version=version+1, updated_at=now()
        where id=:work_order_id
    """), {"status": body.status, "work_order_id": assignment["work_order_id"]})
    await record_event(scope, ticket, "work_assignment.responded",
                       json.dumps({"assignmentId": str(assignment_id), "status": body.status}))
    return dict(updated.mappings().one())


class EvidenceAttach(BaseModel):
    file_id: UUID
    purpose: Literal["issue", "before", "after", "verification"]
    caption: str | None = None
    work_order_id: UUID | None = None
    assignment_id: UUID | None = None


@router.post("/tickets/{ticket_id}/evidence", status_code=201,
             summary="Attach an already verified V3 file as evidence")
async def attach_evidence(ticket_id: UUID, body: EvidenceAttach,
                          scope: Scope) -> dict[str, object]:
    ticket = await visible_ticket(scope, ticket_id, lock=True)
    file = await scope[0].execute(text("""
        select 1 from files where id=:file_id and ticket_id=:ticket_id and status='ready'
    """), {"file_id": body.file_id, "ticket_id": ticket_id})
    if file.first() is None:
        raise HTTPException(422, "A ready file belonging to this ticket is required")
    if body.work_order_id is not None:
        order = await scope[0].execute(text("""
            select 1 from work_orders where id=:id and ticket_id=:ticket_id
        """), {"id": body.work_order_id, "ticket_id": ticket_id})
        if order.first() is None:
            raise HTTPException(422, "Work order does not belong to this ticket")
    if body.assignment_id is not None:
        assignment = await scope[0].execute(text("""
            select 1 from work_assignments a join work_orders w on w.id=a.work_order_id
            where a.id=:id and w.ticket_id=:ticket_id
        """), {"id": body.assignment_id, "ticket_id": ticket_id})
        if assignment.first() is None:
            raise HTTPException(422, "Assignment does not belong to this ticket")
    created = await scope[0].execute(text("""
        insert into evidence_items
          (tenant_id, ticket_id, work_order_id, assignment_id, file_id,
           purpose, uploaded_at, uploaded_by, caption, provenance, status)
        values (nullif(current_setting('app.tenant_id', true), '')::uuid,
          :ticket_id, :work_order_id, :assignment_id, :file_id,
          :purpose, now(), :user_id, :caption, 'upload', 'active')
        returning id, ticket_id, file_id, purpose
    """), {"ticket_id": ticket_id, "work_order_id": body.work_order_id,
           "assignment_id": body.assignment_id, "file_id": body.file_id,
           "purpose": body.purpose, "user_id": scope[1], "caption": body.caption})
    evidence = dict(created.mappings().one())
    await record_event(scope, ticket, "ticket.evidence_attached",
                       json.dumps({"evidenceId": str(evidence["id"])}))
    return evidence
