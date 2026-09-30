"""Task creation and tenant-scoped read endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..concurrency import require_expected_version
from ..db.dependencies import get_db_session
from ..db.task import Task, TaskStatus
from ..events import BusinessEventRepository
from ..incidents.repository import IncidentRepository
from ..request_context import (
    DomainScope,
    RequestContext,
    get_domain_scope,
    get_request_context,
    scope_contains_subject,
)
from ..work_orders.authority import (
    FieldOperationsAuthority,
    FieldOperationsRole,
    get_field_operations_authority,
)
from .repository import TaskRepository
from .schemas import AssignTaskInput, CreateTaskInput, TaskRead


router = APIRouter(tags=["tasks"])


def _tenant_uuid(context: RequestContext) -> UUID:
    try:
        return UUID(context.tenant_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=401,
            detail="Authenticated tenant identifier is invalid",
        ) from exc


def _require_incident_scope(scope: DomainScope, incident_id: UUID) -> None:
    if not scope_contains_subject(
        scope,
        namespace="vinhomes",
        subject_type="incident",
        subject_id=str(incident_id),
    ):
        raise HTTPException(
            status_code=403,
            detail="Incident is outside the effective domain scope",
        )


def _require_coordinator(authority: FieldOperationsAuthority) -> None:
    if authority.actor_type != "user" or not authority.roles.intersection(
        {FieldOperationsRole.SUPERVISOR, FieldOperationsRole.BQL_COORDINATOR}
    ):
        raise HTTPException(
            status_code=403,
            detail="Supervisor or BQL coordinator role required",
        )


@router.post("/incidents/{incident_id}/tasks", response_model=TaskRead, status_code=201)
async def create_task(
    incident_id: UUID,
    payload: CreateTaskInput,
    context: RequestContext = Depends(get_request_context),
    scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority),
    session: AsyncSession = Depends(get_db_session),
) -> Task:
    _require_coordinator(authority)
    tenant_id = _tenant_uuid(context)
    async with session.begin():
        incident = await IncidentRepository(session).get_by_id(
            tenant_id=tenant_id,
            incident_id=incident_id,
        )
        if incident is None:
            raise HTTPException(status_code=404, detail="Incident not found")
        _require_incident_scope(scope, incident_id)

        task = Task(
            incident_id=incident.id,
            title=payload.title,
            domain_type=payload.domain_type,
            domain_data=payload.domain_data.model_dump(mode="json", by_alias=True),
            domain_schema_version=payload.domain_data.schema_version,
            assignee_type=payload.assignee_type,
            assignee_id=None,
            status=TaskStatus.OPEN,
            priority=payload.priority,
            due_at=payload.due_at,
        )
        created_task = await TaskRepository(session).add(task, tenant_id=tenant_id)
        if created_task is None:
            raise HTTPException(status_code=404, detail="Incident not found")

        event = await BusinessEventRepository(session).append(
            tenant_id=tenant_id,
            incident_id=incident_id,
            subject_type="Task",
            subject_id=str(created_task.id),
            event_type="TASK_CREATED",
            actor_type=context.actor.kind,
            actor_id=context.actor.id,
            actor_version=None,
            data={
                "domainType": created_task.domain_type.value,
                "domainSchemaVersion": created_task.domain_schema_version,
            },
            correlation_id=context.correlation_id,
        )
        if event is None:
            raise HTTPException(status_code=404, detail="Incident not found")
        await session.refresh(created_task)
        return created_task


@router.get("/incidents/{incident_id}/tasks", response_model=list[TaskRead])
async def list_incident_tasks(
    incident_id: UUID,
    context: RequestContext = Depends(get_request_context),
    scope: DomainScope = Depends(get_domain_scope),
    session: AsyncSession = Depends(get_db_session),
) -> list[Task]:
    tenant_id = _tenant_uuid(context)
    incident = await IncidentRepository(session).get_by_id(
        tenant_id=tenant_id,
        incident_id=incident_id,
    )
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    _require_incident_scope(scope, incident_id)
    return await TaskRepository(session).list_by_incident(
        tenant_id=tenant_id,
        incident_id=incident_id,
    )


@router.get("/tasks/{task_id}", response_model=TaskRead)
async def get_task(
    task_id: UUID,
    context: RequestContext = Depends(get_request_context),
    scope: DomainScope = Depends(get_domain_scope),
    session: AsyncSession = Depends(get_db_session),
) -> Task:
    tenant_id = _tenant_uuid(context)
    task = await TaskRepository(session).get_by_id(tenant_id=tenant_id, task_id=task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    _require_incident_scope(scope, task.incident_id)
    return task


@router.post("/tasks/{task_id}/assign", response_model=TaskRead)
async def assign_task(
    task_id: UUID,
    payload: AssignTaskInput,
    context: RequestContext = Depends(get_request_context),
    scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority),
    session: AsyncSession = Depends(get_db_session),
) -> Task:
    _require_coordinator(authority)

    tenant_id = _tenant_uuid(context)
    async with session.begin():
        task = await TaskRepository(session).get_by_id(
            tenant_id=tenant_id,
            task_id=task_id,
        )
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        _require_incident_scope(scope, task.incident_id)
        require_expected_version(task.version, payload.expected_version)
        if task.status != TaskStatus.OPEN:
            raise HTTPException(status_code=409, detail="Only OPEN tasks can be assigned")
        if not authority.can_assign(
            payload.assignee_type,
            payload.assignee_id,
            task.incident_id,
        ):
            raise HTTPException(
                status_code=403,
                detail="Task assignee is outside the assigner's resolved team or contract scope",
            )

        task.assignee_type = payload.assignee_type
        task.assignee_id = payload.assignee_id
        task.status = TaskStatus.ASSIGNED
        await session.flush()
        await session.refresh(task)
        return task
