"""WorkOrder reads and lifecycle commands guarded by trusted authority."""

from datetime import datetime, timezone
from typing import Annotated, Any, Callable, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..concurrency import require_expected_version
from ..commands import CommandReceiptRepository
from ..commands.hashing import command_payload_hash
from ..db.command_receipt import CommandReceiptStatus
from ..db.checklist import Checklist, ChecklistVersion
from ..db.dependencies import get_db_session
from ..db.task import TaskDomainType
from ..db.work_order import WorkOrderStatus
from ..evidence.repository import EvidenceRepository
from ..evidence.service import work_order_evidence_read
from ..incidents.repository import IncidentRepository
from ..request_context import (
    DomainScope,
    RequestContext,
    get_domain_scope,
    get_request_context,
    scope_contains_subject,
)
from ..db.work_order_assignment import WorkOrderAssignment
from ..events import BusinessEventRepository
from ..tasks.repository import TaskRepository
from .a5_execution import (
    InvalidA5Execution,
    a5_execution_read,
    a5_task_projection,
    complete_a5_action,
    pin_a5_execution_plan,
    validate_pinned_a5_execution_plan,
    task_for_execution,
)
from .a5_execution_schemas import A5ExecutionRead, CompleteA5ActionInput
from .authority import (
    FieldOperationsAuthority,
    FieldOperationsRole,
    get_field_operations_authority,
)
from .checklist_execution import (
    InvalidChecklistContract,
    checklist_execution_read,
    complete_checklist_item,
    pin_checklist_version,
)
from .checklist_repository import ChecklistRepository
from .checklist_schemas import (
    ChecklistExecutionRead,
    CompleteChecklistItemInput,
    PinChecklistInput,
)
from .execution_details import (
    InvalidExecutionDetails,
    append_execution_detail,
    execution_details_read,
    make_execution_note_record,
    make_equipment_usage_record,
    make_material_usage_record,
    make_measurement_record,
)
from .execution_details_schemas import (
    AddEquipmentUsageInput,
    AddExecutionNoteInput,
    AddMaterialUsageInput,
    AddMeasurementInput,
    ExecutionDetailsRead,
)
from .field_operations_state import (
    InvalidFieldOperationsState,
    read_field_operations_state,
    reset_contractor_response,
    require_active_execution,
    write_field_operations_state,
)
from .lifecycle import (
    InvalidWorkOrderTransition,
    assign,
    complete as complete_lifecycle,
    start,
)
from .repository import WorkOrderRepository
from .schemas import (
    AssignWorkOrderInput,
    WorkOrderAssignmentRead,
    WorkOrderRead,
    WorkOrderPage,
    WorkOrderVersionCommand,
    SupervisorWorkOrderPage,
    supervisor_work_order_read,
)


router = APIRouter(tags=["work-orders"])


def _require_coordinator(authority: FieldOperationsAuthority) -> None:
    if authority.actor_type != "user" or not authority.roles.intersection(
        {FieldOperationsRole.SUPERVISOR, FieldOperationsRole.BQL_COORDINATOR}
    ):
        raise HTTPException(status_code=403, detail="Supervisor or BQL coordinator role required")


def _tenant_id(context: RequestContext) -> UUID:
    try:
        return UUID(context.tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Authenticated tenant identifier is invalid") from exc


def _require_scope(scope: DomainScope, incident_id: UUID) -> None:
    if not scope_contains_subject(
        scope,
        namespace="vinhomes",
        subject_type="incident",
        subject_id=str(incident_id),
    ):
        raise HTTPException(status_code=403, detail="Incident is outside the effective domain scope")


async def _replay_lifecycle_command(
    *, session: AsyncSession, tenant_id: UUID, context: RequestContext,
    command_type: str, idempotency_key: str | None, payload: BaseModel, work_order_id: UUID,
) -> WorkOrderRead | None:
    if idempotency_key is None:
        return None
    receipt = await CommandReceiptRepository(session).get(
        tenant_id=tenant_id, actor_type=context.actor.kind, actor_id=context.actor.id,
        command_type=command_type, idempotency_key=idempotency_key, for_update=True,
    )
    if receipt is None:
        return None
    request_hash = command_payload_hash({
        "workOrderId": str(work_order_id),
        "payload": payload.model_dump(mode="json", by_alias=True),
    })
    if receipt.payload_hash != request_hash:
        raise HTTPException(status_code=409, detail="IDEMPOTENCY_KEY_REUSED")
    if receipt.status is not CommandReceiptStatus.COMPLETED or receipt.response_json is None:
        raise HTTPException(status_code=409, detail="Command with this Idempotency-Key is still in progress")
    return WorkOrderRead.model_validate(receipt.response_json)


async def _store_lifecycle_command(
    *, session: AsyncSession, tenant_id: UUID, context: RequestContext,
    command_type: str, idempotency_key: str | None, payload: BaseModel,
    work_order_id: UUID, response: WorkOrderRead,
) -> None:
    if idempotency_key is None:
        return
    request_hash = command_payload_hash({
        "workOrderId": str(work_order_id),
        "payload": payload.model_dump(mode="json", by_alias=True),
    })
    receipts = CommandReceiptRepository(session)
    receipt = receipts.add(
        tenant_id=tenant_id, actor_type=context.actor.kind, actor_id=context.actor.id,
        command_type=command_type, idempotency_key=idempotency_key, payload_hash=request_hash,
        subject_type="WorkOrder", subject_id=str(work_order_id),
    )
    await receipts.complete(
        receipt, subject_id=str(work_order_id),
        response_json=response.model_dump(mode="json", by_alias=True),
    )


@router.get("/incidents/{incident_id}/work-orders", response_model=list[WorkOrderRead])
async def list_incident_work_orders(
    incident_id: UUID,
    context: RequestContext = Depends(get_request_context),
    scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority),
    session: AsyncSession = Depends(get_db_session),
) -> list[WorkOrderRead]:
    tenant_id = _tenant_id(context)
    if await IncidentRepository(session).get_by_id(tenant_id=tenant_id, incident_id=incident_id) is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    _require_scope(scope, incident_id)
    orders = await WorkOrderRepository(session).list_by_incident(
        tenant_id=tenant_id, incident_id=incident_id
    )
    return [WorkOrderRead.model_validate(order) for order in orders if authority.can_read(order, scope)]


