"""Two human approvals before work dispatch; database is the workflow authority."""

import json
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection
from .v3_auth import scoped_connection, resident_connection, TICKET_VISIBILITY
from .v3_mutations import visible_ticket, record_event
from .v3_water import _responsible_management
from .v3_security import digest, notification

router = APIRouter(tags=["V3 human approval plans"])
Scope = Annotated[tuple[AsyncConnection, str, bool], Depends(scoped_connection)]
Resident = Annotated[tuple[AsyncConnection, str], Depends(resident_connection)]
TENANT = "nullif(current_setting('app.tenant_id',true),'')::uuid"


class PlanStep(BaseModel):
    category_id: UUID
    description: str = Field(min_length=1, max_length=2000)


class PlanCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    steps: list[PlanStep] = Field(min_length=1, max_length=20)
    estimated_amount: Decimal = Field(
        default=Decimal("0"), ge=0, max_digits=18, decimal_places=2
    )
    ticket_version: int = Field(ge=0)
    idempotency_key: str = Field(min_length=1, max_length=160)


class PlanDecision(BaseModel):
    decision: Literal["approve", "reject"]
    version: int = Field(ge=0)
    note: str = Field(min_length=1, max_length=2000)


@router.post("/tickets/{ticket_id}/plans", status_code=201)
async def propose(ticket_id: UUID, body: PlanCreate, scope: Scope):
    ticket = await visible_ticket(scope, ticket_id, lock=True)
    await _responsible_management(scope, ticket)
    fingerprint = digest(body.model_dump(exclude={"idempotency_key", "ticket_version"}))
    old = (
        (
            await scope[0].execute(
                text(
                    "select * from vh_ticket_plans where ticket_id=:id and idempotency_key=:key"
                ),
                {"id": ticket_id, "key": body.idempotency_key},
            )
        )
        .mappings()
        .first()
    )
    if old:
        if old["request_hash"] != fingerprint or old["proposed_by"] != scope[1]:
            raise HTTPException(409, "Plan key already used")
        return dict(old)
    if ticket["version"] != body.ticket_version or ticket["status"] in {
        "closed",
        "cancelled",
        "resolved",
    }:
        raise HTTPException(409, "Ticket changed or is final")
    pending = await scope[0].execute(
        text(
            "select 1 from vh_ticket_plans where ticket_id=:id and status in ('management_pending','resident_pending')"
        ),
        {"id": ticket_id},
    )
    if pending.first():
        raise HTTPException(409, "Decide the existing plan first")
    for step in body.steps:
        cat = await scope[0].execute(
            text("select 1 from service_categories where id=:id and enabled"),
            {"id": step.category_id},
        )
        if cat.first() is None:
            raise HTTPException(422, "Unavailable category")
    result = await scope[0].execute(
        text(f"""insert into vh_ticket_plans(tenant_id,ticket_id,proposed_by,title,steps,estimated_amount,status,idempotency_key,request_hash)
      values({TENANT},:ticket,:actor,:title,cast(:steps as jsonb),:amount,'management_pending',:key,:hash) returning *"""),
        {
            "ticket": ticket_id,
            "actor": scope[1],
            "title": body.title,
            "steps": json.dumps([s.model_dump(mode="json") for s in body.steps]),
            "amount": body.estimated_amount,
            "key": body.idempotency_key,
            "hash": fingerprint,
        },
    )
    plan = dict(result.mappings().one())
    await record_event(
        scope, ticket, "plan.proposed", json.dumps({"planId": str(plan["id"])})
    )
    return plan


@router.get("/tickets/{ticket_id}/plans")
async def list_plans(ticket_id: UUID, scope: Scope):
    await visible_ticket(scope, ticket_id)
    rows = await scope[0].execute(
        text(
            "select * from vh_ticket_plans where ticket_id=:id order by created_at desc"
        ),
        {"id": ticket_id},
    )
    return {"items": [dict(r) for r in rows.mappings()]}


@router.get("/plans")
async def plan_queue(
    scope: Scope,
    status: Literal[
        "management_pending", "resident_pending", "approved", "rejected"
    ] = "management_pending",
    limit: int = Query(50, ge=1, le=100),
):
    rows = await scope[0].execute(
        text(
            f"select p.*,t.title as ticket_title from vh_ticket_plans p join tickets t on t.id=p.ticket_id and t.tenant_id=p.tenant_id where p.status=:status and {TICKET_VISIBILITY} order by p.created_at limit :limit"
        ),
        {"status": status, "limit": limit, "user_id": scope[1], "is_admin": scope[2]},
    )
    return {"items": [dict(r) for r in rows.mappings()]}


