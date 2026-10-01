"""Operations contracts that extend V3 for QC, field work and budget review."""

import json
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .v3_auth import TICKET_VISIBILITY, scoped_connection
from .v3_mutations import management_access, record_event, visible_ticket

router = APIRouter(tags=["Vinhomes V3 field operations"])
Scope = Annotated[tuple[AsyncConnection, str, bool], Depends(scoped_connection, scope="function")]


def mapped(result: object) -> list[dict[str, object]]:
    return [dict(row) for row in result.mappings().all()]


async def work_ticket(scope: Scope, work_order_id: UUID, *, lock: bool = False) -> dict[str, object]:
    order = await scope[0].execute(text("""
        select ticket_id from work_orders where id=:id
    """), {"id": work_order_id})
    ticket_id = order.scalar_one_or_none()
    if ticket_id is None:
        raise HTTPException(404, "Work order not found")
    return await visible_ticket(scope, ticket_id, lock=lock)


async def can_work_order(scope: Scope, work_order_id: UUID,
                         ticket: dict[str, object]) -> bool:
    if await management_access(scope, ticket):
        return True
    assignment = await scope[0].execute(text("""
        select 1 from work_assignments a
        join staff_profiles sp on sp.id=a.staff_id and sp.tenant_id=a.tenant_id
        where a.work_order_id=:id and sp.user_id=:user_id
          and a.status='accepted' limit 1
    """), {"id": work_order_id, "user_id": scope[1]})
    return assignment.first() is not None


async def site_access(scope: Scope, site_id: UUID) -> None:
    result = await scope[0].execute(text("""
        select 1 from sites where id=:site_id and status='active'
    """), {"site_id": site_id})
    if result.first() is None:
        raise HTTPException(404, "Site not found")
    if scope[2]:
        return
    grant = await scope[0].execute(text("""
        select 1 from scoped_user_roles r
        join tenant_memberships m on m.id=r.membership_id and m.tenant_id=r.tenant_id
        join access_scopes s on s.id=r.scope_id and s.tenant_id=r.tenant_id
        where m.user_id=:user_id and m.status='active'
          and r.role_code in ('staff','management')
          and r.valid_from<=now() and (r.valid_to is null or r.valid_to>now())
          and (s.kind='tenant' or (s.kind='site' and s.site_id=:site_id))
        limit 1
    """), {"user_id": scope[1], "site_id": site_id})
    if grant.first() is None:
        raise HTTPException(403, "Site is outside your operations scope")


class QcSubmit(BaseModel):
    outcome: Literal["pass", "fail", "inconclusive"]
    criteria: list[dict[str, object]]
    redo_required: bool = False
    note: str | None = None


@router.get("/work-orders/{work_order_id}/qc", summary="QC history")
async def qc_history(work_order_id: UUID, scope: Scope) -> dict[str, object]:
    await work_ticket(scope, work_order_id)
    result = await scope[0].execute(text("""
        select * from vh_qc_results where work_order_id=:id order by checked_at desc
    """), {"id": work_order_id})
    return {"items": mapped(result)}


@router.post("/work-orders/{work_order_id}/qc", status_code=201,
             summary="Record a QC inspection")
async def submit_qc(work_order_id: UUID, body: QcSubmit, scope: Scope) -> dict[str, object]:
    if body.redo_required and body.outcome != "fail":
        raise HTTPException(422, "Redo requires a failed QC outcome")
    ticket = await work_ticket(scope, work_order_id, lock=True)
    if not await management_access(scope, ticket):
        raise HTTPException(403, "Management grant is required for QC")
    if ticket["status"] in {"closed", "cancelled"}:
        raise HTTPException(409, "Ticket is already closed")
    self_inspection = await scope[0].execute(text("""
        select 1 from work_assignments a join staff_profiles sp on sp.id=a.staff_id and sp.tenant_id=a.tenant_id
        where a.work_order_id=:id and sp.user_id=:actor and a.status in ('accepted','completed')
    """), {"id": work_order_id, "actor": scope[1]})
    if self_inspection.first() is not None:
        raise HTTPException(403, "QC must be performed by an independent reviewer")
    if ticket["status"] == "resolved":
        await scope[0].execute(text("""
            update work_approvals set status='cancelled',updated_at=now()
            where kind='customer_completion' and status='pending'
              and work_order_id in (select id from work_orders where ticket_id=:id)
        """), {"id": ticket["id"]})
        await scope[0].execute(text("update tickets set status='in_progress',resolved_at=null where id=:id"), {"id": ticket["id"]})
    order = await scope[0].execute(text("""
        select status from work_orders where id=:id for update
    """), {"id": work_order_id})
    if order.scalar_one() != "completed":
        raise HTTPException(409, "Work order must be completed before QC")
    result = await scope[0].execute(text("""
        insert into vh_qc_results
          (tenant_id,work_order_id,outcome,criteria,redo_required,note,checked_by)
        values (nullif(current_setting('app.tenant_id',true),'')::uuid,
          :id,:outcome,cast(:criteria as jsonb),:redo,:note,:user_id)
        returning id,work_order_id,outcome,redo_required,checked_at
    """), {"id": work_order_id, "outcome": body.outcome,
           "criteria": json.dumps(body.criteria), "redo": body.redo_required,
           "note": body.note, "user_id": scope[1]})
    qc = dict(result.mappings().one())
    await record_event(scope, ticket, "work_order.qc_recorded",
                       json.dumps({"qcId": str(qc["id"]), "outcome": body.outcome}))
    from .v3_completion import publish_completion
    await publish_completion(scope, ticket["id"])
    return qc