@router.get("/tasks/{task_id}/work-orders", response_model=list[WorkOrderRead])
async def list_task_work_orders(
    task_id: UUID,
    context: RequestContext = Depends(get_request_context),
    scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority),
    session: AsyncSession = Depends(get_db_session),
) -> list[WorkOrderRead]:
    tenant_id = _tenant_id(context)
    task = await TaskRepository(session).get_by_id(tenant_id=tenant_id, task_id=task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    _require_scope(scope, task.incident_id)
    orders = await WorkOrderRepository(session).list_attempts(tenant_id=tenant_id, task_id=task_id)
    return [WorkOrderRead.model_validate(order) for order in orders if authority.can_read(order, scope)]


def _scoped_incident_ids(scope: DomainScope) -> list[UUID]:
    incident_ids: list[UUID] = []
    for subject in scope.subjects:
        if subject.namespace != "vinhomes" or subject.subject_type != "incident":
            continue
        try:
            incident_ids.append(UUID(subject.subject_id))
        except ValueError as exc:
            raise HTTPException(
                status_code=403,
                detail="Effective Incident scope contains an invalid subject identifier",
            ) from exc
    return incident_ids


@router.get("/my/work-orders", response_model=WorkOrderPage)
async def list_my_work_orders(
    context: RequestContext = Depends(get_request_context),
    scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority),
    session: AsyncSession = Depends(get_db_session),
    status_filter: WorkOrderStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> WorkOrderPage:
    """List the authenticated field executor's assigned attempts in scope."""
    worker_roles = {
        FieldOperationsRole.TECHNICIAN,
        FieldOperationsRole.A5_WORKER,
        FieldOperationsRole.SECURITY_WORKER,
        FieldOperationsRole.CONTRACTOR_WORKER,
    }
    if authority.actor_type != "user" or not authority.roles.intersection(worker_roles):
        raise HTTPException(status_code=403, detail="Field executor role required")
    try:
        executor_id = UUID(context.actor.id)
    except ValueError as exc:
        raise HTTPException(
            status_code=401,
            detail="Authenticated executor identifier is invalid",
        ) from exc
    executor_types = list(
        dict.fromkeys(
            membership.executor_type
            for membership in authority.executor_memberships
            if membership.executor_id == executor_id
        )
    )
    if not executor_types:
        return WorkOrderPage(items=[], total=0, limit=limit, offset=offset)
    orders, total = await WorkOrderRepository(session).list_for_executor(
        tenant_id=_tenant_id(context),
        executor_id=executor_id,
        executor_types=executor_types,
        scoped_incident_ids=_scoped_incident_ids(scope),
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return WorkOrderPage(
        items=[
            WorkOrderRead.model_validate(order)
            for order in orders
            if authority.can_read(order, scope)
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/supervisor/work-orders", response_model=SupervisorWorkOrderPage)
async def list_supervisor_work_orders(
    context: RequestContext = Depends(get_request_context),
    scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority),
    session: AsyncSession = Depends(get_db_session),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    unassigned_only: bool = Query(default=False, alias="unassignedOnly"),
    blocked_only: bool = Query(default=False, alias="blockedOnly"),
    overdue_only: bool = Query(default=False, alias="overdueOnly"),
    team_id: UUID | None = Query(default=None, alias="teamId"),
    area_id: str | None = Query(default=None, alias="areaId", min_length=1, max_length=128),
) -> SupervisorWorkOrderPage:
    """Incident-scoped queue with optional trusted team and location narrowing."""
    _require_coordinator(authority)
    trusted_team_ids = {
        subject.subject_id
        for subject in scope.subjects
        if subject.namespace == "vinhomes" and subject.subject_type == "team"
    }
    trusted_area_ids = {
        subject.subject_id
        for subject in scope.subjects
        if subject.namespace == "vinhomes" and subject.subject_type == "area"
    }
    if team_id is not None and str(team_id) not in trusted_team_ids:
        raise HTTPException(status_code=403, detail="Team is outside the effective domain scope")
    if area_id is not None and area_id not in trusted_area_ids:
        raise HTTPException(status_code=403, detail="Area is outside the effective domain scope")
    tenant_id = _tenant_id(context)
    now = datetime.now(timezone.utc)
    rows, total = await WorkOrderRepository(session).list_for_supervisor(
        tenant_id=tenant_id,
        scoped_incident_ids=_scoped_incident_ids(scope),
        limit=limit,
        offset=offset,
        now=now,
        unassigned_only=unassigned_only,
        blocked_only=blocked_only,
        overdue_only=overdue_only,
        team_executor_id=team_id,
        area_location_id=area_id,
    )
    visible = [
        supervisor_work_order_read(order, task, incident, now=now)
        for order, task, incident in rows
        if authority.can_read(order, scope)
    ]
    return SupervisorWorkOrderPage(
        items=visible,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/work-orders/{work_order_id}", response_model=WorkOrderRead)
async def get_work_order(
    work_order_id: UUID,
    context: RequestContext = Depends(get_request_context),
    scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority),
    session: AsyncSession = Depends(get_db_session),
) -> WorkOrderRead:
    order = await WorkOrderRepository(session).get_by_id(
        tenant_id=_tenant_id(context), work_order_id=work_order_id
    )
    if order is None:
        raise HTTPException(status_code=404, detail="WorkOrder not found")
    if not authority.can_read(order, scope):
        raise HTTPException(status_code=404, detail="WorkOrder not found")
    return WorkOrderRead.model_validate(order)


@router.get(
    "/work-orders/{work_order_id}/checklist",
    response_model=ChecklistExecutionRead,
)
async def get_work_order_checklist(
    work_order_id: UUID,
    context: RequestContext = Depends(get_request_context),
    scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority),
    session: AsyncSession = Depends(get_db_session),
) -> ChecklistExecutionRead:
    tenant_id = _tenant_id(context)
    orders = WorkOrderRepository(session)
    order = await orders.get_by_id(tenant_id=tenant_id, work_order_id=work_order_id)
    if order is None or not authority.can_read(order, scope):
        raise HTTPException(status_code=404, detail="WorkOrder not found")
    task = await TaskRepository(session).get_by_id(tenant_id=tenant_id, task_id=order.task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    checklist: Checklist | None = None
    version: ChecklistVersion | None = None
    if order.checklist_version_id is not None:
        pair = await ChecklistRepository(session).get_version_for_tenant(
            tenant_id=tenant_id,
            checklist_version_id=order.checklist_version_id,
        )
        if pair is None:
            raise HTTPException(status_code=409, detail="Pinned checklist version is unavailable")
        checklist, version = pair
    try:
        execution_task = task_for_execution(order, task)
    except InvalidA5Execution as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return checklist_execution_read(
        order,
        task=execution_task,
        checklist=checklist,
        checklist_version=version,
    )


@router.post(
    "/work-orders/{work_order_id}/checklist",
    response_model=WorkOrderRead,
)
async def pin_work_order_checklist(
    work_order_id: UUID,
    payload: PinChecklistInput,
    context: RequestContext = Depends(get_request_context),
    scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority),
    session: AsyncSession = Depends(get_db_session),
) -> WorkOrderRead:
    _require_coordinator(authority)
    tenant_id = _tenant_id(context)
    async with session.begin():
        order = await WorkOrderRepository(session).get_by_id_for_update(
            tenant_id=tenant_id,
            work_order_id=work_order_id,
        )
        if order is None:
            raise HTTPException(status_code=404, detail="WorkOrder not found")
        _require_scope(scope, order.incident_id)
        task = await TaskRepository(session).get_by_id(
            tenant_id=tenant_id,
            task_id=order.task_id,
        )
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        pair = await ChecklistRepository(session).get_version_for_tenant(
            tenant_id=tenant_id,
            checklist_version_id=payload.checklist_version_id,
        )
        if pair is None:
            raise HTTPException(status_code=404, detail="Checklist version not found")
        checklist, version = pair
        try:
            pin_checklist_version(
                order,
                task=task,
                checklist=checklist,
                checklist_version=version,
                checklist_version_id=payload.checklist_version_id,
                expected_version=payload.expected_version,
                authority=authority,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except InvalidChecklistContract as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        await session.flush()
        await session.refresh(order)
        await BusinessEventRepository(session).append(
            tenant_id=tenant_id,
            incident_id=order.incident_id,
            subject_type="WorkOrder",
            subject_id=str(order.id),
            event_type="CHECKLIST_PINNED",
            actor_type=context.actor.kind,
            actor_id=context.actor.id,
            actor_version=None,
            data={"checklistVersionId": str(version.id), "workOrderVersion": order.version},
            correlation_id=context.correlation_id,
        )
        return WorkOrderRead.model_validate(order)


@router.post(
    "/work-orders/{work_order_id}/checklist/items/{item_id}/complete",
    response_model=ChecklistExecutionRead,
)
async def complete_work_order_checklist_item(
    work_order_id: UUID,
    item_id: Annotated[str, Path(min_length=1, max_length=128)],
    payload: CompleteChecklistItemInput,
    context: RequestContext = Depends(get_request_context),
    scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority),
    session: AsyncSession = Depends(get_db_session),
) -> ChecklistExecutionRead:
    tenant_id = _tenant_id(context)
    async with session.begin():
        order = await WorkOrderRepository(session).get_by_id_for_update(
            tenant_id=tenant_id,
            work_order_id=work_order_id,
        )
        if order is None:
            raise HTTPException(status_code=404, detail="WorkOrder not found")
        _require_scope(scope, order.incident_id)
        task = await TaskRepository(session).get_by_id(
            tenant_id=tenant_id,
            task_id=order.task_id,
        )
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        try:
            require_active_execution(order)
        except InvalidFieldOperationsState as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if order.checklist_version_id is None:
            raise HTTPException(status_code=409, detail="No checklist version is pinned")
        pair = await ChecklistRepository(session).get_version_for_tenant(
            tenant_id=tenant_id,
            checklist_version_id=order.checklist_version_id,
        )
        if pair is None:
            raise HTTPException(status_code=409, detail="Pinned checklist version is unavailable")
        checklist, version = pair
        try:
            execution_task = task_for_execution(order, task)
            complete_checklist_item(
                order,
                task=execution_task,
                checklist=checklist,
                checklist_version=version,
                item_id=item_id,
                expected_version=payload.expected_version,
                actor_id=context.actor.id,
                authority=authority,
            )
        except InvalidChecklistContract as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except InvalidA5Execution as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        await session.flush()
        await session.refresh(order)
        await BusinessEventRepository(session).append(
            tenant_id=tenant_id,
            incident_id=order.incident_id,
            subject_type="WorkOrder",
            subject_id=str(order.id),
            event_type="CHECKLIST_ITEM_COMPLETED",
            actor_type=context.actor.kind,
            actor_id=context.actor.id,
            actor_version=None,
            data={"itemId": item_id, "workOrderVersion": order.version},
            correlation_id=context.correlation_id,
        )
        return checklist_execution_read(
            order,
            task=execution_task,
            checklist=checklist,
            checklist_version=version,
        )


@router.post("/work-orders/{work_order_id}/assign", response_model=WorkOrderRead)
async def assign_work_order(
    work_order_id: UUID,
    payload: AssignWorkOrderInput,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", min_length=1, max_length=128),
    context: RequestContext = Depends(get_request_context),
    scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority),
    session: AsyncSession = Depends(get_db_session),
) -> WorkOrderRead:
    if context.actor.kind != "user":
        raise HTTPException(status_code=403, detail="A user actor is required to assign a WorkOrder")
    tenant_id = _tenant_id(context)
    async with session.begin():
        repository = WorkOrderRepository(session)
        order = await repository.get_by_id_for_update(
            tenant_id=tenant_id, work_order_id=work_order_id
        )
        if order is None:
            raise HTTPException(status_code=404, detail="WorkOrder not found")
        _require_scope(scope, order.incident_id)
        _require_coordinator(authority)
        authority.require_assign(order, payload.executor_type, payload.executor_id)
        replay = await _replay_lifecycle_command(
            session=session, tenant_id=tenant_id, context=context, command_type="WO_ASSIGN",
            idempotency_key=idempotency_key, payload=payload, work_order_id=order.id,
        )
        if replay is not None:
            return replay
        previous_executor_id = str(order.executor_id) if order.executor_id is not None else None
        previous_executor_type = order.executor_type
        was_assigned = order.status is WorkOrderStatus.ASSIGNED
        try:
            assign(
                order,
                executor_type=payload.executor_type,
                executor_id=payload.executor_id,
                expected_version=payload.expected_version,
                permission=authority,
            )
        except InvalidWorkOrderTransition as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        reset_contractor_response(order)
        await session.flush()
        session.add(
            WorkOrderAssignment(
                work_order_id=order.id,
                work_order_version=order.version,
                executor_type=order.executor_type,
                executor_id=payload.executor_id,
                assigned_by_type=context.actor.kind,
                assigned_by_id=context.actor.id,
            )
        )
        await session.flush()
        await session.refresh(order)
        event = await BusinessEventRepository(session).append(
            tenant_id=tenant_id,
            incident_id=order.incident_id,
            subject_type="WorkOrder",
            subject_id=str(order.id),
            event_type="WORK_ORDER_REASSIGNED" if was_assigned else "WORK_ORDER_ASSIGNED",
            actor_type=context.actor.kind,
            actor_id=context.actor.id,
            actor_version=None,
            data={
                "executorType": order.executor_type,
                "executorId": str(order.executor_id),
                "previousExecutorType": previous_executor_type if was_assigned else None,
                "previousExecutorId": previous_executor_id if was_assigned else None,
                "workOrderVersion": order.version,
            },
            correlation_id=context.correlation_id,
        )
        if event is None:
            raise HTTPException(status_code=404, detail="Incident not found")
        response = WorkOrderRead.model_validate(order)
        await _store_lifecycle_command(
            session=session, tenant_id=tenant_id, context=context, command_type="WO_ASSIGN",
            idempotency_key=idempotency_key, payload=payload, work_order_id=order.id, response=response,
        )
        return response


@router.post("/work-orders/{work_order_id}/start", response_model=WorkOrderRead)
async def start_work_order(
    work_order_id: UUID,
    payload: WorkOrderVersionCommand,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", min_length=1, max_length=128),
    context: RequestContext = Depends(get_request_context),
    scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority),
    session: AsyncSession = Depends(get_db_session),
) -> WorkOrderRead:
    tenant_id = _tenant_id(context)
    async with session.begin():
        repository = WorkOrderRepository(session)
        order = await repository.get_by_id_for_update(
            tenant_id=tenant_id, work_order_id=work_order_id
        )
        if order is None:
            raise HTTPException(status_code=404, detail="WorkOrder not found")
        _require_scope(scope, order.incident_id)
        authority.require_execute(order)
        replay = await _replay_lifecycle_command(
            session=session, tenant_id=tenant_id, context=context, command_type="WO_START",
            idempotency_key=idempotency_key, payload=payload, work_order_id=order.id,
        )
        if replay is not None:
            return replay
        task = await TaskRepository(session).get_by_id(
            tenant_id=tenant_id,
            task_id=order.task_id,
        )
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        if order.executor_type == "CONTRACTOR":
            contractor_response = read_field_operations_state(order).contractor_response
            if contractor_response is None or contractor_response.status != "ACCEPTED":
                raise HTTPException(status_code=409, detail="Contractor must accept this assignment before starting")
        if task.domain_type is TaskDomainType.SECURITY and read_field_operations_state(order).arrival is None:
            raise HTTPException(status_code=409, detail="Security check-in is required before starting")
        start(
            order,
            expected_version=payload.expected_version,
            permission=authority,
        )
        try:
            if task.domain_type in {TaskDomainType.SANITATION, TaskDomainType.LANDSCAPE}:
                if order.redo_of_work_order_id is not None and "a5Execution" in order.result:
                    validate_pinned_a5_execution_plan(order, task)
                else:
                    pin_a5_execution_plan(order, task)
        except InvalidA5Execution as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        await session.flush()
        await session.refresh(order)
        event = await BusinessEventRepository(session).append(
            tenant_id=tenant_id,
            incident_id=order.incident_id,
            subject_type="WorkOrder",
            subject_id=str(order.id),
            event_type="WORK_ORDER_STARTED",
            actor_type=context.actor.kind,
            actor_id=context.actor.id,
            actor_version=None,
            data={"workOrderVersion": order.version},
            correlation_id=context.correlation_id,
        )
        if event is None:
            raise HTTPException(status_code=404, detail="Incident not found")
        response = WorkOrderRead.model_validate(order)
        await _store_lifecycle_command(
            session=session, tenant_id=tenant_id, context=context, command_type="WO_START",
            idempotency_key=idempotency_key, payload=payload, work_order_id=order.id, response=response,
        )
        return response


