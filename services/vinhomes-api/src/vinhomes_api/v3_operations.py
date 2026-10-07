"""V3 operations endpoints shared by the Operations screens."""

from typing import Annotated, Literal
from uuid import UUID
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .password_auth import surface
from .v3_agent_results import AgentBusinessResponse, agent_result
from .v3_auth import TICKET_VISIBILITY, scoped_connection
from .v3_mutations import record_event, visible_ticket

router = APIRouter(tags=["Vinhomes V3 operations"])
Scope = Annotated[tuple[AsyncConnection, str, bool], Depends(scoped_connection, scope="function")]


def params(scope: Scope) -> dict[str, object]:
    return {"user_id": scope[1], "is_admin": scope[2]}


def rows(result: object) -> list[dict[str, object]]:
    return [dict(row) for row in result.mappings().all()]


def wrong_door(door: str, role: str) -> str | None:
    """Why this role does not sign in at this front door. A door that names nothing serves every role."""
    if door == "field" and role != "staff":
        return "Địa chỉ này dành cho nhân viên hiện trường. Ban quản lý và quản trị đăng nhập ở địa chỉ của Ban quản lý."
    if door == "operations" and role == "staff":
        return "Địa chỉ này dành cho Ban quản lý. Nhân viên hiện trường đăng nhập ở địa chỉ dành cho nhân viên."
    return None


@router.get("/operations/me")
async def operations_me(request: Request, scope: Scope):
    db, actor, admin = scope
    user = (await db.execute(text("select id,name,email from users where id=:id"), {"id": actor})).mappings().one()
    grants = await db.execute(text("""
        select distinct r.role_code from scoped_user_roles r join tenant_memberships m
          on m.id=r.membership_id and m.tenant_id=r.tenant_id
        where m.user_id=:id and m.status='active' and r.valid_from<=now()
          and (r.valid_to is null or r.valid_to>now())
    """), {"id": actor})
    roles = list(grants.scalars())
    role = "admin" if admin else "management" if "management" in roles else "staff"
    if refusal := wrong_door(surface(request), role):
        raise HTTPException(403, {"code": "WRONG_DOOR", "message": refusal})
    return {"user": dict(user), "role": role,
            "dataMode": "local-database" if request.app.state.settings.demo_mode or request.app.state.settings.dev_user_id else "database"}


@router.get("/operations-profile", summary="Authenticated operations identity and actual grants")
async def operations_profile(scope: Scope):
    db, actor, admin = scope
    user = (await db.execute(text("select id,name from users where id=:id"), {"id": actor})).mappings().one()
    roles = (await db.execute(text("""select distinct r.role_code from scoped_user_roles r
      join tenant_memberships m on m.id=r.membership_id and m.tenant_id=r.tenant_id
      where m.user_id=:actor and m.status='active' and r.valid_from<=now()
        and (r.valid_to is null or r.valid_to>now())
        and r.tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid"""), {"actor": actor})).scalars().all()
    return {"user": dict(user), "roles": sorted(roles), "isAdmin": admin,
            "canManage": admin or "management" in roles}


@router.get("/catalogs", summary="Domains, sites, buildings and operations catalogs")
async def catalogs(scope: Scope) -> dict[str, object]:
    db = scope[0]
    # Catalog data remains tenant-scoped by the database RLS policy.
    queries = {
        "domains": "select id, code, name from domains where status='active' order by name",
        "sites": "select id, domain_id, code, name from sites where status='active' order by name",
        "zones": "select id, site_id, code, name from zones where status='active' order by name",
        "buildings": "select id, site_id, zone_id, code, name from buildings where status='active' order by name",
        "managementUnits": "select id, code, name from management_units where status='active' order by name",
        "serviceCategories": "select id, parent_id, code, name from service_categories where enabled order by name",
        "incidentTypes": "select id, category_id, code, name from incident_types order by name",
        "staff": "select sp.id, sp.user_id, sp.management_unit_id, sp.employee_code, sp.availability, u.name from staff_profiles sp join users u on u.id=sp.user_id where sp.active and u.status='active' order by u.name",
    }
    return {key: rows(await db.execute(text(query))) for key, query in queries.items()}