class RedoCreate(BaseModel):
    qc_result_id: UUID
    work_order_version: int = Field(ge=0)
    instruction: str = Field(min_length=1)


@router.post("/work-orders/{work_order_id}/redo", status_code=201,
             summary="Create a redo work order after failed QC")
async def create_redo(work_order_id: UUID, body: RedoCreate,
                      scope: Scope) -> dict[str, object]:
    ticket = await work_ticket(scope, work_order_id, lock=True)
    if not await management_access(scope, ticket):
        raise HTTPException(403, "Management grant is required for a redo")
    source = await scope[0].execute(text("""
        select ticket_id,category_id,required_specialty_id,version,status
        from work_orders where id=:id for update
    """), {"id": work_order_id})
    order = source.mappings().one()
    if order["version"] != body.work_order_version:
        raise HTTPException(409, "Work order version changed; reload before redo")
    if order["status"] != "completed":
        raise HTTPException(409, "Only a completed work order can be redone")
    latest = await scope[0].execute(text("""
        select id,outcome,redo_required from vh_qc_results
        where work_order_id=:id order by checked_at desc,id desc limit 1
    """), {"id": work_order_id})
    qc = latest.mappings().first()
    if qc is None or qc["id"] != body.qc_result_id or qc["outcome"] != "fail" or not qc["redo_required"]:
        raise HTTPException(409, "Latest QC result does not authorize a redo")
    existing = await scope[0].execute(text("""
        select redo_work_order_id from vh_qc_redo_orders where qc_result_id=:id
    """), {"id": body.qc_result_id})
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(409, "A redo work order already exists for this QC result")
    created = await scope[0].execute(text("""
        insert into work_orders
          (tenant_id,ticket_id,category_id,required_specialty_id,
           description,status)
        values (nullif(current_setting('app.tenant_id',true),'')::uuid,
          :ticket_id,:category_id,:specialty_id,:description,'queued')
        returning id,ticket_id,status,version
    """), {"ticket_id": order["ticket_id"], "category_id": order["category_id"],
           "specialty_id": order["required_specialty_id"],
           "description": body.instruction})
    redo = dict(created.mappings().one())
    await scope[0].execute(text("""
        insert into vh_qc_redo_orders
          (tenant_id,qc_result_id,source_work_order_id,redo_work_order_id,created_by)
        values (nullif(current_setting('app.tenant_id',true),'')::uuid,
          :qc_id,:source_id,:redo_id,:user_id)
    """), {"qc_id": body.qc_result_id, "source_id": work_order_id,
           "redo_id": redo["id"], "user_id": scope[1]})
    await record_event(scope, ticket, "work_order.redo_created",
                       json.dumps({"qcId": str(body.qc_result_id),
                                   "sourceWorkOrderId": str(work_order_id),
                                   "redoWorkOrderId": str(redo["id"])}))
    return redo


class CleaningPlanSave(BaseModel):
    plan: dict[str, object]
    status: Literal["draft", "in_progress", "completed", "cancelled"]
    version: int | None = Field(None, ge=0)


