"""Technical observations and human permission requests, without device control."""


import json
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection
from .v3_agent_results import AgentBusinessResponse, agent_result, agent_blocked
from .v3_auth import scoped_connection
from .v3_mutations import visible_ticket, management_access, record_event
from .v3_water import _responsible_management
from .v3_security import building_access, digest

router = APIRouter(tags=["V3 technical assets and permissions"])
Scope = Annotated[tuple[AsyncConnection, str, bool], Depends(scoped_connection)]
TENANT = "nullif(current_setting('app.tenant_id',true),'')::uuid"


async def work_access(scope: Scope, work_id: UUID, write=False):
    db = scope[0]
    row = (
        (
            await db.execute(
                text(
                    "select id,ticket_id,status,version from work_orders where id=:id"
                ),
                {"id": work_id},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(404, "Work order not found")
    ticket = await visible_ticket(scope, row["ticket_id"], lock=write)
    if write:
        row = (
            (
                await db.execute(
                    text(
                        "select id,ticket_id,status,version from work_orders where id=:id for update"
                    ),
                    {"id": work_id},
                )
            )
            .mappings()
            .one()
        )
        if not await management_access(scope, ticket):
            assignment = await db.execute(
                text(
                    "select 1 from work_assignments a join staff_profiles sp on sp.id=a.staff_id and sp.tenant_id=a.tenant_id where a.work_order_id=:id and sp.user_id=:actor and a.status='accepted'"
                ),
                {"id": work_id, "actor": scope[1]},
            )
            if assignment.first() is None:
                raise HTTPException(
                    403, "Assigned executor or responsible management required"
                )
    return dict(row), ticket


async def asset_access(scope: Scope, asset_id: UUID):
    row = (
        (
            await scope[0].execute(
                text("select * from vh_assets where id=:id"), {"id": asset_id}
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(404, "Asset not found")
    await building_access(scope, row["building_id"])
    return dict(row)


@router.get("/assets", response_model=AgentBusinessResponse)
async def assets(scope: Scope, building_id: UUID = Query(..., alias="buildingId")):
    await building_access(scope, building_id)
    rows = await scope[0].execute(
        text("select * from vh_assets where building_id=:id order by code"),
        {"id": building_id},
    )
    return agent_result(
        "asset.read",
        {"items": [dict(r) for r in rows.mappings()]},
        {"building_id": building_id},
    )


@router.get("/assets/{asset_id}", response_model=AgentBusinessResponse)
async def asset(asset_id: UUID, scope: Scope):
    return agent_result(
        "asset.read", await asset_access(scope, asset_id), {"asset_id": asset_id}
    )


@router.get("/assets/{asset_id}/sensor-readings", response_model=AgentBusinessResponse)
async def sensors(asset_id: UUID, scope: Scope, limit: int = Query(50, ge=1, le=100)):
    await asset_access(scope, asset_id)
    rows = await scope[0].execute(
        text(
            "select * from vh_sensor_readings where asset_id=:id order by measured_at desc limit :limit"
        ),
        {"id": asset_id, "limit": limit},
    )
    return agent_result(
        "sensor.read",
        {
            "items": [dict(r) for r in rows.mappings()],
            "source": "database; no live BMS connection",
        },
        {"asset_id": asset_id, "limit": limit},
    )


class SensorCreate(BaseModel):
    parameter: str = Field(min_length=1, max_length=120)
    value: Decimal
    unit: str = Field(min_length=1, max_length=40)
    measured_at: datetime
    source: str = Field(min_length=1, max_length=120)

    @field_validator("measured_at")
    @classmethod
    def timezone_required(cls, value):
        if value.tzinfo is None:
            raise ValueError("measured_at requires a timezone")
        return value


@router.post(
    "/assets/{asset_id}/sensor-readings",
    status_code=201,
    response_model=AgentBusinessResponse,
)
async def record_sensor(asset_id: UUID, body: SensorCreate, scope: Scope):
    a = await asset_access(scope, asset_id)
    from .v3_reports import _management_building

    await _management_building(scope, a["building_id"])
    row = await scope[0].execute(
        text(
            f"insert into vh_sensor_readings(tenant_id,asset_id,parameter,value,unit,measured_at,source,recorded_by) values({TENANT},:asset,:parameter,:value,:unit,:measured_at,:source,:actor) returning *"
        ),
        {**body.model_dump(), "asset": asset_id, "actor": scope[1]},
    )
    return agent_result(
        "sensor.record", dict(row.mappings().one()), {"asset_id": asset_id}
    )


@router.get(
    "/assets/{asset_id}/maintenance-history", response_model=AgentBusinessResponse
)
async def history(
    asset_id: UUID,
    scope: Scope,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    await asset_access(scope, asset_id)
    rows = await scope[0].execute(
        text(
            "select * from vh_maintenance_records where asset_id=:id order by created_at desc limit :limit offset :offset"
        ),
        {"id": asset_id, "limit": limit, "offset": offset},
    )
    return agent_result(
        "maintenance_history.read",
        {"items": [dict(r) for r in rows.mappings()]},
        {"asset_id": asset_id, "limit": limit, "offset": offset},
    )


class Measurement(SensorCreate):
    source: str = "executor"
    note: str = Field(min_length=1, max_length=2000)


@router.post(
    "/work-orders/{work_order_id}/measurements",
    status_code=201,
    response_model=AgentBusinessResponse,
)
async def measurement(work_order_id: UUID, body: Measurement, scope: Scope):
    order, ticket = await work_access(scope, work_order_id, True)
    if order["status"] in {"completed", "cancelled", "rejected"}:
        raise HTTPException(409, "Work order is final")
    row = await scope[0].execute(
        text(
            f"insert into vh_technical_measurements(tenant_id,work_order_id,parameter,value,unit,note,recorded_by,measured_at) values({TENANT},:work,:parameter,:value,:unit,:note,:actor,:measured_at) returning *"
        ),
        {**body.model_dump(), "work": work_order_id, "actor": scope[1]},
    )
    result = dict(row.mappings().one())
    await record_event(
        scope,
        ticket,
        "technical.measurement_recorded",
        json.dumps({"measurementId": str(result["id"])}),
    )
    return agent_result(
        "technical.record_measurement", result, {"work_order_id": work_order_id}
    )


@router.get(
    "/work-orders/{work_order_id}/measurements", response_model=AgentBusinessResponse
)
async def measurements(work_order_id: UUID, scope: Scope):
    await work_access(scope, work_order_id)
    rows = await scope[0].execute(
        text(
            "select * from vh_technical_measurements where work_order_id=:id order by measured_at"
        ),
        {"id": work_order_id},
    )
    return agent_result(
        "technical.read_measurements",
        {"items": [dict(r) for r in rows.mappings()]},
        {"work_order_id": work_order_id},
    )


@router.get("/technical/active-outages", response_model=AgentBusinessResponse)
async def outages(scope: Scope, building_id: UUID = Query(..., alias="buildingId")):
    await building_access(scope, building_id)
    rows = await scope[0].execute(
        text(
            "select si.id,si.status,si.planned_start,si.planned_end from service_interruptions si join work_approvals a on a.id=si.approval_id and a.tenant_id=si.tenant_id join work_orders w on w.id=a.work_order_id and w.tenant_id=a.tenant_id join tickets t on t.id=w.ticket_id and t.tenant_id=w.tenant_id where t.building_id=:id and si.status not in ('restored','cancelled')"
        ),
        {"id": building_id},
    )
    return agent_result(
        "technical.get_active_outage",
        {"items": [dict(r) for r in rows.mappings()]},
        {"building_id": building_id},
    )


class PermissionCreate(BaseModel):
    kind: Literal[
        "utility_isolation", "area_restriction", "apartment_entry", "vendor_dispatch"
    ]
    reason: str = Field(min_length=1, max_length=2000)
    details: dict[str, str | int | bool] = Field(default_factory=dict, max_length=20)
    work_order_version: int = Field(ge=0)
    idempotency_key: str = Field(min_length=1, max_length=160)


@router.post(
    "/work-orders/{work_order_id}/permission-requests",
    status_code=201,
    response_model=AgentBusinessResponse,
)
async def permission(work_order_id: UUID, body: PermissionCreate, scope: Scope):
    order, ticket = await work_access(scope, work_order_id, True)
    fp = digest(body.model_dump(exclude={"idempotency_key", "work_order_version"}))
    old = (
        (
            await scope[0].execute(
                text(
                    "select * from vh_operational_requests where work_order_id=:id and idempotency_key=:key"
                ),
                {"id": work_order_id, "key": body.idempotency_key},
            )
        )
        .mappings()
        .first()
    )
    if old:
        if old["requested_by"] != scope[1] or old["request_hash"] != fp:
            raise HTTPException(409, "Request key already used")
        return agent_result(
            "permission.request", dict(old), {"work_order_id": work_order_id}
        )
    if order["version"] != body.work_order_version or order["status"] in {
        "completed",
        "cancelled",
        "rejected",
    }:
        raise HTTPException(409, "Work order changed")
    # Water uses the existing interruption/notification workflow, not a second state store.
    if (
        body.kind == "utility_isolation"
        and body.details.get("utility") != "electricity"
    ):
        raise HTTPException(
            422,
            "Use existing water shutdown endpoints for water; specify electricity here",
        )
    row = await scope[0].execute(
        text(
            f"insert into vh_operational_requests(tenant_id,work_order_id,kind,details,reason,requested_by,status,idempotency_key,request_hash) values({TENANT},:work,:kind,cast(:details as jsonb),:reason,:actor,'pending',:key,:hash) returning *"
        ),
        {
            "work": work_order_id,
            "kind": body.kind,
            "details": json.dumps(body.details),
            "reason": body.reason,
            "actor": scope[1],
            "key": body.idempotency_key,
            "hash": fp,
        },
    )
    result = dict(row.mappings().one())
    await record_event(
        scope,
        ticket,
        "permission.requested",
        json.dumps({"requestId": str(result["id"]), "kind": body.kind}),
    )
    return agent_result("permission.request", result, {"work_order_id": work_order_id})


@router.get(
    "/work-orders/{work_order_id}/permission-requests",
    response_model=AgentBusinessResponse,
)
async def permissions(work_order_id: UUID, scope: Scope):
    await work_access(scope, work_order_id)
    rows = await scope[0].execute(
        text(
            "select * from vh_operational_requests where work_order_id=:id order by created_at desc"
        ),
        {"id": work_order_id},
    )
    return agent_result(
        "permission.read",
        {"items": [dict(r) for r in rows.mappings()]},
        {"work_order_id": work_order_id},
    )


class PermissionDecision(BaseModel):
    status: Literal["approved", "rejected", "completed", "cancelled"]
    version: int = Field(ge=0)
    note: str = Field(min_length=1, max_length=2000)


@router.post(
    "/permission-requests/{request_id}/decision", response_model=AgentBusinessResponse
)
async def permission_decision(request_id: UUID, body: PermissionDecision, scope: Scope):
    ref = (
        (
            await scope[0].execute(
                text("select work_order_id from vh_operational_requests where id=:id"),
                {"id": request_id},
            )
        )
        .mappings()
        .first()
    )
    if ref is None:
        raise HTTPException(404, "Request not found")
    order, ticket = await work_access(scope, ref["work_order_id"], True)
    await _responsible_management(scope, ticket)
    row = (
        (
            await scope[0].execute(
                text("select * from vh_operational_requests where id=:id for update"),
                {"id": request_id},
            )
        )
        .mappings()
        .one()
    )
    transitions = {
        "pending": {"approved", "rejected", "cancelled"},
        "approved": {"completed", "cancelled"},
    }
    if row["version"] != body.version or body.status not in transitions.get(
        row["status"], set()
    ):
        raise HTTPException(409, "Request state changed")
    if body.status == "approved" and order["status"] in {
        "completed",
        "cancelled",
        "rejected",
    }:
        raise HTTPException(409, "Work order is final")
    result = await scope[0].execute(
        text(
            "update vh_operational_requests set status=:status,version=version+1,decided_by=:actor,decision_note=:note,decided_at=now(),updated_at=now() where id=:id returning *"
        ),
        {"status": body.status, "actor": scope[1], "note": body.note, "id": request_id},
    )
    await record_event(
        scope,
        ticket,
        "permission.decided",
        json.dumps({"requestId": str(request_id), "status": body.status}),
    )
    return agent_result(
        "permission.decision", dict(result.mappings().one()), {"request_id": request_id}
    )


@router.get(
    "/work-orders/{work_order_id}/resolution-check",
    response_model=AgentBusinessResponse,
)
async def resolution(work_order_id: UUID, scope: Scope):
    await work_access(scope, work_order_id)
    db = scope[0]
    checks = {
        "completionEvidence": "select exists(select 1 from evidence_items where work_order_id=:id and status='active' and purpose in ('after','verification'))",
        "waterRestored": "select not exists(select 1 from service_interruptions s join work_approvals a on a.id=s.approval_id and a.tenant_id=s.tenant_id where a.work_order_id=:id and s.status not in ('restored','cancelled'))",
        "permissionsFinished": "select not exists(select 1 from vh_operational_requests where work_order_id=:id and status in ('pending','approved'))",
        "qcPassed": "select coalesce((select outcome='pass' from vh_qc_results where work_order_id=:id order by checked_at desc limit 1),true)",
    }
    result = {
        key: (await db.execute(text(sql), {"id": work_order_id})).scalar_one()
        for key, sql in checks.items()
    }
    return agent_result(
        "technical.verify_resolution",
        {
            "workOrderId": work_order_id,
            "ready": all(result.values()),
            "checks": result,
        },
        {"work_order_id": work_order_id},
    )


class MaintenanceCreate(BaseModel):
    work_order_id: UUID
    note: str = Field(min_length=1, max_length=5000)


class ExecutorResult(BaseModel):
    version: int = Field(ge=0)
    diagnosis: str = Field(min_length=1, max_length=5000)
    repair_notes: str = Field(min_length=1, max_length=5000)


@router.post(
    "/work-orders/{work_order_id}/executor-results",
    response_model=AgentBusinessResponse,
)
async def executor_result(work_order_id: UUID, body: ExecutorResult, scope: Scope):
    order, _ = await work_access(scope, work_order_id, True)
    if order["version"] != body.version or order["status"] != "in_progress":
        raise HTTPException(409, "Current in-progress work required")
    before = await scope[0].execute(
        text(
            "select 1 from evidence_items where work_order_id=:id and status='active' and purpose='before' limit 1"
        ),
        {"id": work_order_id},
    )
    if before.first() is None:
        raise HTTPException(
            409,
            agent_blocked(
                "Attach before evidence first",
                ["beforeEvidence"],
                {"work_order_id": work_order_id, "version": order["version"]},
            ),
        )
    check = await resolution(work_order_id, scope)
    if not check["ready"]:
        raise HTTPException(
            409,
            {
                "checks": check["checks"],
                **agent_blocked(
                    "Work completion conditions are not satisfied",
                    [name for name, passed in check["checks"].items() if not passed],
                    {"work_order_id": work_order_id, "version": order["version"]},
                ),
            },
        )
    await scope[0].execute(
        text(
            "update work_orders set diagnosis=:diagnosis,repair_notes=:notes where id=:id"
        ),
        {"diagnosis": body.diagnosis, "notes": body.repair_notes, "id": work_order_id},
    )
    from .v3_mutations import change_work_order_status, WorkOrderTransition

    return agent_result(
        "technical.submit_executor_result",
        await change_work_order_status(
            work_order_id,
            WorkOrderTransition(
                version=body.version, status="completed", note=body.repair_notes
            ),
            scope,
        ),
        {"work_order_id": work_order_id},
    )


@router.post(
    "/assets/{asset_id}/maintenance-history",
    status_code=201,
    response_model=AgentBusinessResponse,
)
async def append_history(asset_id: UUID, body: MaintenanceCreate, scope: Scope):
    a = await asset_access(scope, asset_id)
    order, ticket = await work_access(scope, body.work_order_id, True)
    await _responsible_management(scope, ticket)
    if ticket["building_id"] != a["building_id"]:
        raise HTTPException(422, "Asset and work order buildings differ")
    if (
        order["status"] != "completed"
        or not (await resolution(body.work_order_id, scope))["ready"]
    ):
        raise HTTPException(409, "Verified completed work required")
    old = (
        (
            await scope[0].execute(
                text(
                    "select * from vh_maintenance_records where asset_id=:asset and work_order_id=:work"
                ),
                {"asset": asset_id, "work": body.work_order_id},
            )
        )
        .mappings()
        .first()
    )
    if old:
        if old["note"] != body.note:
            raise HTTPException(409, "Confirmed maintenance record is immutable")
        return agent_result(
            "maintenance_history.append", dict(old), {"asset_id": asset_id}
        )
    row = await scope[0].execute(
        text(
            f"insert into vh_maintenance_records(tenant_id,asset_id,work_order_id,note,confirmed_by) values({TENANT},:asset,:work,:note,:actor) returning *"
        ),
        {
            "asset": asset_id,
            "work": body.work_order_id,
            "note": body.note,
            "actor": scope[1],
        },
    )
    await record_event(
        scope, ticket, "maintenance.confirmed", json.dumps({"assetId": str(asset_id)})
    )
    return agent_result(
        "maintenance_history.append", dict(row.mappings().one()), {"asset_id": asset_id}
    )