@router.post("/work-orders/{work_order_id}/complete", response_model=WorkOrderRead)
async def complete_work_order(
    work_order_id: UUID,
    payload: WorkOrderVersionCommand,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", min_length=1, max_length=128),
    context: RequestContext = Depends(get_request_context),
    scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority),
    session: AsyncSession = Depends(get_db_session),
) -> WorkOrderRead:
    """Complete an assigned executor's WorkOrder after its prerequisites pass."""
    tenant_id = _tenant_id(context)
    async with session.begin():
        repository = WorkOrderRepository(session)
        order = await repository.get_by_id_for_update(
            tenant_id=tenant_id,
            work_order_id=work_order_id,
        )
        if order is None:
            raise HTTPException(status_code=404, detail="WorkOrder not found")
        _require_scope(scope, order.incident_id)
        authority.require_execute(order)
        replay = await _replay_lifecycle_command(
            session=session, tenant_id=tenant_id, context=context, command_type="WO_COMPLETE",
            idempotency_key=idempotency_key, payload=payload, work_order_id=order.id,
        )
        if replay is not None:
            return replay
        require_expected_version(order.version, payload.expected_version)
        authority.require_execute(order)
        try:
            require_active_execution(order)
        except InvalidFieldOperationsState as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if order.status is not WorkOrderStatus.IN_PROGRESS:
            raise HTTPException(
                status_code=409,
                detail="Only a started WorkOrder can be completed",
            )
        task = await TaskRepository(session).get_by_id(
            tenant_id=tenant_id,
            task_id=order.task_id,
        )
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        if await repository.has_later_attempt(tenant_id=tenant_id, work_order=order):
            raise HTTPException(
                status_code=409,
                detail="An older WorkOrder attempt cannot be completed",
            )

        if task.domain_type in {TaskDomainType.SANITATION, TaskDomainType.LANDSCAPE}:
            execution = await _a5_execution_projection(
                session=session,
                tenant_id=tenant_id,
                order=order,
                task=task,
            )
            completion_blockers = execution.blockers
        else:
            completion_blockers = await _generic_execution_blockers(
                session=session, tenant_id=tenant_id, order=order, task=task
            )
            if task.domain_type is TaskDomainType.SECURITY:
                field_state = read_field_operations_state(order)
                if field_state.arrival is None or field_state.arrival.checked_out_at is None:
                    completion_blockers.append("SECURITY_CHECK_OUT_REQUIRED")
        if completion_blockers:
            raise HTTPException(
                status_code=409,
                detail=(
                    "WorkOrder prerequisites are incomplete: "
                    f"{', '.join(completion_blockers)}"
                ),
            )
        try:
            complete_lifecycle(
                order,
                expected_version=payload.expected_version,
                permission=authority,
            )
        except InvalidWorkOrderTransition as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        field_state = read_field_operations_state(order)
        field_state.execution_state = "COMPLETED"
        write_field_operations_state(order, field_state)
        await session.flush()
        await session.refresh(order)
        event = await BusinessEventRepository(session).append(
            tenant_id=tenant_id,
            incident_id=order.incident_id,
            subject_type="WorkOrder",
            subject_id=str(order.id),
            event_type="WORK_ORDER_COMPLETED",
            actor_type=context.actor.kind,
            actor_id=context.actor.id,
            actor_version=None,
            data={"workOrderVersion": order.version, "taskId": str(task.id)},
            correlation_id=context.correlation_id,
        )
        if event is None:
            raise HTTPException(status_code=404, detail="Incident not found")
        response = WorkOrderRead.model_validate(order)
        await _store_lifecycle_command(
            session=session, tenant_id=tenant_id, context=context, command_type="WO_COMPLETE",
            idempotency_key=idempotency_key, payload=payload, work_order_id=order.id, response=response,
        )
        return response