@router.get("/dashboard", summary="Operations counts from V3")
async def dashboard(scope: Scope) -> dict[str, object]:
    db = scope[0]
    ticket_counts = await db.execute(text(f"""
        select t.status, t.priority, count(*) as count from tickets t
        where {TICKET_VISIBILITY} group by t.status, t.priority
    """), params(scope))
    work_counts = await db.execute(text(f"""
        select w.status, count(*) as count from work_orders w
        join tickets t on t.id=w.ticket_id and t.tenant_id=w.tenant_id
        where {TICKET_VISIBILITY} group by w.status
    """), params(scope))
    approval_counts = await db.execute(text(f"""
        select a.status, count(*) as count from work_approvals a
        join work_orders w on w.id=a.work_order_id and w.tenant_id=a.tenant_id
        join tickets t on t.id=w.ticket_id and t.tenant_id=w.tenant_id
        where {TICKET_VISIBILITY} group by a.status
    """), params(scope))
    return {"tickets": rows(ticket_counts), "workOrders": rows(work_counts), "approvals": rows(approval_counts)}


@router.get("/my-work-orders", summary="Work orders assigned to the current user")
async def my_work_orders(scope: Scope, limit: int = Query(50, ge=1, le=100)) -> dict[str, object]:
    result = await scope[0].execute(text(f"""
        select w.*, a.id as assignment_id,
               case when a.status='offered' and a.offer_expires_at<=now()
                 then 'expired' else a.status end as assignment_status,
               (select approval.status from work_approvals approval
                where approval.work_order_id=w.id and approval.tenant_id=w.tenant_id
                  and approval.kind='customer_repair'
                order by approval.created_at desc,approval.id desc limit 1) as repair_approval_status,
               t.code as ticket_code, t.title as ticket_title
        from work_assignments a
        join staff_profiles sp on sp.id=a.staff_id and sp.tenant_id=a.tenant_id
        join work_orders w on w.id=a.work_order_id and w.tenant_id=a.tenant_id
        join tickets t on t.id=w.ticket_id and t.tenant_id=w.tenant_id
        where sp.user_id=:user_id and {TICKET_VISIBILITY}
        order by a.created_at desc limit :limit
    """), {**params(scope), "limit": limit})
    return {"items": rows(result)}


@router.get("/staff/available", summary="Available staff in a management unit")
async def available_staff(
    scope: Scope,
    management_unit_id: UUID = Query(..., alias="managementUnitId"),
    category_id: UUID = Query(..., alias="categoryId"),
) -> dict[str, object]:
    db, actor_id, is_admin = scope
    if not is_admin:
        permission = await db.execute(text("""
            select 1 from scoped_user_roles r
            join tenant_memberships m on m.id=r.membership_id and m.tenant_id=r.tenant_id
            join access_scopes s on s.id=r.scope_id and s.tenant_id=r.tenant_id
            where m.user_id=:actor_id and m.status='active' and r.role_code='management'
              and r.valid_from<=now() and (r.valid_to is null or r.valid_to>now())
              and r.tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
              and (s.kind='tenant' or
                   (s.kind='management' and s.management_unit_id=:management_unit_id))
            limit 1
        """), {"actor_id": actor_id, "management_unit_id": management_unit_id})
        if permission.first() is None:
            raise HTTPException(403, "Management scope required")
    result = await db.execute(text("""
        select sp.id, sp.employee_code, sp.management_unit_id,
               sp.max_concurrent_jobs, count(wa.id) as active_jobs
        from staff_profiles sp
        join staff_specialties ss on ss.staff_id=sp.id and ss.tenant_id=sp.tenant_id
        join users u on u.id=sp.user_id and u.status='active'
        left join work_assignments wa on wa.staff_id=sp.id and wa.tenant_id=sp.tenant_id
             and (wa.status='accepted' or (wa.status='offered' and wa.offer_expires_at>now()))
             and exists (select 1 from work_orders busy where busy.id=wa.work_order_id
               and busy.tenant_id=wa.tenant_id and busy.status not in ('completed','cancelled','rejected'))
        where sp.management_unit_id=:management_unit_id and ss.category_id=:category_id
          and sp.tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
          and sp.active and ss.active and sp.availability='available'
          and exists (select 1 from staff_shifts sh where sh.staff_id=sp.id
                      and sh.tenant_id=sp.tenant_id and sh.status='available'
                      and sh.starts_at<=now() and sh.ends_at>now())
        group by sp.id
        having count(wa.id)<sp.max_concurrent_jobs
        order by count(wa.id), sp.id
    """), {"management_unit_id": management_unit_id, "category_id": category_id})
    return {"items": rows(result)}