@router.get("/work-orders/{work_order_id}/cleaning-plan", summary="Cleaning plan")
async def get_cleaning_plan(work_order_id: UUID, scope: Scope) -> dict[str, object]:
    await work_ticket(scope, work_order_id)
    result = await scope[0].execute(text("""
        select * from vh_cleaning_plans where work_order_id=:id
    """), {"id": work_order_id})
    plan = result.mappings().first()
    if plan is None:
        raise HTTPException(404, "Cleaning plan not found")
    return dict(plan)


@router.put("/work-orders/{work_order_id}/cleaning-plan", summary="Save cleaning plan")
async def save_cleaning_plan(work_order_id: UUID, body: CleaningPlanSave,
                             scope: Scope) -> dict[str, object]:
    ticket = await work_ticket(scope, work_order_id, lock=True)
    if not await can_work_order(scope, work_order_id, ticket):
        raise HTTPException(403, "Assignment or management grant is required")
    current = await scope[0].execute(text("""
        select version from vh_cleaning_plans where work_order_id=:id for update
    """), {"id": work_order_id})
    current_version = current.scalar_one_or_none()
    if current_version is not None and current_version != body.version:
        raise HTTPException(409, "Cleaning plan version changed; reload before saving")
    if current_version is None and body.version is not None:
        raise HTTPException(409, "Cleaning plan does not exist yet")
    result = await scope[0].execute(text("""
        insert into vh_cleaning_plans
          (tenant_id,work_order_id,plan,status,updated_by)
        values (nullif(current_setting('app.tenant_id',true),'')::uuid,
          :id,cast(:plan as jsonb),:status,:user_id)
        on conflict (tenant_id,work_order_id) do update
          set plan=excluded.plan,status=excluded.status,updated_by=excluded.updated_by,
              version=vh_cleaning_plans.version+1,updated_at=now()
        returning id,work_order_id,status,version,plan
    """), {"id": work_order_id, "plan": json.dumps(body.plan),
           "status": body.status, "user_id": scope[1]})
    saved = dict(result.mappings().one())
    await record_event(scope, ticket, "cleaning_plan.saved",
                       json.dumps({"cleaningPlanId": str(saved["id"]), "status": body.status}))
    return saved


class ContractorSave(BaseModel):
    status: Literal["pending", "accepted", "rejected", "in_progress", "completed"]
    worker_name: str | None = None
    materials: list[dict[str, object]] = Field(default_factory=list)
    note: str | None = None
    version: int | None = Field(None, ge=0)


@router.get("/work-orders/{work_order_id}/contractor", summary="Contractor progress")
async def get_contractor(work_order_id: UUID, scope: Scope) -> dict[str, object]:
    await work_ticket(scope, work_order_id)
    result = await scope[0].execute(text("""
        select * from vh_contractor_updates where work_order_id=:id
    """), {"id": work_order_id})
    row = result.mappings().first()
    if row is None:
        raise HTTPException(404, "Contractor progress not found")
    return dict(row)


@router.put("/work-orders/{work_order_id}/contractor", summary="Record contractor progress")
async def save_contractor(work_order_id: UUID, body: ContractorSave,
                          scope: Scope) -> dict[str, object]:
    ticket = await work_ticket(scope, work_order_id, lock=True)
    if not await can_work_order(scope, work_order_id, ticket):
        raise HTTPException(403, "Assignment or management grant is required")
    current = await scope[0].execute(text("""
        select version from vh_contractor_updates where work_order_id=:id for update
    """), {"id": work_order_id})
    version = current.scalar_one_or_none()
    if version != body.version:
        raise HTTPException(409, "Contractor progress version changed; reload before saving")
    result = await scope[0].execute(text("""
        insert into vh_contractor_updates
          (tenant_id,work_order_id,status,worker_name,materials,note,updated_by)
        values (nullif(current_setting('app.tenant_id',true),'')::uuid,
          :id,:status,:worker,cast(:materials as jsonb),:note,:user_id)
        on conflict (tenant_id,work_order_id) do update
          set status=excluded.status,worker_name=excluded.worker_name,
              materials=excluded.materials,note=excluded.note,
              updated_by=excluded.updated_by,version=vh_contractor_updates.version+1,
              updated_at=now()
        returning id,work_order_id,status,version,materials
    """), {"id": work_order_id, "status": body.status,
           "worker": body.worker_name, "materials": json.dumps(body.materials),
           "note": body.note, "user_id": scope[1]})
    saved = dict(result.mappings().one())
    await record_event(scope, ticket, "contractor.progress_recorded",
                       json.dumps({"contractorUpdateId": str(saved["id"]), "status": body.status}))
    return saved