async def _a5_execution_projection(
    *,
    session: AsyncSession,
    tenant_id: UUID,
    order,
    task,
) -> A5ExecutionRead:
    try:
        execution_task = a5_task_projection(order, task)
    except InvalidA5Execution as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    rows = await EvidenceRepository(session).list_work_order_evidence(
        tenant_id=tenant_id,
        work_order=order,
    )
    checklist: Checklist | None = None
    checklist_version: ChecklistVersion | None = None
    if order.checklist_version_id is not None:
        pair = await ChecklistRepository(session).get_version_for_tenant(
            tenant_id=tenant_id,
            checklist_version_id=order.checklist_version_id,
        )
        if pair is None:
            raise HTTPException(status_code=409, detail="Pinned checklist version is unavailable")
        checklist, checklist_version = pair
    checklist_read = checklist_execution_read(
        order,
        task=execution_task,
        checklist=checklist,
        checklist_version=checklist_version,
    )
    evidence_read = work_order_evidence_read(
        order,
        task=execution_task,
        rows=rows,
        checklist=checklist_read,
    )
    try:
        return a5_execution_read(
            order,
            execution_task,
            satisfied_required_evidence=evidence_read.satisfied_required_evidence,
            missing_required_evidence=evidence_read.missing_required_evidence,
            unsupported_required_evidence=evidence_read.unsupported_required_evidence,
            evidence_blockers=evidence_read.blockers,
        )
    except InvalidA5Execution as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


