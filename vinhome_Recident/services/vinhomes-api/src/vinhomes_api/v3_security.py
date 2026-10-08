"""Database-backed emergency notifications and management security approvals."""


import hashlib
import json
from datetime import datetime, timezone, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .v3_agent_results import AgentBusinessResponse, agent_result
from .v3_auth import scoped_connection, TICKET_VISIBILITY
from .v3_mutations import visible_ticket, record_event, management_access
from .v3_water import _responsible_management

router = APIRouter(tags=["Vinhomes V3 emergency security"])
Scope = Annotated[tuple[AsyncConnection, str, bool], Depends(scoped_connection)]
TENANT = "nullif(current_setting('app.tenant_id',true),'')::uuid"


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str).encode()
    ).hexdigest()


async def building_access(scope: Scope, building_id: UUID) -> dict[str, object]:
    result = await scope[0].execute(
        text(f"""
        select b.id,b.site_id,b.zone_id from buildings b
        where b.id=:id and b.tenant_id={TENANT} and (:admin or exists (
          select 1 from scoped_user_roles r
          join tenant_memberships m on m.id=r.membership_id and m.tenant_id=r.tenant_id
          join access_scopes s on s.id=r.scope_id and s.tenant_id=r.tenant_id
          where m.user_id=:actor and m.status='active' and r.role_code in ('staff','management')
            and r.valid_from<=now() and (r.valid_to is null or r.valid_to>now())
            and (s.kind='tenant' or (s.kind='building' and s.building_id=b.id)
              or (s.kind='site' and s.site_id=b.site_id) or (s.kind='zone' and s.zone_id=b.zone_id))))
    """),
        {"id": building_id, "actor": scope[1], "admin": scope[2]},
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(404, "Building is outside your scope")
    return dict(row)


@router.get("/security/cameras", response_model=AgentBusinessResponse)
async def cameras(
    scope: Scope, building_id: UUID = Query(..., alias="buildingId")
) -> dict[str, object]:
    await building_access(scope, building_id)
    result = await scope[0].execute(
        text("select * from security_cameras where building_id=:id order by code"),
        {"id": building_id},
    )
    return agent_result(
        "security.camera.read",
        {"items": [dict(row) for row in result.mappings()]},
        {"building_id": building_id},
    )


@router.get("/security/emergency-contacts", response_model=AgentBusinessResponse)
async def contacts(
    scope: Scope, building_id: UUID = Query(..., alias="buildingId")
) -> dict[str, object]:
    await building_access(scope, building_id)
    result = await scope[0].execute(
        text("""
        select id,name,role_label,phone,position,ack_timeout_seconds,status
        from security_emergency_contacts where building_id=:id order by position
    """),
        {"id": building_id},
    )
    return agent_result(
        "security.contact.read",
        {"items": [dict(row) for row in result.mappings()]},
        {"building_id": building_id},
    )


async def notification(
    scope: Scope,
    user_id: str,
    key: str,
    payload: dict[str, object],
    event_id: UUID | None = None,
) -> None:
    await scope[0].execute(
        text(f"""
        insert into notification_deliveries(tenant_id,user_id,ticket_event_id,channel,dedupe_key,payload,status,available_at)
        values ({TENANT},:user,:event,'in_app',:key,cast(:payload as jsonb),'pending',now())
        on conflict (tenant_id,user_id,channel,dedupe_key) do nothing
    """),
        {
            "user": user_id,
            "event": event_id,
            "key": key,
            "payload": json.dumps(payload, default=str),
        },
    )


async def next_recipient(scope: Scope, alert_id: UUID) -> bool:
    db = scope[0]
    result = await db.execute(
        text("""
        select d.id,d.recipient_user_id from security_alert_deliveries d
        join users u on u.id=d.recipient_user_id and u.status='active'
        join tenant_memberships m on m.user_id=u.id and m.tenant_id=d.tenant_id and m.status='active'
        where d.alert_id=:id and d.status='waiting' order by d.position limit 1 for update of d
    """),
        {"id": alert_id},
    )
    recipient = result.mappings().first()
    if recipient is None:
        await db.execute(
            text(
                "update security_alerts set status='exhausted',updated_at=now() where id=:id"
            ),
            {"id": alert_id},
        )
        await db.execute(
            text(
                "update security_alert_deliveries set status='cancelled' where alert_id=:id and status='waiting'"
            ),
            {"id": alert_id},
        )
        return False
    await db.execute(
        text("""
        update security_alert_deliveries set status='pending',notified_at=now(),
          deadline_at=now()+make_interval(secs=>ack_timeout_seconds) where id=:id
    """),
        {"id": recipient["id"]},
    )
    await notification(
        scope,
        recipient["recipient_user_id"],
        f"alert:{alert_id}:{recipient['id']}",
        {
            "type": "security.alert",
            "alertId": alert_id,
            "message": "Có cảnh báo khẩn cấp cần xác nhận",
        },
    )
    return True


async def alert_detail(scope: Scope, alert_id: UUID) -> dict[str, object]:
    result = await scope[0].execute(
        text("select * from security_alerts where id=:id"), {"id": alert_id}
    )
    alert = result.mappings().first()
    if alert is None:
        raise HTTPException(404, "Alert not found")
    await visible_ticket(scope, alert["ticket_id"])
    deliveries = await scope[0].execute(
        text("""
        select d.*,c.name,c.role_label from security_alert_deliveries d
        join security_emergency_contacts c on c.id=d.contact_id and c.tenant_id=d.tenant_id
        where d.alert_id=:id order by d.position
    """),
        {"id": alert_id},
    )
    return {**dict(alert), "deliveries": [dict(row) for row in deliveries.mappings()]}


class AlertCreate(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    ticket_version: int = Field(ge=0)
    idempotency_key: str = Field(min_length=1, max_length=160)


@router.post(
    "/tickets/{ticket_id}/emergency-alerts",
    status_code=201,
    response_model=AgentBusinessResponse,
)
async def create_alert(
    ticket_id: UUID, body: AlertCreate, scope: Scope
) -> dict[str, object]:
    ticket = await visible_ticket(scope, ticket_id, lock=True)
    await _responsible_management(scope, ticket)
    fingerprint = digest(body.model_dump(exclude={"idempotency_key", "ticket_version"}))
    previous = await scope[0].execute(
        text("""
        select id,request_hash,created_by from security_alerts where ticket_id=:id and idempotency_key=:key
    """),
        {"id": ticket_id, "key": body.idempotency_key},
    )
    old = previous.mappings().first()
    if old:
        if old["request_hash"] != fingerprint or old["created_by"] != scope[1]:
            raise HTTPException(409, "Alert key already used with different request")
        return agent_result(
            "security.alert.create",
            await alert_detail(scope, old["id"]),
            {"ticket_id": ticket_id},
        )
    if ticket["version"] != body.ticket_version:
        raise HTTPException(409, "Ticket version changed")
    if not ticket["is_emergency"] or ticket["status"] in {"closed", "cancelled"}:
        raise HTTPException(409, "An active emergency ticket is required")
    if not ticket["building_id"]:
        raise HTTPException(409, "Emergency ticket requires a building")
    result = await scope[0].execute(
        text(f"""
        insert into security_alerts(tenant_id,ticket_id,created_by,message,idempotency_key,request_hash)
        values ({TENANT},:ticket,:actor,:message,:key,:hash) returning id
    """),
        {
            "ticket": ticket_id,
            "actor": scope[1],
            "message": body.message,
            "key": body.idempotency_key,
            "hash": fingerprint,
        },
    )
    alert_id = result.scalar_one()
    inserted = await scope[0].execute(
        text(f"""
        insert into security_alert_deliveries(tenant_id,alert_id,contact_id,recipient_user_id,position,ack_timeout_seconds)
        select c.tenant_id,:alert,c.id,c.user_id,c.position,c.ack_timeout_seconds
        from security_emergency_contacts c
        join users u on u.id=c.user_id and u.status='active'
        join tenant_memberships m on m.user_id=u.id and m.tenant_id=c.tenant_id and m.status='active'
        where c.building_id=:building and c.status='active' and c.tenant_id={TENANT} returning id
    """),
        {"alert": alert_id, "building": ticket["building_id"]},
    )
    if not inserted.all():
        raise HTTPException(409, "No active emergency recipients configured")
    await next_recipient(scope, alert_id)
    await record_event(
        scope, ticket, "security.alert_created", json.dumps({"alertId": str(alert_id)})
    )
    return agent_result(
        "security.alert.create",
        await alert_detail(scope, alert_id),
        {"ticket_id": ticket_id},
    )


@router.get("/security/alerts", response_model=AgentBusinessResponse)
async def alerts(
    scope: Scope, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)
) -> dict[str, object]:
    result = await scope[0].execute(
        text(f"""
        select a.id,t.title as ticket_title from security_alerts a
        join tickets t on t.id=a.ticket_id and t.tenant_id=a.tenant_id
        where {TICKET_VISIBILITY} order by a.created_at desc limit :limit offset :offset
    """),
        {"user_id": scope[1], "is_admin": scope[2], "limit": limit, "offset": offset},
    )
    items = [
        {**await alert_detail(scope, row["id"]), "ticket_title": row["ticket_title"]}
        for row in result.mappings()
    ]
    return agent_result(
        "security.alert.read",
        {
            "items": items,
            "nextOffset": offset + len(items) if len(items) == limit else None,
        },
        {"limit": limit, "offset": offset},
    )


class AlertAction(BaseModel):
    version: int = Field(ge=0)


async def lock_alert(
    scope: Scope, alert_id: UUID
) -> tuple[dict[str, object], dict[str, object]]:
    result = await scope[0].execute(
        text("select ticket_id from security_alerts where id=:id"), {"id": alert_id}
    )
    ticket_id = result.scalar_one_or_none()
    if ticket_id is None:
        raise HTTPException(404, "Alert not found")
    ticket = await visible_ticket(scope, ticket_id, lock=True)
    result = await scope[0].execute(
        text("select * from security_alerts where id=:id for update"), {"id": alert_id}
    )
    return dict(result.mappings().one()), ticket


@router.post("/security/alerts/{alert_id}/ack", response_model=AgentBusinessResponse)
async def ack_alert(
    alert_id: UUID, body: AlertAction, scope: Scope
) -> dict[str, object]:
    alert, ticket = await lock_alert(scope, alert_id)
    acknowledged = await scope[0].execute(
        text(
            "select 1 from security_alert_deliveries where alert_id=:id and recipient_user_id=:actor and status='acknowledged'"
        ),
        {"id": alert_id, "actor": scope[1]},
    )
    if alert["status"] == "acknowledged" and acknowledged.first():
        return agent_result(
            "security.alert.ack",
            await alert_detail(scope, alert_id),
            {"alert_id": alert_id},
        )
    if alert["status"] != "open" or alert["version"] != body.version:
        raise HTTPException(409, "Alert state or version changed")
    pending = await scope[0].execute(
        text(
            "select * from security_alert_deliveries where alert_id=:id and status='pending' for update"
        ),
        {"id": alert_id},
    )
    recipient = pending.mappings().first()
    if recipient is None or recipient["recipient_user_id"] != scope[1]:
        raise HTTPException(403, "Only the current alert recipient can ACK")
    if recipient["deadline_at"] <= datetime.now(timezone.utc):
        raise HTTPException(409, "ACK deadline passed; management must escalate")
    await scope[0].execute(
        text(
            "update security_alert_deliveries set status='acknowledged',acknowledged_at=now() where id=:id"
        ),
        {"id": recipient["id"]},
    )
    await scope[0].execute(
        text(
            "update security_alert_deliveries set status='cancelled' where alert_id=:id and status='waiting'"
        ),
        {"id": alert_id},
    )
    await scope[0].execute(
        text(
            "update security_alerts set status='acknowledged',version=version+1,updated_at=now() where id=:id"
        ),
        {"id": alert_id},
    )
    event = await record_event(
        scope,
        ticket,
        "security.alert_acknowledged",
        json.dumps({"alertId": str(alert_id)}),
    )
    await notification(
        scope,
        alert["created_by"],
        f"alert:{alert_id}:ack",
        {"type": "security.alert_acknowledged", "alertId": alert_id},
        event,
    )
    return agent_result(
        "security.alert.ack",
        await alert_detail(scope, alert_id),
        {"alert_id": alert_id},
    )


@router.post(
    "/security/alerts/{alert_id}/escalate", response_model=AgentBusinessResponse
)
async def escalate_alert(
    alert_id: UUID, body: AlertAction, scope: Scope
) -> dict[str, object]:
    alert, ticket = await lock_alert(scope, alert_id)
    await _responsible_management(scope, ticket)
    if alert["status"] != "open" or alert["version"] != body.version:
        raise HTTPException(409, "Alert state or version changed")
    pending = await scope[0].execute(
        text(
            "select * from security_alert_deliveries where alert_id=:id and status='pending' for update"
        ),
        {"id": alert_id},
    )
    recipient = pending.mappings().first()
    if recipient is None or recipient["deadline_at"] > datetime.now(timezone.utc):
        raise HTTPException(409, "Current recipient still has time to ACK")
    await scope[0].execute(
        text("update security_alert_deliveries set status='timed_out' where id=:id"),
        {"id": recipient["id"]},
    )
    has_next = await next_recipient(scope, alert_id)
    await scope[0].execute(
        text(
            "update security_alerts set version=version+1,updated_at=now() where id=:id"
        ),
        {"id": alert_id},
    )
    event = await record_event(
        scope,
        ticket,
        "security.alert_escalated",
        json.dumps({"alertId": str(alert_id), "hasNext": has_next}),
    )
    if not has_next:
        await notification(
            scope,
            alert["created_by"],
            f"alert:{alert_id}:exhausted",
            {"type": "security.alert_exhausted", "alertId": alert_id},
            event,
        )
    return agent_result(
        "security.alert.escalate",
        await alert_detail(scope, alert_id),
        {"alert_id": alert_id},
    )


class SecurityRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)
    work_order_version: int = Field(ge=0)
    idempotency_key: str = Field(min_length=1, max_length=160)


