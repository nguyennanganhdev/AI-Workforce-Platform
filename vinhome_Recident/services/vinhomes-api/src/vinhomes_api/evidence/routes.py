"""Trusted file metadata registration and scoped WorkOrder evidence routes."""

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.checklist import Checklist, ChecklistVersion
from ..commands.idempotency import replay_command_response, store_command_response
from ..db.dependencies import get_db_session
from ..db.evidence import EvidenceRef, FileObject
from ..events import BusinessEventRepository
from ..request_context import (
    DomainScope,
    RequestContext,
    get_domain_scope,
    get_request_context,
    scope_contains_subject,
)
from ..tasks.repository import TaskRepository
from ..work_orders.a5_execution import InvalidA5Execution, task_for_execution
from ..work_orders.authority import FieldOperationsAuthority, get_field_operations_authority
from ..work_orders.authority import FieldOperationsRole
from ..work_orders.field_operations_state import InvalidFieldOperationsState, require_active_execution
from ..work_orders.checklist_execution import checklist_execution_read
from ..work_orders.checklist_repository import ChecklistRepository
from ..work_orders.repository import WorkOrderRepository
from .repository import EvidenceRepository
from .schemas import (
    CreateEvidenceInput,
    FileObjectRead,
    RegisterFileObjectInput,
    WorkOrderEvidenceRead,
)
from .service import (
    InvalidEvidenceMetadata,
    authorize_evidence_write,
    validate_image_video_metadata,
    work_order_evidence_read,
)


router = APIRouter(tags=["field-evidence"])


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


async def _checklist_for_work_order(session: AsyncSession, tenant_id: UUID, order):
    if order.checklist_version_id is None:
        return None, None
    pair = await ChecklistRepository(session).get_version_for_tenant(
        tenant_id=tenant_id,
        checklist_version_id=order.checklist_version_id,
    )
    if pair is None:
        raise HTTPException(status_code=409, detail="Pinned checklist version is unavailable")
    checklist, version = pair
    return checklist, version


@router.post("/file-objects", response_model=FileObjectRead, status_code=201)
async def register_file_object(
    payload: RegisterFileObjectInput,
    context: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_db_session),
) -> FileObjectRead:
    """Register metadata for an object already stored by trusted file service."""
    if context.actor.kind != "service":
        raise HTTPException(status_code=403, detail="Trusted storage service actor required")
    file_object = FileObject(
        id=uuid4(),
        tenant_id=_tenant_id(context),
        storage_provider=payload.storage_provider,
        storage_key=payload.storage_key,
        mime_type=payload.mime_type,
        size_bytes=payload.size_bytes,
        checksum=payload.checksum,
    )
    try:
        async with session.begin():
            await EvidenceRepository(session).add_file_object(file_object)
            await session.refresh(file_object)
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="A FileObject already exists for this tenant storage key",
        ) from exc
    return FileObjectRead.model_validate(file_object)


