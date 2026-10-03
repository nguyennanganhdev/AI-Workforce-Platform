"""Water interruption lifecycle with management approval and resident notices."""


import hashlib
import json
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .v3_agent_results import AgentBusinessResponse, agent_result
from .v3_auth import scoped_connection
from .v3_mutations import record_event, visible_ticket


router = APIRouter(tags=["Vinhomes V3 water interruptions"])
Scope = Annotated[tuple[AsyncConnection, str, bool], Depends(scoped_connection, scope="function")]


class WaterShutdownRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)
    affected_scope_id: UUID
    planned_start: datetime
    planned_end: datetime

    @model_validator(mode="after")
    def valid_period(self) -> "WaterShutdownRequest":
        if (self.planned_start.tzinfo is None or self.planned_end.tzinfo is None
                or self.planned_start >= self.planned_end):
            raise ValueError("planned_start and planned_end must be ordered timestamps with timezone")
        return self


async def _work(scope: Scope, work_order_id: UUID) -> dict[str, object]:
    result = await scope[0].execute(text("""
        select w.id, w.ticket_id, t.building_id, t.zone_id,
               t.management_unit_id, t.site_id
        from work_orders w join tickets t on t.id=w.ticket_id and t.tenant_id=w.tenant_id
        where w.id=:work_order_id
          and w.tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
    """), {"work_order_id": work_order_id})
    row = result.mappings().first()
    if row is None:
        raise HTTPException(404, "Work order not found")
    await visible_ticket(scope, row["ticket_id"])
    return dict(row)


async def _assigned_staff(scope: Scope, work_order_id: UUID) -> None:
    result = await scope[0].execute(text("""
        select 1 from work_assignments a
        join staff_profiles sp on sp.id=a.staff_id and sp.tenant_id=a.tenant_id
        where a.work_order_id=:work_order_id and a.status='accepted'
          and sp.user_id=:actor_id and sp.active
          and a.tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
        limit 1
    """), {"work_order_id": work_order_id, "actor_id": scope[1]})
    if result.first() is None:
        raise HTTPException(403, "Accepted work assignment required")


async def _responsible_management(scope: Scope, work: dict[str, object]) -> None:
    result = await scope[0].execute(text("""
        select 1 from scoped_user_roles r
        join tenant_memberships m on m.id=r.membership_id and m.tenant_id=r.tenant_id
        join access_scopes s on s.id=r.scope_id and s.tenant_id=r.tenant_id
        where m.user_id=:actor_id and m.status='active' and r.role_code='management'
          and r.valid_from<=now() and (r.valid_to is null or r.valid_to>now())
          and r.tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
          and (s.kind='tenant'
            or (s.kind='management' and s.management_unit_id=cast(:management_unit_id as uuid))
            or (s.kind='site' and s.site_id=cast(:site_id as uuid))
            or (s.kind='zone' and s.zone_id=cast(:zone_id as uuid))
            or (s.kind='building' and s.building_id=cast(:building_id as uuid)))
        limit 1
    """), {"actor_id": scope[1], **{key: work[key] for key in
           ("management_unit_id", "site_id", "zone_id", "building_id")}})
    if result.first() is None:
        raise HTTPException(403, "Responsible management scope required")


@router.post("/work-orders/{work_order_id}/water-shutdown-request", status_code=201,
             summary="Request approval for a scoped water shutdown", response_model=AgentBusinessResponse)