class DispatchRequest(SecurityRequest):
    staff_id: UUID


async def security_work(
    scope: Scope, work_order_id: UUID
) -> tuple[dict[str, object], dict[str, object]]:
    row = await scope[0].execute(
        text("select ticket_id from work_orders where id=:id"), {"id": work_order_id}
    )
    ticket_id = row.scalar_one_or_none()
    if ticket_id is None:
        raise HTTPException(404, "Work order not found")
    ticket = await visible_ticket(scope, ticket_id, lock=True)
    result = await scope[0].execute(
        text("""
        select w.*,c.code as category_code from work_orders w
        join service_categories c on c.id=w.category_id and c.tenant_id=w.tenant_id
        where w.id=:id for update of w
    """),
        {"id": work_order_id},
    )
    order = dict(result.mappings().one())
    if order["category_code"] != "security":
        raise HTTPException(422, "Security work order required")
    return order, ticket


async def request_security(
    scope: Scope, work_order_id: UUID, body: SecurityRequest, kind: str
) -> dict[str, object]:
    order, ticket = await security_work(scope, work_order_id)
    if not await management_access(scope, ticket):
        assigned = await scope[0].execute(
            text("""
            select 1 from work_assignments a join staff_profiles sp on sp.id=a.staff_id
            where a.work_order_id=:id and a.status='accepted' and sp.user_id=:actor
        """),
            {"id": work_order_id, "actor": scope[1]},
        )
        if assigned.first() is None:
            raise HTTPException(
                403, "Responsible management or assigned guard required"
            )
    detail = {**body.model_dump(mode="json"), "requested_by": scope[1]}
    fingerprint = digest(detail)
    previous = await scope[0].execute(
        text("""
        select * from work_approvals where work_order_id=:id and kind=:kind
          and request_detail->>'idempotency_key'=:key
    """),
        {"id": work_order_id, "kind": kind, "key": body.idempotency_key},
    )
    old = previous.mappings().first()
    if old:
        if old["request_hash"] != fingerprint:
            raise HTTPException(
                409, "Security request key reused with different content"
            )
        return dict(old)
    if order["version"] != body.work_order_version or order["status"] in {
        "completed",
        "cancelled",
        "rejected",
    }:
        raise HTTPException(409, "Work order state or version changed")
    if ticket["status"] in {"closed", "cancelled"}:
        raise HTTPException(409, "Ticket is no longer active")
    if kind == "management_security_dispatch" and order["status"] != "queued":
        raise HTTPException(409, "Guard dispatch requires a queued work order")
    if kind == "management_security_dispatch":
        valid_staff = await scope[0].execute(
            text("""
            select 1 from staff_profiles sp join staff_specialties ss on ss.staff_id=sp.id and ss.tenant_id=sp.tenant_id
            join users u on u.id=sp.user_id and u.status='active'
            where sp.id=:id and sp.active and ss.active and ss.category_id=:category
              and sp.management_unit_id=:management
        """),
            {
                "id": body.staff_id,
                "category": order["category_id"],
                "management": ticket["management_unit_id"],
            },
        )
        if valid_staff.first() is None:
            raise HTTPException(
                422, "Active guard with matching specialty and management unit required"
            )
    existing = await scope[0].execute(
        text(
            "select 1 from work_approvals where work_order_id=:id and kind=:kind and status='pending' and (expires_at is null or expires_at>now())"
        ),
        {"id": work_order_id, "kind": kind},
    )
    if existing.first():
        raise HTTPException(409, "A security approval is already pending")
    recipient_scope = await scope[0].execute(
        text(
            "select id from access_scopes where kind='management' and management_unit_id=:id"
        ),
        {"id": ticket["management_unit_id"]},
    )
    scope_id = recipient_scope.scalar_one_or_none()
    if scope_id is None:
        raise HTTPException(409, "Responsible management scope is missing")
    result = await scope[0].execute(
        text(f"""
        insert into work_approvals(tenant_id,work_order_id,kind,required_scope_id,request_detail,status,expires_at,request_hash)
        values ({TENANT},:work,:kind,:scope,cast(:detail as jsonb),'pending',now()+interval '1 hour',:hash) returning *
    """),
        {
            "work": work_order_id,
            "kind": kind,
            "scope": scope_id,
            "detail": json.dumps(detail),
            "hash": fingerprint,
        },
    )
    approval = dict(result.mappings().one())
    event = await record_event(
        scope,
        ticket,
        "security.approval_requested",
        json.dumps({"approvalId": str(approval["id"]), "kind": kind}),
    )
    recipients = await scope[0].execute(
        text("""
        select distinct m.user_id from scoped_user_roles r
        join tenant_memberships m on m.id=r.membership_id and m.tenant_id=r.tenant_id
        where r.scope_id=:scope and r.role_code='management' and m.status='active'
          and r.valid_from<=now() and (r.valid_to is null or r.valid_to>now())
    """),
        {"scope": scope_id},
    )
    for user in recipients.scalars():
        await notification(
            scope,
            user,
            f"security-approval:{approval['id']}",
            {"type": "security.approval_requested", "approvalId": approval["id"]},
            event,
        )
    return approval