@router.get("/tasks", summary="Human operations tasks derived from V3 work orders")
async def tasks(scope: Scope, status: str | None = None,
                limit: int = Query(100, ge=1, le=200)) -> dict[str, object]:
    result = await scope[0].execute(text(f"""
        select w.id, w.ticket_id, w.description as title, w.status,
               w.category_id, w.scheduled_at, w.completed_at, w.version,
               t.code as ticket_code, t.priority as ticket_priority,
               sp.user_id as assignee_user_id, a.id as assignment_id
        from work_orders w
        join tickets t on t.id=w.ticket_id and t.tenant_id=w.tenant_id
        left join lateral (
          select wa.id,wa.staff_id from work_assignments wa
          where wa.work_order_id=w.id and wa.status in ('offered','accepted')
          order by wa.created_at desc limit 1
        ) a on true
        left join staff_profiles sp on sp.id=a.staff_id and sp.tenant_id=w.tenant_id
        where {TICKET_VISIBILITY}
          and (cast(:status as text) is null or w.status=:status)
        order by w.created_at desc limit :limit
    """), {**params(scope), "status": status, "limit": limit})
    return {"items": rows(result)}


@router.get("/approvals", summary="Work approval queue")
async def approvals(scope: Scope, status: str | None = None,
                    limit: int = Query(50, ge=1, le=100)) -> dict[str, object]:
    result = await scope[0].execute(text(f"""
        select a.*, w.ticket_id, t.code as ticket_code, t.title as ticket_title
        from work_approvals a
        join work_orders w on w.id=a.work_order_id and w.tenant_id=a.tenant_id
        join tickets t on t.id=w.ticket_id and t.tenant_id=w.tenant_id
        where {TICKET_VISIBILITY}
          and a.kind in ('management_water_shutdown','management_security_dispatch','management_security_cancel')
          and (cast(:status as text) is null or a.status=:status)
          and (:is_admin or a.requested_to_user_id=:user_id
               or (a.required_scope_id is not null and exists (
                   select 1 from scoped_user_roles r
                   join tenant_memberships m on m.id=r.membership_id and m.tenant_id=r.tenant_id
                   join access_scopes s on s.id=r.scope_id and s.tenant_id=r.tenant_id
                   where (r.scope_id=a.required_scope_id or s.kind='tenant')
                     and r.tenant_id=a.tenant_id
                     and m.user_id=:user_id and m.status='active'
                     and r.role_code='management' and r.valid_from<=now()
                     and (r.valid_to is null or r.valid_to>now()))))
        order by a.created_at desc limit :limit
    """), {**params(scope), "status": status, "limit": limit})
    return {"items": rows(result)}