async def request_water_shutdown(work_order_id: UUID, body: WaterShutdownRequest,
                                 scope: Scope) -> dict[str, object]:
    db = scope[0]
    work = await _work(scope, work_order_id)
    await _assigned_staff(scope, work_order_id)
    ticket = await visible_ticket(scope, work["ticket_id"], lock=True)
    affected = await db.execute(text("""
        select id from access_scopes where id=:scope_id
          and tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
          and ((kind='building' and building_id=cast(:building_id as uuid))
               or (kind='zone' and zone_id=cast(:zone_id as uuid)))
    """), {"scope_id": body.affected_scope_id,
           "building_id": work["building_id"], "zone_id": work["zone_id"]})
    if affected.first() is None:
        raise HTTPException(422, "Affected scope must be this building or zone")
    manager_scope = await db.execute(text("""
        select id from access_scopes where kind='management'
          and management_unit_id=cast(:management_unit_id as uuid)
          and tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
        order by id limit 1
    """), {"management_unit_id": work["management_unit_id"]})
    required_scope_id = manager_scope.scalar_one_or_none()
    if required_scope_id is None:
        raise HTTPException(409, "Management approval scope is not configured")
    details = {"reason": body.reason, "affectedScopeId": str(body.affected_scope_id),
               "plannedStart": body.planned_start.isoformat(),
               "plannedEnd": body.planned_end.isoformat()}
    request_hash = hashlib.sha256(json.dumps(details, sort_keys=True).encode()).hexdigest()
    prior = await db.execute(text("""
        select si.id, si.approval_id, si.status from service_interruptions si
        join work_approvals a on a.id=si.approval_id and a.tenant_id=si.tenant_id
        where si.work_order_id=:work_order_id and a.request_hash=:request_hash
          and si.status not in ('cancelled','restored')
        order by si.created_at desc limit 1
    """), {"work_order_id": work_order_id, "request_hash": request_hash})
    old = prior.mappings().first()
    if old is not None:
        return agent_result('utility_isolation.request', dict(old), {'work_order_id': work_order_id})
    approval = await db.execute(text("""
        insert into work_approvals
          (tenant_id, work_order_id, kind, required_scope_id, request_detail,
           status, request_hash)
        values (nullif(current_setting('app.tenant_id', true), '')::uuid,
                :work_order_id, 'management_water_shutdown', :required_scope_id,
                cast(:detail as jsonb), 'pending', :request_hash)
        returning id
    """), {"work_order_id": work_order_id, "required_scope_id": required_scope_id,
           "detail": json.dumps(details), "request_hash": request_hash})
    approval_id = approval.scalar_one()
    interruption = await db.execute(text("""
        insert into service_interruptions
          (tenant_id, work_order_id, approval_id, utility, reason,
           planned_start, planned_end, status)
        values (nullif(current_setting('app.tenant_id', true), '')::uuid,
                :work_order_id, :approval_id, 'water', :reason,
                :planned_start, :planned_end, 'proposed')
        returning id, approval_id, status
    """), {"work_order_id": work_order_id, "approval_id": approval_id,
           "reason": body.reason, "planned_start": body.planned_start,
           "planned_end": body.planned_end})
    created = dict(interruption.mappings().one())
    await db.execute(text("""
        insert into interruption_scopes (tenant_id, interruption_id, scope_id)
        values (nullif(current_setting('app.tenant_id', true), '')::uuid,
                :interruption_id, :scope_id)
    """), {"interruption_id": created["id"], "scope_id": body.affected_scope_id})
    await record_event(scope, ticket, "water.shutdown_requested",
                       json.dumps({"interruptionId": str(created["id"]),
                                   "approvalId": str(approval_id)}))
    return agent_result('utility_isolation.request', created, {'work_order_id': work_order_id})


@router.get("/work-orders/{work_order_id}/water-interruptions",
            summary="List water interruptions for a visible work order", response_model=AgentBusinessResponse)
async def water_interruptions(work_order_id: UUID, scope: Scope) -> dict[str, object]:
    await _work(scope, work_order_id)
    result = await scope[0].execute(text("""
        select id, approval_id, reason, planned_start, planned_end,
               actual_start, actual_end, status, created_at
        from service_interruptions where work_order_id=:work_order_id and utility='water'
          and tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
        order by created_at desc limit 100
    """), {"work_order_id": work_order_id})
    return agent_result('water.read', {"items": [dict(row) for row in result.mappings()]}, {'work_order_id': work_order_id})


async def _interruption(scope: Scope, interruption_id: UUID) -> tuple[dict[str, object], dict[str, object]]:
    found = await scope[0].execute(text("""
        select si.id, si.work_order_id from service_interruptions si
        where si.id=:id and si.utility='water'
          and si.tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
    """), {"id": interruption_id})
    row = found.mappings().first()
    if row is None:
        raise HTTPException(404, "Water interruption not found")
    work = await _work(scope, row["work_order_id"])
    ticket = await visible_ticket(scope, work["ticket_id"], lock=True)
    locked = await scope[0].execute(text("""
        select id, work_order_id, approval_id, status, planned_start, planned_end
        from service_interruptions where id=:id for update
    """), {"id": interruption_id})
    return dict(locked.mappings().one()), ticket