@router.post(
    "/work-orders/{work_order_id}/security/dispatch-request",
    status_code=201,
    response_model=AgentBusinessResponse,
)
async def dispatch_request(
    work_order_id: UUID, body: DispatchRequest, scope: Scope
) -> dict[str, object]:
    return agent_result(
        "security.dispatch_request",
        await request_security(
            scope, work_order_id, body, "management_security_dispatch"
        ),
        {"work_order_id": work_order_id},
    )


@router.post(
    "/work-orders/{work_order_id}/security/cancel-request",
    status_code=201,
    response_model=AgentBusinessResponse,
)
async def cancel_request(
    work_order_id: UUID, body: SecurityRequest, scope: Scope
) -> dict[str, object]:
    return agent_result(
        "security.cancel_request",
        await request_security(
            scope, work_order_id, body, "management_security_cancel"
        ),
        {"work_order_id": work_order_id},
    )


async def decide_security(
    approval_id: UUID, status: str, note: str, scope: Scope
) -> dict[str, object]:
    found = await scope[0].execute(
        text("select work_order_id from work_approvals where id=:id"),
        {"id": approval_id},
    )
    work_id = found.scalar_one_or_none()
    if work_id is None:
        raise HTTPException(404, "Approval not found")
    order, ticket = await security_work(scope, work_id)
    await _responsible_management(scope, ticket)
    result = await scope[0].execute(
        text(
            "select *,expires_at is null or expires_at>now() as unexpired from work_approvals where id=:id for update"
        ),
        {"id": approval_id},
    )
    approval = dict(result.mappings().one())
    if approval["status"] != "pending":
        if (
            approval["status"] == status
            and approval["decided_by"] == scope[1]
            and approval["decision_note"] == note
        ):
            return approval
        raise HTTPException(409, "Security approval already decided")
    if not approval["unexpired"]:
        raise HTTPException(409, "Security approval expired")
    grant = await scope[0].execute(
        text("""
        select 1 from scoped_user_roles r join tenant_memberships m on m.id=r.membership_id and m.tenant_id=r.tenant_id
        join access_scopes s on s.id=r.scope_id and s.tenant_id=r.tenant_id
        where m.user_id=:actor and m.status='active' and r.role_code='management'
          and (r.scope_id=:scope or s.kind='tenant') and r.valid_from<=now() and (r.valid_to is null or r.valid_to>now())
    """),
        {"actor": scope[1], "scope": approval["required_scope_id"]},
    )
    if grant.first() is None:
        raise HTTPException(403, "Approval management scope required")
    if status == "approved" and (
        order["version"] != approval["request_detail"]["work_order_version"]
        or order["status"] in {"completed", "cancelled", "rejected"}
    ):
        raise HTTPException(409, "Work order changed after security request")
    await scope[0].execute(
        text(
            "update work_approvals set status=:status,decision_note=:note,decided_by=:actor,decided_at=now(),updated_at=now() where id=:id"
        ),
        {"status": status, "note": note, "actor": scope[1], "id": approval_id},
    )
    if status == "approved" and approval["kind"] == "management_security_dispatch":
        from .v3_mutations import create_assignment, AssignmentCreate

        await create_assignment(
            work_id,
            AssignmentCreate(
                staff_id=approval["request_detail"]["staff_id"],
                work_order_version=order["version"],
                offer_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            ),
            scope,
        )
        ticket = await visible_ticket(scope, ticket["id"], lock=True)
    elif status == "approved" and approval["kind"] == "management_security_cancel":
        await scope[0].execute(
            text(
                "update work_assignments set status='cancelled',updated_at=now() where work_order_id=:id and status in ('offered','accepted')"
            ),
            {"id": work_id},
        )
        await scope[0].execute(
            text(
                "update work_orders set status='cancelled',version=version+1,updated_at=now() where id=:id"
            ),
            {"id": work_id},
        )
        active = await scope[0].execute(
            text(
                "select 1 from work_orders where ticket_id=:id and status not in ('completed','cancelled','rejected') limit 1"
            ),
            {"id": ticket["id"]},
        )
        if active.first() is None and ticket["status"] not in {"closed", "resolved"}:
            await scope[0].execute(
                text(
                    "update tickets set status='cancelled',updated_at=now() where id=:id"
                ),
                {"id": ticket["id"]},
            )
    event = await record_event(
        scope,
        ticket,
        "security.approval_decided",
        json.dumps({"approvalId": str(approval_id), "status": status}),
    )
    await scope[0].execute(
        text("update work_approvals set decided_event_id=:event where id=:id"),
        {"event": event, "id": approval_id},
    )
    await notification(
        scope,
        approval["request_detail"]["requested_by"],
        f"security-approval:{approval_id}:decision",
        {
            "type": "security.approval_decided",
            "approvalId": approval_id,
            "status": status,
        },
        event,
    )
    if status == "approved":
        guards = await scope[0].execute(
            text("""
            select distinct sp.user_id from work_assignments a
            join staff_profiles sp on sp.id=a.staff_id and sp.tenant_id=a.tenant_id
            where a.work_order_id=:work and a.status in ('offered','accepted','cancelled')
        """),
            {"work": work_id},
        )
        for guard in guards.scalars():
            await notification(
                scope,
                guard,
                f"security-approval:{approval_id}:guard",
                {
                    "type": "security.approval_decided",
                    "approvalId": approval_id,
                    "status": status,
                },
                event,
            )
    result = await scope[0].execute(
        text("select * from work_approvals where id=:id"), {"id": approval_id}
    )
    return dict(result.mappings().one())