async def _generic_execution_blockers(*, session: AsyncSession, tenant_id: UUID, order, task) -> list[str]:
    """Evaluate shared checklist and evidence prerequisites for non-A5 work."""
    evidence_rows = await EvidenceRepository(session).list_work_order_evidence(
        tenant_id=tenant_id, work_order=order
    )
    checklist: Checklist | None = None
    checklist_version: ChecklistVersion | None = None
    if order.checklist_version_id is not None:
        pair = await ChecklistRepository(session).get_version_for_tenant(
            tenant_id=tenant_id, checklist_version_id=order.checklist_version_id
        )
        if pair is None:
            return ["PINNED_CHECKLIST_UNAVAILABLE"]
        checklist, checklist_version = pair
    checklist_read = checklist_execution_read(
        order, task=task, checklist=checklist, checklist_version=checklist_version
    )
    evidence_read = work_order_evidence_read(
        order, task=task, rows=evidence_rows, checklist=checklist_read
    )
    return evidence_read.blockers


@router.get(
    "/work-orders/{work_order_id}/a5-execution",
    response_model=A5ExecutionRead,
)
async def get_work_order_a5_execution(
    work_order_id: UUID,
    context: RequestContext = Depends(get_request_context),
    scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority),
    session: AsyncSession = Depends(get_db_session),
) -> A5ExecutionRead:
    tenant_id = _tenant_id(context)
    order = await WorkOrderRepository(session).get_by_id(
        tenant_id=tenant_id,
        work_order_id=work_order_id,
    )
    if order is None or not authority.can_read(order, scope):
        raise HTTPException(status_code=404, detail="WorkOrder not found")
    task = await TaskRepository(session).get_by_id(tenant_id=tenant_id, task_id=order.task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return await _a5_execution_projection(
        session=session,
        tenant_id=tenant_id,
        order=order,
        task=task,
    )


@router.post(
    "/work-orders/{work_order_id}/cleaning-actions/{action_id}/complete",
    response_model=A5ExecutionRead,
)
async def complete_work_order_cleaning_action(
    work_order_id: UUID,
    action_id: UUID,
    payload: CompleteA5ActionInput,
    context: RequestContext = Depends(get_request_context),
    scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority),
    session: AsyncSession = Depends(get_db_session),
) -> A5ExecutionRead:
    tenant_id = _tenant_id(context)
    async with session.begin():
        repository = WorkOrderRepository(session)
        order = await repository.get_by_id_for_update(
            tenant_id=tenant_id,
            work_order_id=work_order_id,
        )
        if order is None:
            raise HTTPException(status_code=404, detail="WorkOrder not found")
        _require_scope(scope, order.incident_id)
        task = await TaskRepository(session).get_by_id(
            tenant_id=tenant_id,
            task_id=order.task_id,
        )
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        if await repository.has_later_attempt(tenant_id=tenant_id, work_order=order):
            raise HTTPException(
                status_code=409,
                detail="Actions cannot be completed on an older WorkOrder attempt",
            )
        try:
            require_active_execution(order)
        except InvalidFieldOperationsState as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        try:
            complete_a5_action(
                order,
                task,
                action_id=action_id,
                expected_version=payload.expected_version,
                actor_id=context.actor.id,
                authority=authority,
            )
        except InvalidA5Execution as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        await session.flush()
        await session.refresh(order)
        await BusinessEventRepository(session).append(
            tenant_id=tenant_id,
            incident_id=order.incident_id,
            subject_type="WorkOrder",
            subject_id=str(order.id),
            event_type="A5_ACTION_COMPLETED",
            actor_type=context.actor.kind,
            actor_id=context.actor.id,
            actor_version=None,
            data={"actionId": str(action_id), "workOrderVersion": order.version},
            correlation_id=context.correlation_id,
        )
        return await _a5_execution_projection(
            session=session,
            tenant_id=tenant_id,
            order=order,
            task=task,
        )