async def plan_ticket(db: AsyncConnection, plan_id: UUID):
    row = (
        (
            await db.execute(
                text("select ticket_id from vh_ticket_plans where id=:id"),
                {"id": plan_id},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(404, "Plan not found")
    return row["ticket_id"]


@router.post("/plans/{plan_id}/management-decision")
async def management_decision(plan_id: UUID, body: PlanDecision, scope: Scope):
    ticket = await visible_ticket(
        scope, await plan_ticket(scope[0], plan_id), lock=True
    )
    await _responsible_management(scope, ticket)
    plan = (
        (
            await scope[0].execute(
                text("select * from vh_ticket_plans where id=:id for update"),
                {"id": plan_id},
            )
        )
        .mappings()
        .one()
    )
    if plan["status"] != "management_pending" or plan["version"] != body.version:
        raise HTTPException(409, "Plan changed")
    status = "resident_pending" if body.decision == "approve" else "rejected"
    row = await scope[0].execute(
        text(
            "update vh_ticket_plans set status=:status,version=version+1,management_by=:actor,management_note=:note,management_at=now(),updated_at=now() where id=:id returning *"
        ),
        {"status": status, "actor": scope[1], "note": body.note, "id": plan_id},
    )
    event = await record_event(
        scope,
        ticket,
        "plan.management_decided",
        json.dumps({"planId": str(plan_id), "status": status}),
    )
    requester = (
        await scope[0].execute(
            text("select requester_user_id from tickets where id=:id"),
            {"id": ticket["id"]},
        )
    ).scalar_one()
    await notification(
        scope,
        requester,
        f"plan:{plan_id}:management",
        {"type": "plan.management_decided", "planId": str(plan_id), "status": status},
        event,
    )
    return dict(row.mappings().one())


@router.get("/resident/plans")
async def resident_plans(scope: Resident, limit: int = Query(50, ge=1, le=100)):
    rows = await scope[0].execute(
        text(
            "select p.* from vh_ticket_plans p join tickets t on t.id=p.ticket_id and t.tenant_id=p.tenant_id where t.requester_user_id=:actor order by p.created_at desc limit :limit"
        ),
        {"actor": scope[1], "limit": limit},
    )
    return {"items": [dict(r) for r in rows.mappings()]}


@router.post("/resident/plans/{plan_id}/decision")
async def resident_decision(plan_id: UUID, body: PlanDecision, scope: Resident):
    db, actor = scope
    tid = await plan_ticket(db, plan_id)
    ticket = (
        (
            await db.execute(
                text(
                    "select * from tickets where id=:id and requester_user_id=:actor for update"
                ),
                {"id": tid, "actor": actor},
            )
        )
        .mappings()
        .first()
    )
    if ticket is None:
        raise HTTPException(404, "Plan not found")
    plan = (
        (
            await db.execute(
                text("select * from vh_ticket_plans where id=:id for update"),
                {"id": plan_id},
            )
        )
        .mappings()
        .one()
    )
    if (
        plan["status"] != "resident_pending"
        or plan["version"] != body.version
        or ticket["status"] in {"closed", "cancelled", "resolved"}
    ):
        raise HTTPException(409, "Plan or ticket changed")
    status = "approved" if body.decision == "approve" else "rejected"
    work = []
    steps = [dict(step) for step in plan["steps"]]
    if status == "approved":
        for step in steps:
            category = await db.execute(
                text("select 1 from service_categories where id=:id and enabled"),
                {"id": UUID(step["category_id"])},
            )
            if category.first() is None:
                raise HTTPException(
                    409, "Plan category is no longer available; request a revised plan"
                )
            order = await db.execute(
                text(f"""insert into work_orders(tenant_id,ticket_id,category_id,required_specialty_id,description,status,scheduled_at)
                values({TENANT},:ticket,:category,:category,:description,'queued',:scheduled) returning id"""),
                {
                    "ticket": tid,
                    "category": UUID(step["category_id"]),
                    "description": step["description"],
                    "scheduled": datetime.fromisoformat(plan["proposal"]["appointment_at"]) if (plan["proposal"] or {}).get("appointment_at") else None,
                },
            )
            work_id = str(order.scalar_one())
            work.append(work_id)
            step["work_order_id"] = work_id
        await db.execute(
            text("update tickets set status='assigned' where id=:id"), {"id": tid}
        )
    result = await db.execute(
        text(
            "update vh_ticket_plans set status=:status,steps=cast(:steps as jsonb),version=version+1,resident_by=:actor,resident_note=:note,resident_at=now(),updated_at=now() where id=:id returning *"
        ),
        {
            "status": status,
            "steps": json.dumps(steps),
            "actor": actor,
            "note": body.note,
            "id": plan_id,
        },
    )
    await record_event(
        (db, actor, False),
        dict(ticket),
        "plan.resident_decided",
        json.dumps({"planId": str(plan_id), "status": status, "workOrderIds": work}),
        to_status="assigned" if work else None,
    )
    if work and (plan["proposal"] or {}).get("performer_staff_id"):
        from .v3_request_presentation import offer_planned_work
        for work_id in work:
            await offer_planned_work(db, tid, UUID(work_id), plan)
    elif work and plan["proposed_by_agent_id"] and plan["management_by"] is None:
        # A plan the Supervisor approved itself: it also hands the work to an available technician.
        from .work_offers import offer_work
        for work_id in work:
            await offer_work(db, tid, UUID(work_id), plan["proposed_by_agent_id"])
    return {**dict(result.mappings().one()), "workOrderIds": work}


@router.get("/resident/tickets/{ticket_id}/progress")
async def progress(ticket_id: UUID, scope: Resident):
    ticket = (
        (
            await scope[0].execute(
                text(
                    "select id,code,title,status,created_at,updated_at from tickets where id=:id and requester_user_id=:actor"
                ),
                {"id": ticket_id, "actor": scope[1]},
            )
        )
        .mappings()
        .first()
    )
    if ticket is None:
        raise HTTPException(404, "Ticket not found")
    events = await scope[0].execute(
        text(
            "select id,seq,event_type,to_status,occurred_at from ticket_events where ticket_id=:id and event_type in ('ticket.created','ticket.routing_accepted','ticket.status_changed','plan.management_decided','plan.resident_decided','work_order.offered','work_assignment.responded','work_order.status_changed') order by seq"
        ),
        {"id": ticket_id},
    )
    work = await scope[0].execute(
        text(
            "select id,status,description,completed_at from work_orders where ticket_id=:id order by created_at"
        ),
        {"id": ticket_id},
    )
    return {
        "ticket": dict(ticket),
        "milestones": [dict(r) for r in events.mappings()],
        "workOrders": [dict(r) for r in work.mappings()],
    }
