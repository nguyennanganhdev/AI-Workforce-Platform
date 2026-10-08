"""Scoped report aggregates and persistent DOCX export records."""


import json
from datetime import date
from typing import Annotated, Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection
from .v3_agent_results import AgentBusinessResponse, agent_result
from .v3_auth import scoped_connection
from .v3_reports import _management_building, _frequency, _issued_revenue, _docx
from .v3_security import digest

router = APIRouter(tags=["V3 extended reports"])
Scope = Annotated[tuple[AsyncConnection, str, bool], Depends(scoped_connection)]
TENANT = "nullif(current_setting('app.tenant_id',true),'')::uuid"


async def report_scope(scope: Scope, building: UUID, start: date, end: date):
    if start >= end or (end - start).days > 3660:
        raise HTTPException(422, "Ordered date range up to ten years required")
    await _management_building(scope, building)


@router.get("/reports/filter-options", response_model=AgentBusinessResponse)
async def options(scope: Scope):
    rows = await scope[0].execute(
        text("select id,name from buildings where status='active' order by name")
    )
    buildings = []
    for row in rows.mappings():
        try:
            await _management_building(scope, row["id"])
            buildings.append(dict(row))
        except HTTPException as exc:
            if exc.status_code != 403:
                raise
    if not buildings:
        raise HTTPException(403, "Management building scope required")
    categories = await scope[0].execute(
        text("select id,name,code from service_categories where enabled order by name")
    )
    staff = await scope[0].execute(
        text(
            "select distinct sp.id,u.name,sp.employee_code from staff_profiles sp join users u on u.id=sp.user_id join management_coverage mc on mc.management_unit_id=sp.management_unit_id and mc.tenant_id=sp.tenant_id join access_scopes s on s.id=mc.scope_id and s.tenant_id=mc.tenant_id join buildings b on (s.kind='tenant' or (s.kind='building' and s.building_id=b.id) or (s.kind='site' and s.site_id=b.site_id) or (s.kind='zone' and s.zone_id=b.zone_id)) and b.tenant_id=s.tenant_id where b.id=any(:ids) and mc.valid_from<=now() and (mc.valid_to is null or mc.valid_to>now())"
        ),
        {"ids": [b["id"] for b in buildings]},
    )
    return agent_result(
        "get_report_filter_options",
        {
            "buildings": buildings,
            "categories": [dict(r) for r in categories.mappings()],
            "employees": [dict(r) for r in staff.mappings()],
            "exportFormats": ["docx"],
        },
        {},
    )


@router.get("/reports/employee-performance", response_model=AgentBusinessResponse)
async def performance(
    scope: Scope,
    building_id: UUID = Query(..., alias="buildingId"),
    from_date: date = Query(..., alias="fromDate"),
    to_date: date = Query(..., alias="toDate"),
):
    await report_scope(scope, building_id, from_date, to_date)
    rows = await scope[0].execute(
        text("""with jobs as (
      select distinct sp.id as staff_id,u.name,w.id as work_id,w.status,w.completed_at,w.started_at,t.resolution_due_at
      from work_assignments a join staff_profiles sp on sp.id=a.staff_id and sp.tenant_id=a.tenant_id
      join users u on u.id=sp.user_id join work_orders w on w.id=a.work_order_id and w.tenant_id=a.tenant_id
      join tickets t on t.id=w.ticket_id and t.tenant_id=w.tenant_id
      where t.building_id=:building and a.created_at>=:start and a.created_at<:end
    ), scores as (select r.staff_id,avg(r.score) average_rating,count(*) rating_count
      from ticket_reviews r join tickets t on t.id=r.ticket_id and t.tenant_id=r.tenant_id
      where t.building_id=:building and r.submitted_at>=:start and r.submitted_at<:end group by r.staff_id)
    select j.staff_id,j.name,count(*) assigned_count,count(*) filter(where j.status='completed') completed_count,
      count(*) filter(where j.status='completed' and j.resolution_due_at is not null) timed_completion_count,
      count(*) filter(where j.status='completed' and j.completed_at<=j.resolution_due_at) on_time_count,
      avg(extract(epoch from j.completed_at-j.started_at)) filter(where j.status='completed' and j.started_at is not null) average_processing_seconds,
      count(*) filter(where exists(select 1 from vh_qc_redo_orders redo where redo.source_work_order_id=j.work_id)) redo_count,
      s.average_rating,coalesce(s.rating_count,0) rating_count
      from jobs j left join scores s on s.staff_id=j.staff_id group by j.staff_id,j.name,s.average_rating,s.rating_count order by j.name"""),
        {"building": building_id, "start": from_date, "end": to_date},
    )
    items = []
    for row in rows.mappings():
        value = dict(row)
        value["on_time_rate"] = (
            value["on_time_count"] / value["timed_completion_count"]
            if value["timed_completion_count"]
            else None
        )
        items.append(value)
    return agent_result(
        "get_employee_performance_summary",
        {
            "items": items,
            "periodBasis": "assignment creation; feedback uses submission date",
            "fromDate": from_date,
            "toDate": to_date,
        },
        {"building_id": building_id, "from_date": from_date, "to_date": to_date},
    )