@router.get("/tickets/{ticket_id}/evidence", summary="Evidence for a ticket")
async def ticket_evidence(ticket_id: UUID, scope: Scope) -> dict[str, object]:
    result = await scope[0].execute(text(f"""
        select e.id, e.ticket_id, e.work_order_id, e.assignment_id, e.file_id,
               e.purpose, e.caption, e.provenance, e.status, e.captured_at,
               e.uploaded_at, f.original_name, f.declared_mime_type
        from evidence_items e
        join tickets t on t.id=e.ticket_id and t.tenant_id=e.tenant_id
        join files f on f.id=e.file_id and f.tenant_id=e.tenant_id
        where t.id=:ticket_id and {TICKET_VISIBILITY}
        order by e.uploaded_at desc
    """), {**params(scope), "ticket_id": ticket_id})
    return {"items": rows(result)}


@router.get("/tickets/{ticket_id}/timeline", summary="Ticket event timeline")
async def ticket_timeline(ticket_id: UUID, scope: Scope) -> dict[str, object]:
    result = await scope[0].execute(text(f"""
        select ev.id, ev.seq, ev.event_type, ev.from_status, ev.to_status,
               ev.actor_kind, ev.actor_user_id, ev.payload, ev.occurred_at
        from ticket_events ev
        join tickets t on t.id=ev.ticket_id and t.tenant_id=ev.tenant_id
        where t.id=:ticket_id and {TICKET_VISIBILITY}
        order by ev.seq desc limit 200
    """), {**params(scope), "ticket_id": ticket_id})
    return {"items": rows(result)}


@router.post("/tickets/{ticket_id}/routing/ack",
             summary="Responsible management accepts a routed resident ticket")
async def acknowledge_ticket_routing(ticket_id: UUID, scope: Scope) -> dict[str, object]:
    db, actor_id, _ = scope
    ticket = await visible_ticket(scope, ticket_id, lock=True)
    grant = await db.execute(text("""
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
    """), {"actor_id": actor_id,
           "management_unit_id": ticket["management_unit_id"],
           "site_id": ticket["site_id"], "zone_id": ticket["zone_id"],
           "building_id": ticket["building_id"]})
    if grant.first() is None:
        raise HTTPException(403, "Responsible management role required")
    routing = await db.execute(text("""
        select id, status from ticket_routing_history
        where ticket_id=:ticket_id and to_management_id=cast(:management_unit_id as uuid)
          and tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
        order by requested_at desc limit 1 for update
    """), {"ticket_id": ticket_id,
           "management_unit_id": ticket["management_unit_id"]})
    route = routing.mappings().first()
    if route is None:
        raise HTTPException(404, "Routing request not found")
    if route["status"] != "requested":
        raise HTTPException(409, "Routing request is no longer pending")
    event_id = await record_event(scope, ticket, "ticket.routing_accepted",
                                  json.dumps({"routingId": str(route["id"])}))
    updated = await db.execute(text("""
        update ticket_routing_history set status='accepted', ack_event_id=:event_id,
            acknowledged_at=now() where id=:id
        returning id, ticket_id, status, acknowledged_at
    """), {"id": route["id"], "event_id": event_id})
    await db.execute(text("""
        insert into notification_deliveries
          (tenant_id, user_id, ticket_event_id, channel, dedupe_key,
           payload, status, available_at)
        select t.tenant_id, t.requester_user_id, :event_id, 'in_app',
               :dedupe_key, cast(:payload as jsonb), 'pending', now()
        from tickets t where t.id=:ticket_id
          and t.tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
        on conflict (tenant_id, user_id, channel, dedupe_key) do nothing
    """), {"ticket_id": ticket_id, "event_id": event_id,
           "dedupe_key": f"ticket:{ticket_id}:routing-accepted",
           "payload": json.dumps({"type": "ticket.routing_accepted",
                                  "ticketId": str(ticket_id)})})
    return dict(updated.mappings().one())


class ApprovalDecision(BaseModel):
    status: Literal["approved", "rejected"]
    note: str = Field(min_length=1, max_length=2000)