class BudgetRequest(BaseModel):
    reviewer_user_id: str = Field(min_length=1)
    amount_vnd: Decimal = Field(gt=0)
    purpose: str = Field(min_length=1)


@router.get("/budget-approvals", summary="Budget approval queue")
async def budget_approvals(scope: Scope, status: str | None = None) -> dict[str, object]:
    result = await scope[0].execute(text(f"""
        select a.* from vh_budget_approvals a
        join work_orders w on w.id=a.work_order_id and w.tenant_id=a.tenant_id
        join tickets t on t.id=w.ticket_id and t.tenant_id=w.tenant_id
        where {TICKET_VISIBILITY}
          and (cast(:status as text) is null or a.status=:status)
          and (:is_admin or a.reviewer_user_id=:user_id or a.requested_by=:user_id)
        order by a.created_at desc limit 100
    """), {"is_admin": scope[2], "user_id": scope[1], "status": status})
    return {"items": mapped(result)}


@router.post("/work-orders/{work_order_id}/budget-approvals", status_code=201,
             summary="Request budget approval")
async def request_budget(work_order_id: UUID, body: BudgetRequest,
                         scope: Scope) -> dict[str, object]:
    ticket = await work_ticket(scope, work_order_id, lock=True)
    if not await management_access(scope, ticket):
        raise HTTPException(403, "Management grant is required for budget requests")
    reviewer = await scope[0].execute(text("""
        select 1 from users u where u.id=:id and u.status='active'
          and (exists (select 1 from platform_admins pa where pa.user_id=u.id)
               or exists (
                 select 1 from scoped_user_roles r
                 join tenant_memberships m on m.id=r.membership_id and m.tenant_id=r.tenant_id
                 where m.user_id=u.id and m.status='active'
                   and r.role_code='management' and r.valid_from<=now()
                   and (r.valid_to is null or r.valid_to>now())))
    """), {"id": body.reviewer_user_id})
    if reviewer.first() is None:
        raise HTTPException(422, "Reviewer needs an active management or admin grant")
    result = await scope[0].execute(text("""
        insert into vh_budget_approvals
          (tenant_id,work_order_id,requested_by,reviewer_user_id,
           amount_vnd,purpose,status)
        values (nullif(current_setting('app.tenant_id',true),'')::uuid,
          :id,:user_id,:reviewer,:amount,:purpose,'pending')
        returning id,work_order_id,status,amount_vnd,version
    """), {"id": work_order_id, "user_id": scope[1],
           "reviewer": body.reviewer_user_id, "amount": body.amount_vnd,
           "purpose": body.purpose})
    approval = dict(result.mappings().one())
    await record_event(scope, ticket, "budget_approval.requested",
                       json.dumps({"approvalId": str(approval["id"])}))
    return approval


class BudgetDecision(BaseModel):
    status: Literal["approved", "rejected"]
    note: str = Field(min_length=1)
    version: int = Field(ge=0)


@router.post("/budget-approvals/{approval_id}/decision", summary="Decide budget request")
async def decide_budget(approval_id: UUID, body: BudgetDecision,
                        scope: Scope) -> dict[str, object]:
    found = await scope[0].execute(text("""
        select id,work_order_id,reviewer_user_id from vh_budget_approvals where id=:id
    """), {"id": approval_id})
    approval = found.mappings().first()
    if approval is None:
        raise HTTPException(404, "Budget approval not found")
    ticket = await work_ticket(scope, approval["work_order_id"], lock=True)
    if not scope[2] and approval["reviewer_user_id"] != scope[1]:
        raise HTTPException(403, "Only the assigned reviewer can decide")
    updated = await scope[0].execute(text("""
        update vh_budget_approvals set status=:status,decided_by=:user_id,
          decided_at=now(),decision_note=:note,version=version+1,updated_at=now()
        where id=:id and status='pending' and version=:version
        returning id,work_order_id,status,version,decided_at
    """), {"id": approval_id, "status": body.status,
           "user_id": scope[1], "note": body.note, "version": body.version})
    row = updated.mappings().first()
    if row is None:
        raise HTTPException(409, "Approval changed; reload before deciding")
    await record_event(scope, ticket, "budget_approval.decided",
                       json.dumps({"approvalId": str(approval_id), "status": body.status}))
    return dict(row)