@router.get(
    "/work-orders/{work_order_id}/assignments",
    response_model=list[WorkOrderAssignmentRead],
)
async def list_work_order_assignments(
    work_order_id: UUID,
    context: RequestContext = Depends(get_request_context),
    scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority),
    session: AsyncSession = Depends(get_db_session),
) -> list[WorkOrderAssignmentRead]:
    tenant_id = _tenant_id(context)
    order = await WorkOrderRepository(session).get_by_id(
        tenant_id=tenant_id, work_order_id=work_order_id
    )
    if order is None:
        raise HTTPException(status_code=404, detail="WorkOrder not found")
    _require_scope(scope, order.incident_id)
    if not authority.roles.intersection(
        {FieldOperationsRole.SUPERVISOR, FieldOperationsRole.BQL_COORDINATOR}
    ):
        raise HTTPException(status_code=403, detail="Supervisor or BQL coordinator role required")
    rows = await WorkOrderRepository(session).list_assignments(
        tenant_id=tenant_id, work_order_id=work_order_id
    )
    return [WorkOrderAssignmentRead.model_validate(row) for row in rows]


@router.get(
    "/work-orders/{work_order_id}/execution-details",
    response_model=ExecutionDetailsRead,
)
async def get_work_order_execution_details(
    work_order_id: UUID,
    context: RequestContext = Depends(get_request_context),
    scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority),
    session: AsyncSession = Depends(get_db_session),
) -> ExecutionDetailsRead:
    order = await WorkOrderRepository(session).get_by_id(
        tenant_id=_tenant_id(context), work_order_id=work_order_id
    )
    if order is None or not authority.can_read(order, scope):
        raise HTTPException(status_code=404, detail="WorkOrder not found")
    _require_scope(scope, order.incident_id)
    try:
        return execution_details_read(order)
    except InvalidExecutionDetails as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