@router.post("/approvals/{approval_id}/decision", summary="Approve or reject a work request", response_model=AgentBusinessResponse)
async def decide_approval(approval_id: UUID, body: ApprovalDecision, scope: Scope) -> dict[str, object]:
    db, actor_id, _ = scope
    result = await db.execute(text(f"""
        select a.id, a.status, a.kind, a.requested_to_user_id, a.required_scope_id,
               w.ticket_id, t.management_unit_id, t.site_id, t.zone_id, t.building_id
        from work_approvals a
        join work_orders w on w.id=a.work_order_id and w.tenant_id=a.tenant_id
        join tickets t on t.id=w.ticket_id and t.tenant_id=w.tenant_id
        where a.id=:approval_id and {TICKET_VISIBILITY}
    """), {**params(scope), "approval_id": approval_id})
    approval = result.mappings().first()
    if approval is None:
        raise HTTPException(404, "Approval not found")
    if approval["kind"] in {"management_security_dispatch", "management_security_cancel"}:
        from .v3_security import decide_security
        return agent_result("approval.decision", await decide_security(approval_id, body.status, body.note, scope), {"approval_id": approval_id, "ticket_id": approval["ticket_id"]})
    if approval["kind"] != "management_water_shutdown":
        raise HTTPException(403, "This approval requires its assigned customer")
    ticket = await visible_ticket(scope, approval["ticket_id"], lock=True)
    locked = await db.execute(text("""
        select status, expires_at is null or expires_at>now() as unexpired
        from work_approvals where id=:id for update
    """), {"id": approval_id})
    locked_approval = locked.mappings().one()
    if locked_approval["status"] != "pending" or not locked_approval["unexpired"]:
        raise HTTPException(409, "Approval is no longer pending")
    grant = await db.execute(text("""
        select 1 from scoped_user_roles r
        join tenant_memberships m on m.id=r.membership_id and m.tenant_id=r.tenant_id
        join access_scopes s on s.id=r.scope_id and s.tenant_id=r.tenant_id
        where r.tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
          and m.user_id=:user_id and m.status='active' and r.role_code='management'
          and r.valid_from<=now() and (r.valid_to is null or r.valid_to>now())
          and (s.kind='tenant'
            or (s.kind='management' and s.management_unit_id=cast(:management_unit_id as uuid))
            or (s.kind='site' and s.site_id=cast(:site_id as uuid))
            or (s.kind='zone' and s.zone_id=cast(:zone_id as uuid))
            or (s.kind='building' and s.building_id=cast(:building_id as uuid)))
          and (cast(:required_scope_id as uuid) is null or r.scope_id=cast(:required_scope_id as uuid)
               or s.kind='tenant')
        limit 1
    """), {"user_id": actor_id, "management_unit_id": approval["management_unit_id"],
           "site_id": approval["site_id"], "zone_id": approval["zone_id"],
           "building_id": approval["building_id"],
           "required_scope_id": approval["required_scope_id"]})
    if grant.first() is None or (approval["requested_to_user_id"] is not None
                                 and approval["requested_to_user_id"] != actor_id):
        raise HTTPException(403, "Responsible management approval required")
    updated = await db.execute(text("""
        update work_approvals set status=:status, decided_by=:user_id,
          decided_at=now(), decision_note=:note, updated_at=now()
        where id=:approval_id
        returning id, work_order_id, status, decided_by, decided_at, decision_note
    """), {"status": body.status, "note": body.note, "user_id": actor_id, "approval_id": approval_id})
    decision = dict(updated.mappings().one())
    await db.execute(text("""
        update service_interruptions
        set status=:interruption_status, updated_at=now()
        where approval_id=:approval_id and status='proposed'
    """), {"approval_id": approval_id,
           "interruption_status": "approved" if body.status == "approved" else "cancelled"})
    event_id = await record_event(scope, ticket, "work_approval.decided",
                                  json.dumps({"approvalId": str(approval_id), "status": body.status}))
    await db.execute(text("""
        update work_approvals set decided_event_id=:event_id where id=:approval_id
    """), {"event_id": event_id, "approval_id": approval_id})
    return agent_result("approval.decision", decision, {"approval_id": approval_id, "ticket_id": approval["ticket_id"]})