class CheckpointCreate(BaseModel):
    site_id: UUID
    name: str = Field(min_length=1)
    location: str = Field(min_length=1)
    sort_order: int = 0


@router.get("/security/checkpoints", summary="Security checkpoints at a site")
async def security_checkpoints(scope: Scope, site_id: UUID = Query(..., alias="siteId")) -> dict[str, object]:
    await site_access(scope, site_id)
    result = await scope[0].execute(text("""
        select * from vh_security_checkpoints where site_id=:site_id
        order by sort_order,name
    """), {"site_id": site_id})
    return {"items": mapped(result)}


@router.post("/security/checkpoints", status_code=201, summary="Create a security checkpoint")
async def create_checkpoint(body: CheckpointCreate, scope: Scope) -> dict[str, object]:
    await site_access(scope, body.site_id)
    if not scope[2]:
        raise HTTPException(403, "Administrator required to configure checkpoints")
    result = await scope[0].execute(text("""
        insert into vh_security_checkpoints
          (tenant_id,site_id,name,location,sort_order,status)
        values (nullif(current_setting('app.tenant_id',true),'')::uuid,
          :site_id,:name,:location,:sort_order,'pending')
        returning id,site_id,name,location,status
    """), body.model_dump())
    return dict(result.mappings().one())


class CheckpointUpdate(BaseModel):
    status: Literal["checked", "missed"]
    notes: str | None = None


@router.patch("/security/checkpoints/{checkpoint_id}", summary="Record a checkpoint visit")
async def mark_checkpoint(checkpoint_id: UUID, body: CheckpointUpdate,
                          scope: Scope) -> dict[str, object]:
    found = await scope[0].execute(text("""
        select site_id from vh_security_checkpoints where id=:id
    """), {"id": checkpoint_id})
    site_id = found.scalar_one_or_none()
    if site_id is None:
        raise HTTPException(404, "Checkpoint not found")
    await site_access(scope, site_id)
    result = await scope[0].execute(text("""
        update vh_security_checkpoints set status=:status,notes=:notes,
          guard_user_id=:user_id,checked_at=now(),updated_at=now()
        where id=:id returning id,site_id,status,guard_user_id,checked_at
    """), {"id": checkpoint_id, "status": body.status,
           "notes": body.notes, "user_id": scope[1]})
    return dict(result.mappings().one())


class SecurityIncidentCreate(BaseModel):
    site_id: UUID
    ticket_id: UUID | None = None
    title: str = Field(min_length=1)
    location: str = Field(min_length=1)
    severity: Literal["p1", "p2", "p3", "p4"] | None = None
    business_severity: Literal["P0", "P1", "P2", "P3"] | None = None
    report: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def valid_severity(self) -> "SecurityIncidentCreate":
        levels = {"P0": "p1", "P1": "p2", "P2": "p3", "P3": "p4"}
        if self.severity is None and self.business_severity is None:
            raise ValueError("severity or business_severity is required")
        if self.severity and self.business_severity and self.severity != levels[self.business_severity]:
            raise ValueError("severity and business_severity disagree")
        return self


@router.get("/security/incidents", summary="Security incident reports")
async def security_incidents(scope: Scope, site_id: UUID = Query(..., alias="siteId")) -> dict[str, object]:
    await site_access(scope, site_id)
    result = await scope[0].execute(text("""
        select * from vh_security_incidents where site_id=:site_id
        order by reported_at desc limit 100
    """), {"site_id": site_id})
    return {"items": mapped(result)}


@router.post("/security/incidents", status_code=201, summary="Report a security incident")
async def report_security_incident(body: SecurityIncidentCreate,
                                   scope: Scope) -> dict[str, object]:
    await site_access(scope, body.site_id)
    ticket = None
    if body.ticket_id is not None:
        ticket = await visible_ticket(scope, body.ticket_id, lock=True)
        if ticket["site_id"] != body.site_id:
            raise HTTPException(422, "Ticket belongs to another site")
    severity = body.severity or {"P0": "p1", "P1": "p2", "P2": "p3", "P3": "p4"}[body.business_severity]
    result = await scope[0].execute(text("""
        insert into vh_security_incidents
          (tenant_id,site_id,ticket_id,title,location,severity,report,status,reported_by)
        values (nullif(current_setting('app.tenant_id',true),'')::uuid,
          :site_id,:ticket_id,:title,:location,:severity,
          cast(:report as jsonb),'investigating',:user_id)
        returning id,site_id,ticket_id,title,severity,status,reported_at
    """), {"site_id": body.site_id, "ticket_id": body.ticket_id,
           "title": body.title, "location": body.location,
           "severity": severity, "report": json.dumps(body.report),
           "user_id": scope[1]})
    incident = dict(result.mappings().one())
    if ticket is not None:
        await record_event(scope, ticket, "security.incident_reported",
                           json.dumps({"securityIncidentId": str(incident["id"])}))
    return incident


