"""Create immutable next attempts after an explicit QC redo decision."""

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.action_request import ActionRequest
from ..db.qc_result import QCOutcome, QCResult
from ..db.task import Task
from ..db.work_order import WorkOrder, WorkOrderStatus
from ..tasks.repository import TaskRepository
from .a5_execution import InvalidA5Execution, pin_redo_a5_execution_plan
from .checklist_execution import (
    InvalidChecklistContract,
    parse_checklist_criteria,
    validate_checklist_category,
)
from .checklist_repository import ChecklistRepository
from .repository import WorkOrderRepository


class InvalidRedoRequest(Exception):
    """The failed attempt is not eligible to produce another attempt."""


async def create_redo_work_order(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    failed_work_order: WorkOrder,
    qc_result: QCResult,
) -> WorkOrder:
    """Append an unassigned OPEN attempt while preserving its predecessor.

    The same Task, authorized ActionRequest, executor type, and published
    checklist version are reused. Execution result/evidence/measurements are
    attempt-scoped and therefore start empty. A supervisor assigns the new
    attempt through the existing permission-checked assignment route.
    """
    if (
        failed_work_order.status is not WorkOrderStatus.COMPLETED
        or qc_result.work_order_id != failed_work_order.id
        or qc_result.outcome is not QCOutcome.FAIL
        or not qc_result.redo_required
    ):
        raise InvalidRedoRequest("Only QC FAIL with redo_required can create a redo attempt")

    tasks = TaskRepository(session)
    task: Task | None = await tasks.get_by_id_for_update(
        tenant_id=tenant_id,
        task_id=failed_work_order.task_id,
    )
    if task is None or task.incident_id != failed_work_order.incident_id:
        raise InvalidRedoRequest("WorkOrder Task is not available in the same tenant and Incident")

    action_request = await session.get(ActionRequest, failed_work_order.action_request_id)
    if (
        action_request is None
        or action_request.task_id != task.id
        or action_request.incident_id != task.incident_id
    ):
        raise InvalidRedoRequest("The original ActionRequest is not bound to this Task and Incident")

    attempts = await WorkOrderRepository(session).list_attempts(
        tenant_id=tenant_id,
        task_id=task.id,
    )
    if (
        not attempts
        or attempts[-1].id != failed_work_order.id
        or attempts[-1].attempt_no != failed_work_order.attempt_no
    ):
        raise InvalidRedoRequest("Redo can only be created from the latest WorkOrder attempt")

    if failed_work_order.checklist_version_id is not None:
        pair = await ChecklistRepository(session).get_version_for_tenant(
            tenant_id=tenant_id,
            checklist_version_id=failed_work_order.checklist_version_id,
        )
        if pair is None:
            raise InvalidRedoRequest("Pinned checklist version is unavailable in this tenant")
        checklist, checklist_version = pair
        try:
            validate_checklist_category(task, checklist)
            parse_checklist_criteria(checklist_version)
        except InvalidChecklistContract as exc:
            raise InvalidRedoRequest("Pinned checklist contract is invalid for this Task") from exc
        if checklist_version.status != "PUBLISHED" or checklist_version.published_at is None:
            raise InvalidRedoRequest("Only the original published checklist version can be reused")

    redo = WorkOrder(
        id=uuid4(),
        incident_id=failed_work_order.incident_id,
        task_id=failed_work_order.task_id,
        action_request_id=failed_work_order.action_request_id,
        executor_type=failed_work_order.executor_type,
        executor_id=None,
        status=WorkOrderStatus.OPEN,
        attempt_no=failed_work_order.attempt_no + 1,
        redo_of_work_order_id=failed_work_order.id,
        checklist_version_id=failed_work_order.checklist_version_id,
        result={},
    )
    try:
        pin_redo_a5_execution_plan(redo, failed_work_order, task)
    except InvalidA5Execution as exc:
        raise InvalidRedoRequest(str(exc)) from exc
    session.add(redo)
    await session.flush()
    return redo
