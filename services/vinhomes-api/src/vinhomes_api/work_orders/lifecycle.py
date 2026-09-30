"""Guarded WorkOrder state changes. HTTP commands require Phase 2 permission binding."""

from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID

from ..concurrency import require_expected_version
from ..db.work_order import WorkOrder, WorkOrderStatus


class InvalidWorkOrderTransition(Exception):
    pass


class WorkOrderPermission(Protocol):
    """Implemented by a trusted permission adapter, never by request payload."""

    def require_assign(self, work_order: WorkOrder, executor_type: str, executor_id: UUID) -> None: ...

    def require_execute(self, work_order: WorkOrder) -> None: ...


def assign(
    work_order: WorkOrder,
    *,
    executor_type: str,
    executor_id: UUID,
    expected_version: int,
    permission: WorkOrderPermission,
) -> None:
    require_expected_version(work_order.version, expected_version)
    if work_order.status not in {WorkOrderStatus.OPEN, WorkOrderStatus.ASSIGNED}:
        raise InvalidWorkOrderTransition("Only an OPEN or not-yet-started ASSIGNED WorkOrder can be assigned")
    if work_order.status == WorkOrderStatus.ASSIGNED and work_order.execution_started_at is not None:
        raise InvalidWorkOrderTransition("An execution already started and cannot be reassigned")
    if work_order.executor_id == executor_id and work_order.executor_type == executor_type:
        raise InvalidWorkOrderTransition("WorkOrder is already assigned to this executor")
    permission.require_assign(work_order, executor_type, executor_id)
    work_order.executor_type = executor_type
    work_order.executor_id = executor_id
    work_order.status = WorkOrderStatus.ASSIGNED


def start(
    work_order: WorkOrder,
    *,
    expected_version: int,
    permission: WorkOrderPermission,
    now: datetime | None = None,
) -> None:
    require_expected_version(work_order.version, expected_version)
    if work_order.status != WorkOrderStatus.ASSIGNED or work_order.executor_id is None:
        raise InvalidWorkOrderTransition("Only an assigned WorkOrder can be started")
    permission.require_execute(work_order)
    work_order.execution_started_at = now or datetime.now(timezone.utc)
    work_order.status = WorkOrderStatus.IN_PROGRESS


def complete(
    work_order: WorkOrder,
    *,
    expected_version: int,
    permission: WorkOrderPermission,
    now: datetime | None = None,
) -> None:
    require_expected_version(work_order.version, expected_version)
    if work_order.status != WorkOrderStatus.IN_PROGRESS or work_order.execution_started_at is None:
        raise InvalidWorkOrderTransition("Only a started WorkOrder can be completed")
    permission.require_execute(work_order)
    work_order.execution_completed_at = now or datetime.now(timezone.utc)
    work_order.status = WorkOrderStatus.COMPLETED