class SecurityIncidentUpdate(BaseModel):
    status: Literal["investigating", "resolved", "escalated_to_police"]
    report: dict[str, object]


@router.patch("/security/incidents/{incident_id}", summary="Update a security incident")
async def update_security_incident(incident_id: UUID, body: SecurityIncidentUpdate,
                                   scope: Scope) -> dict[str, object]:
    found = await scope[0].execute(text("""
        select site_id,ticket_id from vh_security_incidents where id=:id
    """), {"id": incident_id})
    incident = found.mappings().first()
    if incident is None:
        raise HTTPException(404, "Security incident not found")
    await site_access(scope, incident["site_id"])
    ticket = await visible_ticket(scope, incident["ticket_id"], lock=True) if incident["ticket_id"] else None
    updated = await scope[0].execute(text("""
        update vh_security_incidents set status=:status,
          report=cast(:report as jsonb),updated_at=now()
        where id=:id returning id,status,updated_at
    """), {"id": incident_id, "status": body.status,
           "report": json.dumps(body.report)})
    if ticket is not None:
        await record_event(scope, ticket, "security.incident_updated",
                           json.dumps({"securityIncidentId": str(incident_id),
                                       "status": body.status}))
    return dict(updated.mappings().one())


class HandoverCreate(BaseModel):
    site_id: UUID
    shift_name: Literal["ca_sang", "ca_chieu", "ca_dem"]
    shift_date: date
    to_user_id: str = Field(min_length=1)
    payload: dict[str, object]


@router.get("/security/handovers", summary="Security shift handovers")
async def security_handovers(scope: Scope, site_id: UUID = Query(..., alias="siteId")) -> dict[str, object]:
    await site_access(scope, site_id)
    result = await scope[0].execute(text("""
        select * from vh_security_handovers where site_id=:site_id
        order by created_at desc limit 100
    """), {"site_id": site_id})
    return {"items": mapped(result)}


@router.post("/security/handovers", status_code=201, summary="Submit a shift handover")
async def create_handover(body: HandoverCreate, scope: Scope) -> dict[str, object]:
    await site_access(scope, body.site_id)
    recipient = await scope[0].execute(text("""
        select 1 from users where id=:id and status='active'
    """), {"id": body.to_user_id})
    if recipient.first() is None:
        raise HTTPException(422, "Recipient is not an active user")
    result = await scope[0].execute(text("""
        insert into vh_security_handovers
          (tenant_id,site_id,shift_name,shift_date,payload,from_user_id,to_user_id)
        values (nullif(current_setting('app.tenant_id',true),'')::uuid,
          :site_id,:shift_name,:shift_date,cast(:payload as jsonb),:user_id,:to_user_id)
        returning id,site_id,shift_name,shift_date,confirmed,created_at
    """), {"site_id": body.site_id, "shift_name": body.shift_name,
           "shift_date": body.shift_date, "payload": json.dumps(body.payload),
           "user_id": scope[1], "to_user_id": body.to_user_id})
    return dict(result.mappings().one())


@router.post("/security/handovers/{handover_id}/confirm", summary="Confirm receipt of shift handover")
async def confirm_handover(handover_id: UUID, scope: Scope) -> dict[str, object]:
    found = await scope[0].execute(text("""
        select site_id,to_user_id from vh_security_handovers where id=:id
    """), {"id": handover_id})
    handover = found.mappings().first()
    if handover is None:
        raise HTTPException(404, "Handover not found")
    await site_access(scope, handover["site_id"])
    if not scope[2] and handover["to_user_id"] != scope[1]:
        raise HTTPException(403, "Only the recipient can confirm this handover")
    result = await scope[0].execute(text("""
        update vh_security_handovers set confirmed=true,updated_at=now()
        where id=:id and confirmed=false returning id,confirmed,updated_at
    """), {"id": handover_id})
    row = result.mappings().first()
    if row is None:
        raise HTTPException(409, "Handover already confirmed")
    return dict(row)