async def _append_execution_detail(
    *,
    work_order_id: UUID,
    detail_kind: Literal[
        "measurements", "materialUsage", "equipmentUsage", "executionNotes"
    ],
    payload: BaseModel,
    record_factory: Callable[..., BaseModel],
    context: RequestContext,
    scope: DomainScope,
    authority: FieldOperationsAuthority,
    session: AsyncSession,
) -> ExecutionDetailsRead:
    tenant_id = _tenant_id(context)
    async with session.begin():
        order = await WorkOrderRepository(session).get_by_id_for_update(
            tenant_id=tenant_id,
            work_order_id=work_order_id,
        )
        if order is None:
            raise HTTPException(status_code=404, detail="WorkOrder not found")
        _require_scope(scope, order.incident_id)
        authority.require_execute(order)
        try:
            require_active_execution(order)
        except InvalidFieldOperationsState as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if await WorkOrderRepository(session).has_later_attempt(
            tenant_id=tenant_id,
            work_order=order,
        ):
            raise HTTPException(
                status_code=409,
                detail="Execution details cannot be added to an older WorkOrder attempt",
            )
        try:
            record = record_factory(payload, actor_id=context.actor.id)
            append_execution_detail(
                order,
                detail_kind=detail_kind,
                record=record,
                expected_version=payload.expected_version,
                authority=authority,
            )
        except InvalidExecutionDetails as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        await session.flush()
        await session.refresh(order)
        event_kind = {
            "measurements": "MEASUREMENT_RECORDED",
            "materialUsage": "MATERIAL_USAGE_RECORDED",
            "equipmentUsage": "EQUIPMENT_USAGE_RECORDED",
            "executionNotes": "EXECUTION_NOTE_ADDED",
        }[detail_kind]
        await BusinessEventRepository(session).append(
            tenant_id=tenant_id,
            incident_id=order.incident_id,
            subject_type="WorkOrder",
            subject_id=str(order.id),
            event_type=event_kind,
            actor_type=context.actor.kind,
            actor_id=context.actor.id,
            actor_version=None,
            data={"workOrderVersion": order.version, "recordId": str(record.id)},
            correlation_id=context.correlation_id,
        )
        return execution_details_read(order)