async def _notify_affected(db: AsyncConnection, interruption_id: UUID,
                           event: Literal["shutdown", "restored"]) -> None:
    await db.execute(text("""
        insert into notification_deliveries
          (tenant_id, user_id, interruption_id, channel, dedupe_key,
           payload, status, available_at)
        select si.tenant_id, ur.user_id, si.id, 'in_app', :dedupe_key,
               cast(:payload as jsonb), 'pending', now()
        from service_interruptions si
        join interruption_scopes isc on isc.interruption_id=si.id and isc.tenant_id=si.tenant_id
        join access_scopes s on s.id=isc.scope_id and s.tenant_id=isc.tenant_id
        join units u on u.tenant_id=si.tenant_id
          and ((s.kind='building' and u.building_id=s.building_id)
               or (s.kind='zone' and u.zone_id=s.zone_id))
        join unit_residents ur on ur.unit_id=u.id and ur.tenant_id=u.tenant_id
        join users person on person.id=ur.user_id and person.status='active'
        where si.id=:interruption_id and ur.verification_status='verified'
          and ur.valid_from<=now() and (ur.valid_to is null or ur.valid_to>now())
        on conflict (tenant_id, user_id, channel, dedupe_key) do nothing
    """), {"interruption_id": interruption_id,
           "dedupe_key": f"water:{interruption_id}:{event}",
           "payload": json.dumps({"type": f"water.{event}",
                                  "interruptionId": str(interruption_id)})})


@router.post("/water-interruptions/{interruption_id}/notify",
             summary="Notify affected residents after management approval", response_model=AgentBusinessResponse)
async def notify_water_shutdown(interruption_id: UUID, scope: Scope) -> dict[str, object]:
    interruption, ticket = await _interruption(scope, interruption_id)
    work = await _work(scope, interruption["work_order_id"])
    await _responsible_management(scope, work)
    if interruption["status"] != "approved":
        raise HTTPException(409, "Management approval is required before notice")
    await _notify_affected(scope[0], interruption_id, "shutdown")
    updated = await scope[0].execute(text("""
        update service_interruptions set status='notified', updated_at=now()
        where id=:id returning id, status
    """), {"id": interruption_id})
    await record_event(scope, ticket, "water.shutdown_notified",
                       json.dumps({"interruptionId": str(interruption_id)}))
    return agent_result('water.notify', dict(updated.mappings().one()), {'interruption_id': interruption_id})


@router.post("/water-interruptions/{interruption_id}/start",
             summary="Record that the approved water shutdown began", response_model=AgentBusinessResponse)
async def start_water_shutdown(interruption_id: UUID, scope: Scope) -> dict[str, object]:
    interruption, ticket = await _interruption(scope, interruption_id)
    await _assigned_staff(scope, interruption["work_order_id"])
    if interruption["status"] != "notified":
        raise HTTPException(409, "Residents must be notified before shutdown")
    updated = await scope[0].execute(text("""
        update service_interruptions set status='active', actual_start=now(),
            operated_by=:actor_id, updated_at=now()
        where id=:id returning id, status, actual_start
    """), {"id": interruption_id, "actor_id": scope[1]})
    await record_event(scope, ticket, "water.shutdown_started",
                       json.dumps({"interruptionId": str(interruption_id)}))
    return agent_result('water.start', dict(updated.mappings().one()), {'interruption_id': interruption_id})


@router.post("/water-interruptions/{interruption_id}/restore",
             summary="Record water restoration and notify residents", response_model=AgentBusinessResponse)
async def restore_water(interruption_id: UUID, scope: Scope) -> dict[str, object]:
    interruption, ticket = await _interruption(scope, interruption_id)
    await _assigned_staff(scope, interruption["work_order_id"])
    if interruption["status"] != "active":
        raise HTTPException(409, "Water interruption is not active")
    updated = await scope[0].execute(text("""
        update service_interruptions set status='restored', actual_end=now(),
            operated_by=:actor_id, updated_at=now()
        where id=:id returning id, status, actual_end
    """), {"id": interruption_id, "actor_id": scope[1]})
    await _notify_affected(scope[0], interruption_id, "restored")
    await record_event(scope, ticket, "water.restored",
                       json.dumps({"interruptionId": str(interruption_id)}))
    return agent_result('water.restore', dict(updated.mappings().one()), {'interruption_id': interruption_id})
