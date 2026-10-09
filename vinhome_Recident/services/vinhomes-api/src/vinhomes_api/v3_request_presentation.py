"""Scoped facts and editable plan presentation for the management request screen.

Schedules live on the existing plan aggregate and cannot bypass either approval.
"""
import json
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .v3_audit import audit
from .v3_auth import TICKET_VISIBILITY, scoped_connection
from .v3_mutations import management_access, record_event, visible_ticket

router = APIRouter(tags=["Vinhomes request presentation"])
Scope = Annotated[tuple[AsyncConnection, str, bool], Depends(scoped_connection, scope="function")]
TENANT = "nullif(current_setting('app.tenant_id',true),'')::uuid"


@router.get("/tickets/{ticket_id}/conversation", summary="What the resident and Reception said about a ticket")
async def ticket_conversation(ticket_id: UUID, scope: Scope) -> dict[str, object]:
    await visible_ticket(scope, ticket_id)
    rows = await scope[0].execute(text(f"""
        select m.id,m.seq,m.sender_kind,m.body->>'text' as text,m.created_at from messages m
        where m.channel_id=(select channel_id from tickets where id=:ticket) and m.tenant_id={TENANT} and m.visibility in ('room','customer')
          and m.body->>'text'<>'' order by m.seq desc limit 100
    """), {"ticket": ticket_id})
    return {"items": [dict(row) for row in rows.mappings()][::-1]}


@router.get("/tickets/{ticket_id}/presentation")
async def presentation(ticket_id: UUID, scope: Scope):
    await visible_ticket(scope, ticket_id)
    db = scope[0]
    resident = (await db.execute(text(f"""
        select coalesce(nullif(t.contact_name,''),u.name) as name,t.contact_phone as phone,
               t.unit_id,t.building_id
        from tickets t left join users u on u.id=t.requester_user_id
        where t.id=:ticket and t.tenant_id={TENANT}
    """), {"ticket": ticket_id})).mappings().one()
    result = {"resident": {key: resident[key] for key in ("name", "phone") if resident[key]}, "participants": [], "events": []}
    plan = (await db.execute(text(f"""
        select p.proposal,(select u.name from staff_profiles sp join users u on u.id=sp.user_id
          where sp.id::text=p.proposal->>'performer_staff_id' and sp.tenant_id=p.tenant_id) as performer_name
        from vh_ticket_plans p where p.ticket_id=:ticket and p.tenant_id={TENANT}
        order by p.created_at desc limit 1
    """), {"ticket": ticket_id})).mappings().first()
    if plan:
        proposal = plan["proposal"] or {}
        result["schedule"] = {key: proposal[key] for key in ("performer_staff_id", "appointment_at") if proposal.get(key)}
        if plan["performer_name"]:
            result["schedule"]["performer_name"] = plan["performer_name"]
    if resident["unit_id"]:
        history = (await db.execute(text(f"""
            select t.id,t.title,t.status from tickets t where t.unit_id=:unit and t.id<>:ticket
              and {TICKET_VISIBILITY} order by t.created_at desc limit 10
        """), {"unit": resident["unit_id"], "ticket": ticket_id, "user_id": scope[1], "is_admin": scope[2]})).mappings().all()
        result["apartment_history"] = [dict(row) for row in history]
    photos = (await db.execute(text(f"""
        select distinct f.id,f.original_name as name from ticket_files tf
        join files f on f.id=tf.file_id and f.tenant_id=tf.tenant_id
        where tf.ticket_id=:ticket and tf.tenant_id={TENANT} and f.status='ready'
          and f.declared_mime_type like 'image/%'
    """), {"ticket": ticket_id})).mappings().all()
    result["photos"] = [dict(row) for row in photos]
    return result