@router.post(
    "/work-orders/{work_order_id}/measurements",
    response_model=ExecutionDetailsRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_work_order_measurement(
    work_order_id: UUID,
    payload: AddMeasurementInput,
    context: RequestContext = Depends(get_request_context),
    scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority),
    session: AsyncSession = Depends(get_db_session),
) -> ExecutionDetailsRead:
    return await _append_execution_detail(
        work_order_id=work_order_id,
        detail_kind="measurements",
        payload=payload,
        record_factory=make_measurement_record,
        context=context,
        scope=scope,
        authority=authority,
        session=session,
    )


@router.post(
    "/work-orders/{work_order_id}/material-usage",
    response_model=ExecutionDetailsRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_work_order_material_usage(
    work_order_id: UUID,
    payload: AddMaterialUsageInput,
    context: RequestContext = Depends(get_request_context),
    scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority),
    session: AsyncSession = Depends(get_db_session),
) -> ExecutionDetailsRead:
    return await _append_execution_detail(
        work_order_id=work_order_id,
        detail_kind="materialUsage",
        payload=payload,
        record_factory=make_material_usage_record,
        context=context,
        scope=scope,
        authority=authority,
        session=session,
    )


@router.post(
    "/work-orders/{work_order_id}/equipment-usage",
    response_model=ExecutionDetailsRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_work_order_equipment_usage(
    work_order_id: UUID,
    payload: AddEquipmentUsageInput,
    context: RequestContext = Depends(get_request_context),
    scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority),
    session: AsyncSession = Depends(get_db_session),
) -> ExecutionDetailsRead:
    return await _append_execution_detail(
        work_order_id=work_order_id,
        detail_kind="equipmentUsage",
        payload=payload,
        record_factory=make_equipment_usage_record,
        context=context,
        scope=scope,
        authority=authority,
        session=session,
    )


@router.post(
    "/work-orders/{work_order_id}/execution-notes",
    response_model=ExecutionDetailsRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_work_order_execution_note(
    work_order_id: UUID,
    payload: AddExecutionNoteInput,
    context: RequestContext = Depends(get_request_context),
    scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority),
    session: AsyncSession = Depends(get_db_session),
) -> ExecutionDetailsRead:
    return await _append_execution_detail(
        work_order_id=work_order_id,
        detail_kind="executionNotes",
        payload=payload,
        record_factory=make_execution_note_record,
        context=context,
        scope=scope,
        authority=authority,
        session=session,
    )