@router.get("/reports/employee-feedback", response_model=AgentBusinessResponse)
async def feedback(
    scope: Scope,
    building_id: UUID = Query(..., alias="buildingId"),
    staff_id: UUID = Query(..., alias="staffId"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    await _management_building(scope, building_id)
    rows = await scope[0].execute(
        text(
            "select r.id,r.score,r.comment,r.submitted_at,r.ticket_id,r.assignment_id from ticket_reviews r join tickets t on t.id=r.ticket_id and t.tenant_id=r.tenant_id where t.building_id=:building and r.staff_id=:staff order by r.submitted_at desc,r.id limit :limit offset :offset"
        ),
        {"building": building_id, "staff": staff_id, "limit": limit, "offset": offset},
    )
    items = [dict(r) for r in rows.mappings()]
    return agent_result(
        "get_employee_feedback_details",
        {
            "items": items,
            "nextOffset": offset + len(items) if len(items) == limit else None,
        },
        {
            "building_id": building_id,
            "staff_id": staff_id,
            "limit": limit,
            "offset": offset,
        },
    )


@router.get("/reports/repair-revenue", response_model=AgentBusinessResponse)
async def repair_revenue(
    scope: Scope,
    building_id: UUID = Query(..., alias="buildingId"),
    category_id: UUID = Query(..., alias="categoryId"),
    from_date: date = Query(..., alias="fromDate"),
    to_date: date = Query(..., alias="toDate"),
):
    await report_scope(scope, building_id, from_date, to_date)
    rows = await scope[0].execute(
        text("""with amounts as (
      select i.id,i.work_order_id,i.currency,i.grand_total,sum(l.total_amount) billed
      from invoices i join invoice_lines l on l.invoice_id=i.id and l.tenant_id=i.tenant_id
      join tickets t on t.id=i.ticket_id and t.tenant_id=i.tenant_id
      where t.building_id=:building and l.category_id=:category and i.status='issued' and i.issued_at>=:start and i.issued_at<:end
      group by i.id,i.work_order_id,i.currency,i.grand_total
    ), collected as (select pa.invoice_id,sum(pa.amount) paid from payment_allocations pa join payments p on p.id=pa.payment_id and p.tenant_id=pa.tenant_id where p.reconciliation_status='confirmed' and p.settled_at<:end group by pa.invoice_id)
    select a.currency,sum(a.billed) billed_amount,sum(coalesce(c.paid,0)*a.billed/nullif(a.grand_total,0)) collected_amount,
      sum(greatest(a.billed-coalesce(c.paid,0)*a.billed/nullif(a.grand_total,0),0)) outstanding_amount,
      count(distinct a.work_order_id) billed_work_count,count(*) invoice_count from amounts a left join collected c on c.invoice_id=a.id group by a.currency"""),
        {
            "building": building_id,
            "category": category_id,
            "start": from_date,
            "end": to_date,
        },
    )
    return agent_result(
        "get_repair_revenue_summary",
        {
            "items": [dict(r) for r in rows.mappings()],
            "collectionBasis": "confirmed allocations through toDate; proportional allocation by category in mixed invoices",
            "laborMaterialsSplit": None,
            "splitReason": "invoice_lines has no labor/material discriminator",
        },
        {
            "building_id": building_id,
            "category_id": category_id,
            "from_date": from_date,
            "to_date": to_date,
        },
    )


@router.get("/reports/incident-frequency-summary", response_model=AgentBusinessResponse)
async def incident_summary(
    scope: Scope,
    building_id: UUID = Query(..., alias="buildingId"),
    from_date: date = Query(..., alias="fromDate"),
    to_date: date = Query(..., alias="toDate"),
    interval: Literal["day", "week", "month"] = "month",
    category_id: UUID | None = Query(None, alias="categoryId"),
):
    await report_scope(scope, building_id, from_date, to_date)
    rows = await scope[0].execute(
        text(f"""select date_trunc('{interval}',t.created_at)::date as period,
      t.category_id,c.name as category_name,t.incident_type_id,coalesce(it.name,'Không phân loại') as incident_type,count(*) as incident_count
      from tickets t left join service_categories c on c.id=t.category_id and c.tenant_id=t.tenant_id
      left join incident_types it on it.id=t.incident_type_id and it.tenant_id=t.tenant_id
      where t.building_id=:building and t.request_kind='incident' and t.created_at>=:start and t.created_at<:end
        and (cast(:category as uuid) is null or t.category_id=:category)
      group by 1,2,3,4,5 order by 1,3,5"""),
        {
            "building": building_id,
            "start": from_date,
            "end": to_date,
            "category": category_id,
        },
    )
    items = [dict(r) for r in rows.mappings()]
    total = sum(row["incident_count"] for row in items)
    for row in items:
        row["share"] = row["incident_count"] / total if total else 0
    return agent_result(
        "get_incident_frequency_summary",
        {
            "buildingId": building_id,
            "interval": interval,
            "totalTickets": total,
            "items": items,
            "shareBasis": "share of selected building/category and whole date range",
        },
        {
            "building_id": building_id,
            "from_date": from_date,
            "to_date": to_date,
            "interval": interval,
            "category_id": category_id,
        },
    )


@router.get("/reports/supporting-records", response_model=AgentBusinessResponse)
async def supporting(
    scope: Scope,
    building_id: UUID = Query(..., alias="buildingId"),
    from_date: date = Query(..., alias="fromDate"),
    to_date: date = Query(..., alias="toDate"),
    kind: Literal["tickets", "work_orders", "invoices"] = "tickets",
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    await report_scope(scope, building_id, from_date, to_date)
    queries = {
        "tickets": "select t.id,t.code,t.title,t.status,t.category_id,t.created_at from tickets t where t.building_id=:building and t.created_at>=:start and t.created_at<:end order by t.created_at desc,t.id",
        "work_orders": "select w.id,w.ticket_id,w.category_id,w.description,w.status,w.created_at from work_orders w join tickets t on t.id=w.ticket_id and t.tenant_id=w.tenant_id where t.building_id=:building and w.created_at>=:start and w.created_at<:end order by w.created_at desc,w.id",
        "invoices": "select i.id,i.invoice_no,i.ticket_id,i.work_order_id,i.status,i.grand_total,i.currency,i.issued_at from invoices i join tickets t on t.id=i.ticket_id and t.tenant_id=i.tenant_id where t.building_id=:building and i.status='issued' and i.issued_at>=:start and i.issued_at<:end order by i.issued_at desc,i.id",
    }
    rows = await scope[0].execute(
        text(queries[kind] + " limit :limit offset :offset"),
        {
            "building": building_id,
            "start": from_date,
            "end": to_date,
            "limit": limit,
            "offset": offset,
        },
    )
    items = [dict(r) for r in rows.mappings()]
    return agent_result(
        "get_report_supporting_records",
        {
            "items": items,
            "nextOffset": offset + len(items) if len(items) == limit else None,
        },
        {
            "building_id": building_id,
            "from_date": from_date,
            "to_date": to_date,
            "kind": kind,
            "limit": limit,
            "offset": offset,
        },
    )


class ExportCreate(BaseModel):
    kind: Literal["incident_frequency", "issued_revenue"]
    building_id: UUID
    category_id: UUID | None = None
    from_date: date
    to_date: date
    format: Literal["docx"] = "docx"
    idempotency_key: str = Field(min_length=1, max_length=160)


@router.post("/reports/exports", status_code=201, response_model=AgentBusinessResponse)
async def export(body: ExportCreate, scope: Scope):
    await report_scope(scope, body.building_id, body.from_date, body.to_date)
    fp = digest(body.model_dump(exclude={"idempotency_key"}))
    await scope[0].execute(
        text("select pg_advisory_xact_lock(hashtextextended(:key,0))"),
        {"key": f"report:{scope[1]}:{body.idempotency_key}"},
    )
    old = (
        (
            await scope[0].execute(
                text(
                    "select id,request_hash from vh_report_exports where created_by=:actor and idempotency_key=:key"
                ),
                {"actor": scope[1], "key": body.idempotency_key},
            )
        )
        .mappings()
        .first()
    )
    if old:
        if old["request_hash"] != fp:
            raise HTTPException(409, "Export key already used")
        return agent_result(
            "create_report_export", await export_status(old["id"], scope), {}
        )
    if body.kind == "issued_revenue":
        if body.category_id is None:
            raise HTTPException(422, "category_id required for revenue")
        data = await _issued_revenue(
            scope, body.building_id, body.category_id, body.from_date, body.to_date
        )
    else:
        data = await _frequency(scope, body.building_id, body.from_date, body.to_date)
    content = _docx(
        [f"Bao cao {body.kind}", f"{body.from_date} - {body.to_date}"]
        + [json.dumps(row, ensure_ascii=False, default=str) for row in data]
    )
    result = await scope[0].execute(
        text(
            f"insert into vh_report_exports(tenant_id,building_id,created_by,kind,filters,status,content,idempotency_key,request_hash) values({TENANT},:building,:actor,:kind,cast(:filters as jsonb),'ready',:content,:key,:hash) returning id"
        ),
        {
            "building": body.building_id,
            "actor": scope[1],
            "kind": body.kind,
            "filters": json.dumps(
                body.model_dump(mode="json", exclude={"idempotency_key"})
            ),
            "content": content,
            "key": body.idempotency_key,
            "hash": fp,
        },
    )
    return agent_result(
        "create_report_export", await export_status(result.scalar_one(), scope), {}
    )


@router.get("/reports/exports/{export_id}", response_model=AgentBusinessResponse)
async def export_status(export_id: UUID, scope: Scope):
    row = (
        (
            await scope[0].execute(
                text(
                    "select id,building_id,kind,status,error_code,created_at from vh_report_exports where id=:id and created_by=:actor"
                ),
                {"id": export_id, "actor": scope[1]},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(404, "Export not found")
    await _management_building(scope, row["building_id"])
    return agent_result(
        "get_report_export_status",
        {
            **dict(row),
            "reportId": row["id"],
            "jobId": row["id"],
            "execution": "synchronous",
            "downloadUrl": f"/reports/exports/{export_id}/content"
            if row["status"] == "ready"
            else None,
        },
        {},
    )


@router.get("/reports/exports/{export_id}/content")
async def download(export_id: UUID, scope: Scope):
    status = await export_status(export_id, scope)
    if status["status"] != "ready":
        raise HTTPException(409, "Export not ready")
    data = (
        await scope[0].execute(
            text("select content from vh_report_exports where id=:id"),
            {"id": export_id},
        )
    ).scalar_one()
    return Response(
        bytes(data),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="report-{export_id}.docx"'
        },
    )