class PlanPresentation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=0)
    summary: str = Field(min_length=1, max_length=300)
    steps: list[str] = Field(min_length=1, max_length=20)
    performer_staff_id: UUID | None = None
    appointment_at: datetime | None = None

    @field_validator("summary")
    @classmethod
    def summary_text(cls, value):
        if not value.strip():
            raise ValueError("Phương án không được để trống")
        return value.strip()

    @field_validator("steps")
    @classmethod
    def step_text(cls, values):
        if any(not value.strip() or len(value.strip()) > 2000 for value in values):
            raise ValueError("Mỗi bước cần có nội dung và tối đa 2000 ký tự")
        if len("\n".join(values)) > 1900:
            raise ValueError("Các bước thực hiện quá dài; tối đa 1900 ký tự")
        return [value.strip() for value in values]

    @field_validator("appointment_at")
    @classmethod
    def aware_appointment(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError("Giờ hẹn cần có múi giờ")
        return value


@router.patch("/plans/{plan_id}/presentation")
async def edit_plan(plan_id: UUID, body: PlanPresentation, scope: Scope):
    db = scope[0]
    ticket_id = (await db.execute(text(f"select ticket_id from vh_ticket_plans where id=:id and tenant_id={TENANT}"), {"id": plan_id})).scalar_one_or_none()
    if ticket_id is None:
        raise HTTPException(404, "Không tìm thấy phương án")
    ticket = await visible_ticket(scope, ticket_id, lock=True)
    if not await management_access(scope, ticket):
        raise HTTPException(403, "Bạn không có quyền sửa phương án của đơn vị này")
    plan = (await db.execute(text(f"select * from vh_ticket_plans where id=:id and tenant_id={TENANT} for update"), {"id": plan_id})).mappings().one()
    if plan["status"] != "management_pending" or plan["version"] != body.version:
        raise HTTPException(409, "Phương án đã thay đổi hoặc đã được duyệt. Tải lại để kiểm tra.")
    if ticket["status"] in {"closed", "cancelled", "resolved"}:
        raise HTTPException(409, "Yêu cầu đã kết thúc")
    if body.performer_staff_id:
        staff = (await db.execute(text(f"""
            select sp.id from staff_profiles sp join users u on u.id=sp.user_id and u.status='active'
            where sp.id=:staff and sp.tenant_id={TENANT} and sp.active
              and sp.management_unit_id=:unit
              and exists(select 1 from staff_specialties ss where ss.staff_id=sp.id and ss.tenant_id=sp.tenant_id
                and ss.category_id=:category and ss.active)
        """), {"staff": body.performer_staff_id, "unit": ticket["management_unit_id"], "category": ticket["category_id"]})).first()
        if staff is None:
            raise HTTPException(422, "Người thực hiện cần thuộc đơn vị và có chuyên môn phù hợp")
    if body.appointment_at and body.appointment_at <= datetime.now(timezone.utc):
        raise HTTPException(422, "Giờ hẹn cần nằm trong tương lai")
    proposal = {**(plan["proposal"] or {}), "summary": body.summary, "steps": body.steps,
                "performer_staff_id": str(body.performer_staff_id) if body.performer_staff_id else None,
                "appointment_at": body.appointment_at.isoformat() if body.appointment_at else None}
    # Supervisor steps describe one visit. Preserve its execution category and one work-order aggregate.
    executable = [{"category_id": str(ticket["category_id"]), "description": "\n".join(f"{i}. {line}" for i, line in enumerate(body.steps, 1))}]
    if not ticket["category_id"]:
        raise HTTPException(422, "Yêu cầu cần được phân loại trước khi sửa phương án")
    if not plan["proposed_by_client_id"]:
        # Manual plans can carry distinct categories: do not collapse that execution model.
        if len(plan["steps"]) != len(body.steps):
            raise HTTPException(422, "Phương án nhiều chuyên môn cần giữ nguyên số bước")
        executable = [{**step, "description": body.steps[i]} for i, step in enumerate(plan["steps"])]
    changed = (await db.execute(text(f"""
        update vh_ticket_plans set title=:title,proposal=cast(:proposal as jsonb),steps=cast(:steps as jsonb),
          version=version+1,updated_at=now() where id=:id and tenant_id={TENANT} returning id,version
    """), {"id": plan_id, "title": body.summary, "proposal": json.dumps(proposal, ensure_ascii=False), "steps": json.dumps(executable, ensure_ascii=False)})).mappings().one()
    payload = {"planId": str(plan_id), "performerStaffId": proposal["performer_staff_id"], "appointmentAt": proposal["appointment_at"]}
    await record_event(scope, ticket, "plan.presentation_updated", json.dumps(payload))
    await audit(db, scope[1], "plan.presentation_updated", "ticket_plan", str(plan_id), payload)
    return dict(changed)

async def offer_planned_work(db, ticket_id: UUID, work_order_id: UUID, plan) -> bool:
    """Offer the named performer after consent; an unavailable performer leaves a human hand-back.

    An appointment is a scheduled visit, not permission to skip a staff member's acceptance.
    """
    proposal = plan["proposal"] or {}
    staff_id = proposal.get("performer_staff_id")
    if not staff_id:
        return False
    # Security dispatch keeps its independent management authorization gate.
    category_code = (await db.execute(text("select c.code from work_orders w join service_categories c on c.id=w.category_id and c.tenant_id=w.tenant_id where w.id=:id"), {"id": work_order_id})).scalar_one()
    if category_code == "security":
        return False
    staff = (await db.execute(text(f"""
        select sp.id from staff_profiles sp join users u on u.id=sp.user_id and u.status='active'
        join tickets t on t.id=:ticket and t.tenant_id=sp.tenant_id
        join work_orders w on w.id=:work and w.ticket_id=t.id and w.tenant_id=t.tenant_id
        where sp.id=cast(:staff as uuid) and sp.tenant_id={TENANT} and sp.active
          and sp.management_unit_id=t.management_unit_id and sp.availability='available'
          and exists(select 1 from staff_specialties ss where ss.staff_id=sp.id and ss.tenant_id=sp.tenant_id
            and ss.category_id=w.category_id and ss.active)
          and exists(select 1 from staff_shifts sh where sh.staff_id=sp.id and sh.tenant_id=sp.tenant_id
            and sh.status='available' and sh.starts_at<=now() and sh.ends_at>now())
          and (select count(*) from work_assignments wa join work_orders busy on busy.id=wa.work_order_id
            and busy.tenant_id=wa.tenant_id where wa.staff_id=sp.id and wa.tenant_id=sp.tenant_id
            and busy.status not in ('completed','cancelled','rejected')
            and (wa.status='accepted' or (wa.status='offered' and wa.offer_expires_at>now()))) < sp.max_concurrent_jobs
        for update of sp
    """), {"ticket": ticket_id, "work": work_order_id, "staff": staff_id})).scalar_one_or_none()
    if staff is None:
        return False
    appointment = datetime.fromisoformat(proposal["appointment_at"]) if proposal.get("appointment_at") else None
    assignment = (await db.execute(text(f"""
        insert into work_assignments(tenant_id,work_order_id,staff_id,assigned_by_user_id,assigned_by_client_id,
          status,offered_at,offer_expires_at,eta_at)
        values({TENANT},:work,:staff,:person,:agent,'offered',now(),now()+interval '24 hours',:appointment) returning id
    """), {"work": work_order_id, "staff": staff, "person": plan["management_by"],
           "agent": plan["proposed_by_client_id"] if not plan["management_by"] else None, "appointment": appointment})).scalar_one()
    await db.execute(text("update work_orders set status='offered',version=version+1,updated_at=now() where id=:id"), {"id": work_order_id})
    payload = {"assignmentId": str(assignment), "performerStaffId": str(staff), "appointmentAt": proposal.get("appointment_at")}
    ticket = (await db.execute(text("select * from tickets where id=:id for update"), {"id": ticket_id})).mappings().one()
    if plan["management_by"]:
        await record_event((db, plan["management_by"], False), dict(ticket), "work_order.offered", json.dumps(payload))
    else:
        from .work_offers import agent_event
        await agent_event(db, ticket_id, plan["proposed_by_client_id"], "work_order.offered", payload)
    return True