@router.get(
    "/work-orders/{work_order_id}/evidence",
    response_model=WorkOrderEvidenceRead,
)
async def list_work_order_evidence(
    work_order_id: UUID,
    context: RequestContext = Depends(get_request_context),
    scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority),
    session: AsyncSession = Depends(get_db_session),
) -> WorkOrderEvidenceRead:
    tenant_id = _tenant_id(context)
    order = await WorkOrderRepository(session).get_by_id(
        tenant_id=tenant_id,
        work_order_id=work_order_id,
    )
    if order is None or not authority.can_read(order, scope):
        raise HTTPException(status_code=404, detail="WorkOrder not found")
    _require_scope(scope, order.incident_id)
    task = await TaskRepository(session).get_by_id(tenant_id=tenant_id, task_id=order.task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    rows = await EvidenceRepository(session).list_work_order_evidence(
        tenant_id=tenant_id,
        work_order=order,
    )
    try:
        execution_task = task_for_execution(order, task)
    except InvalidA5Execution as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    checklist, checklist_version = await _checklist_for_work_order(
        session,
        tenant_id,
        order,
    )
    checklist_read = checklist_execution_read(
        order,
        task=execution_task,
        checklist=checklist,
        checklist_version=checklist_version,
    )
    return work_order_evidence_read(
        order,
        task=execution_task,
        rows=rows,
        checklist=checklist_read,
    )


@router.post(
    "/work-orders/{work_order_id}/evidence",
    response_model=WorkOrderEvidenceRead,
    status_code=201,
)
async def add_work_order_evidence(
    work_order_id: UUID,
    payload: CreateEvidenceInput,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", min_length=1, max_length=128),
    context: RequestContext = Depends(get_request_context),
    scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority),
    session: AsyncSession = Depends(get_db_session),
) -> WorkOrderEvidenceRead:
    tenant_id = _tenant_id(context)
    async with session.begin():
        order = await WorkOrderRepository(session).get_by_id_for_update(
            tenant_id=tenant_id,
            work_order_id=work_order_id,
        )
        if order is None:
            raise HTTPException(status_code=404, detail="WorkOrder not found")
        _require_scope(scope, order.incident_id)
        if payload.capture_phase.value == "QC":
            if authority.actor_type != "user" or FieldOperationsRole.QC not in authority.roles:
                raise HTTPException(status_code=403, detail="QC role required for QC evidence")
            if context.actor.id == str(order.executor_id):
                raise HTTPException(status_code=403, detail="Executor cannot provide independent QC evidence")
        else:
            authority.require_execute(order)
        replay = await replay_command_response(
            session=session,
            tenant_id=tenant_id,
            actor_type=context.actor.kind,
            actor_id=context.actor.id,
            command_type="EVIDENCE_ADD",
            idempotency_key=idempotency_key,
            subject_type="WorkOrder",
            subject_id=str(order.id),
            payload=payload,
            response_model=WorkOrderEvidenceRead,
        )
        if replay is not None:
            return replay
        if payload.capture_phase.value != "QC":
            try:
                require_active_execution(order)
            except InvalidFieldOperationsState as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
        task = await TaskRepository(session).get_by_id(
            tenant_id=tenant_id,
            task_id=order.task_id,
        )
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        try:
            execution_task = task_for_execution(order, task)
        except InvalidA5Execution as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        repository = EvidenceRepository(session)
        file_object = await repository.get_file_object(
            tenant_id=tenant_id,
            file_object_id=payload.file_object_id,
        )
        if file_object is None:
            raise HTTPException(status_code=404, detail="FileObject not found")
        if await repository.has_later_attempt(tenant_id=tenant_id, work_order=order):
            raise HTTPException(status_code=409, detail="Evidence cannot be added to an older WorkOrder attempt")
        authorize_evidence_write(
            authority,
            order,
            capture_phase=payload.capture_phase,
            actor_id=context.actor.id,
        )
        try:
            validate_image_video_metadata(file_object.mime_type, payload.metadata)
        except InvalidEvidenceMetadata as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        reference = EvidenceRef(
            id=uuid4(),
            incident_id=order.incident_id,
            task_id=order.task_id,
            work_order_id=order.id,
            file_id=file_object.id,
            kind=payload.kind,
            capture_phase=payload.capture_phase,
            evidence_metadata=payload.metadata.model_dump(
                mode="json",
                by_alias=True,
                exclude_none=True,
            ),
            uploaded_by=context.actor.id,
        )
        await repository.add_evidence_ref(reference)
        await session.refresh(reference)
        event = await BusinessEventRepository(session).append(
            tenant_id=tenant_id,
            incident_id=order.incident_id,
            subject_type="EvidenceRef",
            subject_id=str(reference.id),
            event_type="EVIDENCE_ADDED",
            actor_type=context.actor.kind,
            actor_id=context.actor.id,
            actor_version=None,
            data={
                "workOrderId": str(order.id),
                "taskId": str(order.task_id),
                "capturePhase": reference.capture_phase.value,
                "kind": reference.kind,
            },
            correlation_id=context.correlation_id,
        )
        if event is None:
            raise HTTPException(status_code=404, detail="Incident not found")
        rows = await repository.list_work_order_evidence(
            tenant_id=tenant_id,
            work_order=order,
        )
        checklist, checklist_version = await _checklist_for_work_order(
            session,
            tenant_id,
            order,
        )
        checklist_read = checklist_execution_read(
            order,
            task=execution_task,
            checklist=checklist,
            checklist_version=checklist_version,
        )
        response = work_order_evidence_read(
            order,
            task=execution_task,
            rows=rows,
            checklist=checklist_read,
        )
        await store_command_response(
            session=session,
            tenant_id=tenant_id,
            actor_type=context.actor.kind,
            actor_id=context.actor.id,
            command_type="EVIDENCE_ADD",
            idempotency_key=idempotency_key,
            subject_type="WorkOrder",
            subject_id=str(order.id),
            payload=payload,
            response=response,
        )
        return response
