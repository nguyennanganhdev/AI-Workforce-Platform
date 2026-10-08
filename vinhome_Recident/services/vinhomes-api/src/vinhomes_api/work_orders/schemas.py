"""Read projection for execution attempts."""

from datetime import datetime, timezone
from math import ceil
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from typing import Annotated

from ..db.incident import Incident, IncidentStatus
from ..db.task import Task, TaskStatus
from ..db.work_order import WorkOrderStatus


class WorkOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    incident_id: UUID = Field(alias="incidentId")
    task_id: UUID = Field(alias="taskId")
    action_request_id: UUID = Field(alias="actionRequestId")
    executor_type: str = Field(alias="executorType")
    executor_id: UUID | None = Field(alias="executorId")
    status: WorkOrderStatus
    attempt_no: int = Field(alias="attemptNo")
    redo_of_work_order_id: UUID | None = Field(alias="redoOfWorkOrderId")
    checklist_version_id: UUID | None = Field(alias="checklistVersionId")
    execution_started_at: datetime | None = Field(alias="executionStartedAt")
    execution_completed_at: datetime | None = Field(alias="executionCompletedAt")
    result: dict[str, Any]
    version: int


_ExecutorType = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]


class AssignWorkOrderInput(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    executor_type: _ExecutorType = Field(alias="executorType")
    executor_id: UUID = Field(alias="executorId")
    expected_version: int = Field(alias="expectedVersion", ge=1)


class WorkOrderVersionCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    expected_version: int = Field(alias="expectedVersion", ge=1)


class WorkOrderAssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    work_order_id: UUID = Field(alias="workOrderId")
    work_order_version: int = Field(alias="workOrderVersion")
    executor_type: str = Field(alias="executorType")
    executor_id: UUID = Field(alias="executorId")
    assigned_by_type: str = Field(alias="assignedByType")
    assigned_by_id: str = Field(alias="assignedById")
    assigned_at: datetime = Field(alias="assignedAt")


class SupervisorWorkOrderRead(BaseModel):
    """Supervisor projection combining execution status and existing deadlines."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    work_order: WorkOrderRead = Field(alias="workOrder")
    task_status: TaskStatus = Field(alias="taskStatus")
    task_priority: str = Field(alias="taskPriority")
    task_due_at: datetime | None = Field(alias="taskDueAt")
    task_remaining_seconds: int | None = Field(alias="taskRemainingSeconds")
    task_overdue: bool = Field(alias="taskOverdue")
    incident_status: IncidentStatus = Field(alias="incidentStatus")
    incident_severity: str = Field(alias="incidentSeverity")
    incident_sla_due_at: datetime | None = Field(alias="incidentSlaDueAt")
    incident_sla_remaining_seconds: int | None = Field(alias="incidentSlaRemainingSeconds")
    incident_sla_overdue: bool = Field(alias="incidentSlaOverdue")


class SupervisorWorkOrderPage(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    items: list[SupervisorWorkOrderRead]
    total: int
    limit: int
    offset: int


class WorkOrderPage(BaseModel):
    """Paginated WorkOrders assigned to the authenticated field executor."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    items: list[WorkOrderRead]
    total: int
    limit: int
    offset: int


def _remaining_seconds(due_at: datetime | None, now: datetime) -> int | None:
    if due_at is None:
        return None
    normalized_due = (
        due_at.replace(tzinfo=timezone.utc)
        if due_at.tzinfo is None
        else due_at.astimezone(timezone.utc)
    )
    return ceil((normalized_due - now.astimezone(timezone.utc)).total_seconds())


def supervisor_work_order_read(
    work_order,
    task: Task,
    incident: Incident,
    *,
    now: datetime,
) -> SupervisorWorkOrderRead:
    task_due_at = task.due_at
    incident_sla_due_at = incident.sla_due_at
    return SupervisorWorkOrderRead(
        workOrder=WorkOrderRead.model_validate(work_order),
        taskStatus=task.status,
        taskPriority=task.priority,
        taskDueAt=task_due_at,
        taskRemainingSeconds=_remaining_seconds(task_due_at, now),
        taskOverdue=(
            task_due_at is not None
            and task.status not in {TaskStatus.DONE, TaskStatus.CANCELLED}
            and _remaining_seconds(task_due_at, now) <= 0
        ),
        incidentStatus=incident.status,
        incidentSeverity=incident.severity,
        incidentSlaDueAt=incident_sla_due_at,
        incidentSlaRemainingSeconds=_remaining_seconds(incident_sla_due_at, now),
        incidentSlaOverdue=(
            incident_sla_due_at is not None
            and _remaining_seconds(incident_sla_due_at, now) <= 0
        ),
    )
