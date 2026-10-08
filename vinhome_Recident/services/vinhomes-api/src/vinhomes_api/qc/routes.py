"""Scoped QC queue, detail, and immutable decision routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..concurrency import require_expected_version
from ..commands.idempotency import replay_command_response, store_command_response
from ..db.dependencies import get_db_session
from ..db.qc_result import QCOutcome, QCResult
from ..db.task import TaskStatus
from ..db.work_order import WorkOrderStatus
from ..events import BusinessEventRepository
from ..request_context import (
    DomainScope,
    RequestContext,
    get_domain_scope,
    get_request_context,
    scope_contains_subject,
)
from ..tasks.repository import TaskRepository
from ..work_orders.authority import (
    FieldOperationsAuthority,
    FieldOperationsRole,
    get_field_operations_authority,
)
from ..work_orders.redo import InvalidRedoRequest, create_redo_work_order
from ..work_orders.repository import WorkOrderRepository
from ..work_orders.schemas import WorkOrderRead
from .repository import QCRepository
from .schemas import (
    QCQueuePage,
    QCResultRead,
    QCSubmissionRead,
    QCWorkOrderDetail,
    SubmitQCInput,
    qc_result_read,
    queue_item_read,
)
from .service import (
    actor_matches_executor,
    build_qc_work_order_detail,
    qc_evidence_projection,
    validate_qc_result,
)


router = APIRouter(tags=["field-qc"])
_MAX_PAGE_SIZE = 100


def _tenant_uuid(context: RequestContext) -> UUID:
    try:
        return UUID(context.tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Authenticated tenant identifier is invalid") from exc


def _require_qc_role(authority: FieldOperationsAuthority) -> None:
    if authority.actor_type != "user" or FieldOperationsRole.QC not in authority.roles:
        raise HTTPException(status_code=403, detail="QC role required")


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


def _require_work_order_scope(scope: DomainScope, incident_id: UUID) -> None:
    if not scope_contains_subject(
        scope,
        namespace="vinhomes",
        subject_type="incident",
        subject_id=str(incident_id),
    ):
        raise HTTPException(status_code=404, detail="WorkOrder not found")


@router.get("/qc/work-orders", response_model=QCQueuePage)
async def list_qc_queue(
    context: RequestContext = Depends(get_request_context),
    scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority),
    session: AsyncSession = Depends(get_db_session),
    limit: int = Query(default=25, ge=1, le=_MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0),
) -> QCQueuePage:
    _require_qc_role(authority)
    rows, total = await QCRepository(session).list_waiting_work_orders(
        tenant_id=_tenant_uuid(context),
        scoped_incident_ids=_scoped_incident_ids(scope),
        limit=limit,
        offset=offset,
    )
    items = [
        queue_item_read(order, task, incident)
        for order, task, incident in rows
        if authority.can_read(order, scope)
    ]
    return QCQueuePage(items=items, total=total, limit=limit, offset=offset)


@router.get("/qc/work-orders/{work_order_id}", response_model=QCWorkOrderDetail)
async def get_qc_work_order_detail(
    work_order_id: UUID,
    context: RequestContext = Depends(get_request_context),
    scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority),
    session: AsyncSession = Depends(get_db_session),
) -> QCWorkOrderDetail:
    _require_qc_role(authority)
    tenant_id = _tenant_uuid(context)
    order = await WorkOrderRepository(session).get_by_id(
        tenant_id=tenant_id,
        work_order_id=work_order_id,
    )
    if order is None or not authority.can_read(order, scope):
        raise HTTPException(status_code=404, detail="WorkOrder not found")
    task = await TaskRepository(session).get_by_id(tenant_id=tenant_id, task_id=order.task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return await build_qc_work_order_detail(
        session=session,
        tenant_id=tenant_id,
        work_order=order,
        task=task,
        actor_id=context.actor.id,
    )


@router.post(
    "/qc/work-orders/{work_order_id}/results",
    response_model=QCSubmissionRead,
    status_code=status.HTTP_201_CREATED,
)
async def submit_qc_result(
    work_order_id: UUID,
    payload: SubmitQCInput,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", min_length=1, max_length=128),
    context: RequestContext = Depends(get_request_context),
    scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority),
    session: AsyncSession = Depends(get_db_session),
) -> QCSubmissionRead:
    _require_qc_role(authority)
    tenant_id = _tenant_uuid(context)
    async with session.begin():
        work_orders = WorkOrderRepository(session)
        order = await work_orders.get_by_id_for_update(
            tenant_id=tenant_id,
            work_order_id=work_order_id,
        )
        if order is None:
            raise HTTPException(status_code=404, detail="WorkOrder not found")
        _require_work_order_scope(scope, order.incident_id)
        replay = await replay_command_response(
            session=session,
            tenant_id=tenant_id,
            actor_type=context.actor.kind,
            actor_id=context.actor.id,
            command_type="QC_SUBMIT",
            idempotency_key=idempotency_key,
            subject_type="WorkOrder",
            subject_id=str(order.id),
            payload=payload,
            response_model=QCSubmissionRead,
        )
        if replay is not None:
            return replay
        if order.status is not WorkOrderStatus.COMPLETED:
            raise HTTPException(status_code=409, detail="QC requires a COMPLETED WorkOrder")
        if await work_orders.has_later_attempt(tenant_id=tenant_id, work_order=order):
            raise HTTPException(status_code=409, detail="QC can only be submitted for the latest WorkOrder attempt")
        require_expected_version(order.version, payload.expected_version)
        if order.executor_id is not None and actor_matches_executor(
            context.actor.id, order.executor_id
        ):
            raise HTTPException(status_code=403, detail="Executor cannot QC their own WorkOrder")

        task = await TaskRepository(session).get_by_id(tenant_id=tenant_id, task_id=order.task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        detail = await build_qc_work_order_detail(
            session=session,
            tenant_id=tenant_id,
            work_order=order,
            task=task,
            actor_id=context.actor.id,
        )
        if "QC_RESULT_ALREADY_RECORDED" in detail.blockers:
            raise HTTPException(
                status_code=409,
                detail="A QC result already exists; correction semantics are not defined by the current contract",
            )
        if detail.blockers:
            raise HTTPException(
                status_code=409,
                detail=f"QC prerequisites are incomplete: {', '.join(detail.blockers)}",
            )

        if detail.qc_criteria is None:
            raise HTTPException(
                status_code=409,
                detail="QC criteria are not defined for this Task domain by the current contract",
            )
        ordered_failures = validate_qc_result(
            criteria=detail.qc_criteria,
            outcome=payload.outcome,
            failed_criteria=payload.failed_criteria,
            redo_required=payload.redo_required,
        )
        evidence_by_id = {item.id: item for item in detail.evidence.items}
        selected_evidence = []
        for evidence_id in payload.evidence_ref_ids:
            item = evidence_by_id.get(evidence_id)
            if item is None or item.capture_phase.value != "QC":
                raise HTTPException(
                    status_code=422,
                    detail="evidenceRefIds must reference QC evidence attached to this WorkOrder",
                )
            selected_evidence.append(item)

        result = QCResult(
            work_order_id=order.id,
            outcome=payload.outcome,
            criteria_json=detail.qc_criteria,
            failed_criteria_json=ordered_failures,
            redo_required=payload.redo_required,
            note=payload.note,
            checked_by=context.actor.id,
        )
        qc_repository = QCRepository(session)
        await qc_repository.add_result(result)
        for item in selected_evidence:
            await qc_repository.add_evidence_link(result.id, item.id)
        redo_work_order = None
        if payload.outcome is QCOutcome.FAIL and payload.redo_required:
            try:
                redo_work_order = await create_redo_work_order(
                    session,
                    tenant_id=tenant_id,
                    failed_work_order=order,
                    qc_result=result,
                )
            except InvalidRedoRequest as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
        event_repository = BusinessEventRepository(session)
        event = await event_repository.append(
            tenant_id=tenant_id,
            incident_id=order.incident_id,
            subject_type="QCResult",
            subject_id=str(result.id),
            event_type={
                QCOutcome.PASS: "QC_PASSED",
                QCOutcome.FAIL: "QC_FAILED",
                QCOutcome.INCONCLUSIVE: "QC_INCONCLUSIVE",
            }[payload.outcome],
            actor_type=context.actor.kind,
            actor_id=context.actor.id,
            actor_version=None,
            data={
                "workOrderId": str(order.id),
                "taskId": str(task.id),
                "outcome": payload.outcome.value,
                "failedCriteria": ordered_failures,
                "redoRequired": payload.redo_required,
            },
            correlation_id=context.correlation_id,
        )
        if event is None:
            raise HTTPException(status_code=404, detail="Incident not found")
        if payload.outcome is QCOutcome.PASS:
            task.status = TaskStatus.DONE
            await session.flush()
            task_event = await event_repository.append(
                tenant_id=tenant_id,
                incident_id=order.incident_id,
                subject_type="Task",
                subject_id=str(task.id),
                event_type="TASK_COMPLETED",
                actor_type=context.actor.kind,
                actor_id=context.actor.id,
                actor_version=None,
                data={"workOrderId": str(order.id), "qcResultId": str(result.id)},
                correlation_id=context.correlation_id,
            )
            if task_event is None:
                raise HTTPException(status_code=404, detail="Incident not found")
        if redo_work_order is not None:
            redo_event = await event_repository.append(
                tenant_id=tenant_id,
                incident_id=order.incident_id,
                subject_type="WorkOrder",
                subject_id=str(redo_work_order.id),
                event_type="REDO_CREATED",
                actor_type=context.actor.kind,
                actor_id=context.actor.id,
                actor_version=None,
                data={
                    "taskId": str(task.id),
                    "redoOfWorkOrderId": str(order.id),
                    "attemptNo": redo_work_order.attempt_no,
                    "qcResultId": str(result.id),
                },
                correlation_id=context.correlation_id,
            )
            if redo_event is None:
                raise HTTPException(status_code=404, detail="Incident not found")
        await session.refresh(result)
        linked_rows = await qc_repository.list_result_evidence(
            tenant_id=tenant_id,
            qc_result_id=result.id,
        )
        response = QCSubmissionRead(
            result=qc_result_read(result, evidence=qc_evidence_projection(linked_rows)),
            redoWorkOrder=(
                WorkOrderRead.model_validate(redo_work_order)
                if redo_work_order is not None
                else None
            ),
        )
        await store_command_response(
            session=session,
            tenant_id=tenant_id,
            actor_type=context.actor.kind,
            actor_id=context.actor.id,
            command_type="QC_SUBMIT",
            idempotency_key=idempotency_key,
            subject_type="WorkOrder",
            subject_id=str(order.id),
            payload=payload,
            response=response,
        )
        return response
