"""Active V3 read API. The retired vh_* routes are intentionally not mounted."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .v3_auth import TICKET_VISIBILITY, scoped_connection

router = APIRouter(tags=["Vinhomes V3"])
Scope = Annotated[tuple[AsyncConnection, str, bool], Depends(scoped_connection, scope="function")]


def _params(scope: Scope) -> dict[str, object]:
    _, actor_id, is_admin = scope
    return {"user_id": actor_id, "is_admin": is_admin}


def _rows(result: object) -> list[dict[str, object]]:
    return [dict(row) for row in result.mappings().all()]


@router.get("/management-units/resolve", summary="Resolve management unit for a building and domain")
async def resolve_management_unit(
    scope: Scope,
    building_id: UUID = Query(..., alias="buildingId"),
    domain_id: UUID = Query(..., alias="domainId"),
    service_category_id: UUID | None = Query(None, alias="serviceCategoryId"),
) -> dict[str, object]:
    connection, _, _ = scope
    params = {**_params(scope), "building_id": building_id, "domain_id": domain_id,
              "service_category_id": service_category_id}
    building = await connection.execute(text("""
        select b.id, b.site_id, b.zone_id from buildings b
        join sites si on si.id=b.site_id and si.tenant_id=b.tenant_id
        join domains d on d.id=si.domain_id and d.tenant_id=b.tenant_id
        where b.id=:building_id and d.id=:domain_id
          and b.tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
          and b.status='active' and si.status='active' and d.status='active'
    """), params)
    location = building.mappings().first()
    if location is None:
        raise HTTPException(404, "Active building not found in this domain")
    params = {**params, "site_id": location["site_id"], "zone_id": location["zone_id"]}
    scope_match = """s.kind='tenant'
        or (s.kind='site' and s.site_id=:site_id)
        or (s.kind='zone' and s.zone_id=cast(:zone_id as uuid))
        or (s.kind='building' and s.building_id=:building_id)"""
    access = await connection.execute(text(f"""
        select :is_admin or exists (
            select 1 from scoped_user_roles r
            join tenant_memberships m on m.id=r.membership_id and m.tenant_id=r.tenant_id
            join access_scopes s on s.id=r.scope_id and s.tenant_id=r.tenant_id
            where m.user_id=:user_id and m.status='active'
              and r.role_code in ('management','staff')
              and r.valid_from<=now() and (r.valid_to is null or r.valid_to>now())
              and r.tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
              and ({scope_match})
        )
    """), params)
    if not access.scalar_one():
        raise HTTPException(403, "Building is outside your operations scope")
    coverages = await connection.execute(text(f"""
        select mc.management_unit_id, mc.service_category_id, mc.priority,
               case s.kind when 'building' then 4 when 'zone' then 3
                   when 'site' then 2 else 1 end as specificity
        from management_coverage mc
        join access_scopes s on s.id=mc.scope_id and s.tenant_id=mc.tenant_id
        join management_units mu on mu.id=mc.management_unit_id and mu.tenant_id=mc.tenant_id
        where mc.tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
          and mu.status='active'
          and mc.valid_from<=now() and (mc.valid_to is null or mc.valid_to>now())
          and (cast(:service_category_id as uuid) is null
               or mc.service_category_id=cast(:service_category_id as uuid))
          and ({scope_match})
        order by mc.service_category_id, specificity desc, mc.priority desc
    """), params)
    best_by_category: dict[UUID, dict[str, object]] = {}
    for row in coverages.mappings():
        category = row["service_category_id"]
        previous = best_by_category.get(category)
        if previous is None:
            best_by_category[category] = dict(row)
        elif (row["specificity"], row["priority"]) == (previous["specificity"], previous["priority"]):
            if row["management_unit_id"] != previous["management_unit_id"]:
                raise HTTPException(409, "Multiple management units have equal coverage priority")
    if not best_by_category:
        raise HTTPException(404, "No active management coverage for this building")
    unit_ids = {row["management_unit_id"] for row in best_by_category.values()}
    if len(unit_ids) != 1:
        raise HTTPException(409, "Management unit varies by service category; provide serviceCategoryId")
    return {"managementUnitId": next(iter(unit_ids)), "buildingId": building_id,
            "domainId": domain_id, "serviceCategoryId": service_category_id}


@router.get("/tickets", summary="Danh sách ticket V3")
async def list_tickets(
    scope: Scope,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0, le=100000),
    status: str | None = None,
    building_id: UUID | None = Query(None, alias="buildingId"),
    priority: str | None = None,
) -> dict[str, object]:
    connection, _, _ = scope
    result = await connection.execute(text(f"""
        select t.id, t.code, t.request_kind, t.title, t.description,
               t.status, t.priority, t.severity, t.triage_status,
               t.is_emergency, t.site_id, t.zone_id, t.building_id,
               t.management_unit_id, t.category_id, t.assigned_team_id,
               t.response_due_at, t.resolution_due_at, t.created_at,
               t.updated_at, t.version
        from tickets t
        where {TICKET_VISIBILITY}
          and (cast(:status as text) is null or t.status=:status)
          and (cast(:building_id as uuid) is null or t.building_id=cast(:building_id as uuid))
          and (cast(:priority as text) is null or t.priority=:priority)
        order by t.created_at desc, t.id desc
        limit :limit offset :offset
    """), {**_params(scope), "limit": limit, "offset": offset,
           "status": status, "building_id": building_id, "priority": priority})
    items = _rows(result)
    return {"items": items, "nextOffset": offset + len(items) if len(items) == limit else None}


@router.get("/tickets/{ticket_id}", summary="Ticket, sự kiện và work order")
async def get_ticket(ticket_id: UUID, scope: Scope) -> dict[str, object]:
    connection, _, _ = scope
    params = {**_params(scope), "ticket_id": ticket_id}
    ticket = await connection.execute(text(f"""
        select t.id, t.code, t.request_kind, t.title, t.description,
               t.status, t.priority, t.severity, t.triage_status,
               t.is_emergency, t.site_id, t.zone_id, t.building_id,
               t.management_unit_id, t.category_id, t.assigned_team_id,
               t.response_due_at, t.resolution_due_at, t.created_at,
               t.updated_at, t.version
        from tickets t where t.id=:ticket_id and {TICKET_VISIBILITY}
    """), params)
    row = ticket.mappings().first()
    if row is None:
        raise HTTPException(404, "Ticket not found")
    events = await connection.execute(text("""
        select id, seq, event_type, from_status, to_status, occurred_at, payload
        from ticket_events where ticket_id=:ticket_id order by seq desc limit 100
    """), params)
    orders = await connection.execute(text("""
        select * from work_orders where ticket_id=:ticket_id
        order by created_at desc limit 100
    """), params)
    return {"ticket": dict(row), "events": _rows(events), "workOrders": _rows(orders)}


@router.get("/tickets/{ticket_id}/triage", summary="Assessment và quyết định triage")
async def get_ticket_triage(ticket_id: UUID, scope: Scope) -> dict[str, object]:
    connection, _, _ = scope
    params = {**_params(scope), "ticket_id": ticket_id}
    ticket = await connection.execute(text(f"""
        select t.id, t.version, t.triage_status from tickets t
        where t.id=:ticket_id and {TICKET_VISIBILITY}
    """), params)
    row = ticket.mappings().first()
    if row is None:
        raise HTTPException(404, "Ticket not found")
    assessments = await connection.execute(text("""
        select * from ticket_assessments where ticket_id=:ticket_id
        order by created_at desc limit 100
    """), params)
    decisions = await connection.execute(text("""
        select * from ticket_triage_decisions where ticket_id=:ticket_id
        order by created_at desc limit 100
    """), params)
    reviews = await connection.execute(text("""
        select * from ticket_triage_reviews where ticket_id=:ticket_id
        order by created_at desc limit 100
    """), params)
    return {"ticket": dict(row), "assessments": _rows(assessments),
            "decisions": _rows(decisions), "reviews": _rows(reviews)}


@router.get("/work-orders", summary="Danh sách work order V3")
async def list_work_orders(
    scope: Scope,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0, le=100000),
    ticket_id: UUID | None = Query(None, alias="ticketId"),
    status: str | None = None,
) -> dict[str, object]:
    connection, _, _ = scope
    result = await connection.execute(text(f"""
        select w.*, t.code as ticket_code from work_orders w
        join tickets t on t.id=w.ticket_id and t.tenant_id=w.tenant_id
        where {TICKET_VISIBILITY}
          and (cast(:ticket_id as uuid) is null or t.id=cast(:ticket_id as uuid))
          and (cast(:status as text) is null or w.status=:status)
        order by w.created_at desc, w.id desc
        limit :limit offset :offset
    """), {**_params(scope), "ticket_id": ticket_id, "status": status,
           "limit": limit, "offset": offset})
    items = _rows(result)
    return {"items": items, "nextOffset": offset + len(items) if len(items) == limit else None}


@router.get("/dispatch-queue", summary="Queued work orders in my operations scope")
async def dispatch_queue(scope: Scope, limit: int = Query(50, ge=1, le=100)) -> dict[str, object]:
    return await list_work_orders(scope, limit, 0, None, "queued")


@router.get("/work-orders/{work_order_id}", summary="Work order, phân công và phê duyệt")
async def get_work_order(work_order_id: UUID, scope: Scope) -> dict[str, object]:
    connection, _, _ = scope
    params = {**_params(scope), "work_order_id": work_order_id}
    order = await connection.execute(text(f"""
        select w.*, t.code as ticket_code from work_orders w
        join tickets t on t.id=w.ticket_id and t.tenant_id=w.tenant_id
        where w.id=:work_order_id and {TICKET_VISIBILITY}
    """), params)
    row = order.mappings().first()
    if row is None:
        raise HTTPException(404, "Work order not found")
    assignments = await connection.execute(text("""
        select * from work_assignments where work_order_id=:work_order_id
        order by created_at desc limit 100
    """), params)
    approvals = await connection.execute(text("""
        select * from work_approvals where work_order_id=:work_order_id
        order by created_at desc limit 100
    """), params)
    qc = await connection.execute(text("""
        select * from vh_qc_results where work_order_id=:work_order_id
        order by checked_at desc limit 100
    """), params)
    redo = await connection.execute(text("""
        select * from vh_qc_redo_orders where source_work_order_id=:work_order_id
    """), params)
    return {"workOrder": dict(row), "assignments": _rows(assignments),
            "approvals": _rows(approvals), "qcResults": _rows(qc), "redoOrders": _rows(redo)}
