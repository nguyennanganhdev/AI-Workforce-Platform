"""Checklist pinning and append-only item completion rules for a WorkOrder attempt."""

from copy import deepcopy
from datetime import datetime, timezone
from uuid import UUID

from pydantic import ValidationError

from ..concurrency import require_expected_version
from ..db.checklist import Checklist, ChecklistVersion
from ..db.task import Task, TaskDomainType
from ..db.work_order import WorkOrder, WorkOrderStatus
from .authority import FieldOperationsAuthority, FieldOperationsRole
from .checklist_schemas import (
    ChecklistCriteria,
    ChecklistExecutionRead,
    ChecklistItemCompletionRead,
    ChecklistVersionRead,
    _ChecklistExecutionState,
)
from .lifecycle import InvalidWorkOrderTransition


class InvalidChecklistContract(Exception):
    """Persisted checklist JSON does not satisfy the reviewed runtime contract."""


def cleaning_plan_requires_checklist(task: Task) -> bool:
    """The ERD's A5 CHECKLIST required-evidence code gates completion."""
    return (
        (
            task.domain_type in {TaskDomainType.SANITATION, TaskDomainType.LANDSCAPE}
            and isinstance(task.domain_data.get("requiredEvidence"), list)
            and "CHECKLIST" in task.domain_data["requiredEvidence"]
        )
        or (
            task.domain_type in {TaskDomainType.TECHNICAL, TaskDomainType.SECURITY}
            and task.domain_data.get("checklistRequired") is True
        )
    )


def parse_checklist_criteria(version: ChecklistVersion) -> ChecklistCriteria:
    try:
        return ChecklistCriteria.model_validate(version.criteria_json)
    except ValidationError as exc:
        raise InvalidChecklistContract("Published checklist criteria are invalid") from exc


def validate_checklist_category(task: Task, checklist: Checklist) -> None:
    if checklist.category != task.domain_type.value:
        raise InvalidChecklistContract(
            "Checklist category must match the Task domain type"
        )


def pin_checklist_version(
    work_order: WorkOrder,
    *,
    task: Task,
    checklist: Checklist,
    checklist_version: ChecklistVersion,
    checklist_version_id: UUID,
    expected_version: int,
    authority: FieldOperationsAuthority,
) -> None:
    require_expected_version(work_order.version, expected_version)
    if work_order.status != WorkOrderStatus.OPEN or work_order.executor_id is not None:
        raise InvalidWorkOrderTransition(
            "Checklist version can only be pinned to an unassigned OPEN WorkOrder"
        )
    if authority.actor_type != "user" or not authority.roles.intersection(
        {FieldOperationsRole.SUPERVISOR, FieldOperationsRole.BQL_COORDINATOR}
    ):
        raise PermissionError("Supervisor or BQL coordinator role required")
    if checklist_version.published_at is None or checklist_version.status != "PUBLISHED":
        raise InvalidChecklistContract("Only a published checklist version can be pinned")
    validate_checklist_category(task, checklist)
    parse_checklist_criteria(checklist_version)
    if work_order.checklist_version_id is not None:
        if work_order.checklist_version_id == checklist_version_id:
            return
        raise InvalidWorkOrderTransition(
            "A WorkOrder attempt cannot change its pinned checklist version"
        )
    work_order.checklist_version_id = checklist_version_id


def complete_checklist_item(
    work_order: WorkOrder,
    *,
    task: Task,
    checklist: Checklist,
    checklist_version: ChecklistVersion,
    item_id: str,
    expected_version: int,
    actor_id: str,
    authority: FieldOperationsAuthority,
    now: datetime | None = None,
) -> None:
    authority.require_execute(work_order)
    require_expected_version(work_order.version, expected_version)
    if work_order.status != WorkOrderStatus.IN_PROGRESS:
        raise InvalidWorkOrderTransition(
            "Checklist items can only be completed while a WorkOrder is IN_PROGRESS"
        )
    if work_order.checklist_version_id != checklist_version.id:
        raise InvalidChecklistContract("Checklist version does not match the pinned version")
    if checklist_version.published_at is None or checklist_version.status != "PUBLISHED":
        raise InvalidChecklistContract("Pinned checklist version is not published")
    validate_checklist_category(task, checklist)
    criteria = parse_checklist_criteria(checklist_version)
    if item_id not in {item.id for item in criteria.items}:
        raise InvalidChecklistContract("Checklist item does not exist in the pinned version")

    execution, state_invalid = _get_execution(work_order, checklist_version.id)
    if state_invalid:
        raise InvalidChecklistContract("Stored checklist execution data is invalid")
    if execution is not None and item_id in execution.completed_items:
        raise InvalidWorkOrderTransition("Checklist item is already complete")

    timestamp = now or datetime.now(timezone.utc)
    completion = ChecklistItemCompletionRead(
        itemId=item_id,
        completedAt=timestamp,
        completedBy=actor_id,
    )
    completed_items = dict(execution.completed_items) if execution is not None else {}
    completed_items[item_id] = completion
    next_execution = _ChecklistExecutionState(
        checklistVersionId=checklist_version.id,
        completedItems=completed_items,
    )
    next_result = deepcopy(work_order.result)
    next_result["checklistExecution"] = next_execution.model_dump(
        mode="json", by_alias=True
    )
    work_order.result = next_result


def checklist_execution_read(
    work_order: WorkOrder,
    *,
    task: Task,
    checklist: Checklist | None,
    checklist_version: ChecklistVersion | None,
) -> ChecklistExecutionRead:
    required_for_completion = cleaning_plan_requires_checklist(task)
    blockers: list[str] = []
    missing_required_item_ids: list[str] = []
    completed_items: list[ChecklistItemCompletionRead] = []
    checklist_read = None

    if checklist_version is None or checklist is None:
        if required_for_completion:
            blockers.append("CHECKLIST_VERSION_REQUIRED")
        return ChecklistExecutionRead(
            workOrderId=work_order.id,
            checklistVersionId=None,
            checklist=None,
            requiredForCompletion=required_for_completion,
            isComplete=False,
            canCompleteWorkOrder=not required_for_completion,
            completedItems=[],
            missingRequiredItemIds=[],
            blockers=blockers,
        )

    try:
        validate_checklist_category(task, checklist)
        criteria = parse_checklist_criteria(checklist_version)
    except InvalidChecklistContract:
        blockers.append("CHECKLIST_CONTRACT_INVALID")
        criteria = None

    if criteria is not None:
        execution, state_invalid = _get_execution(work_order, checklist_version.id)
        if execution is not None:
            known_item_ids = {item.id for item in criteria.items}
            if any(item_id not in known_item_ids for item_id in execution.completed_items):
                execution = None
                state_invalid = True
        if state_invalid:
            blockers.append("CHECKLIST_EXECUTION_DATA_INVALID")
        if execution is not None:
            completed_items = sorted(
                execution.completed_items.values(),
                key=lambda completion: completion.item_id,
            )
        completed_ids = set(execution.completed_items) if execution is not None else set()
        missing_required_item_ids = [
            item.id for item in criteria.items if item.required and item.id not in completed_ids
        ]
        checklist_read = ChecklistVersionRead(
            id=checklist_version.id,
            checklistId=checklist.id,
            code=checklist.code,
            name=checklist.name,
            category=checklist.category,
            versionNo=checklist_version.version_no,
            criteria=criteria,
        )
        is_complete = not missing_required_item_ids
        if required_for_completion and not is_complete:
            blockers.append("REQUIRED_CHECKLIST_ITEMS_INCOMPLETE")
    else:
        _, state_invalid = _get_execution(work_order, checklist_version.id)
        if state_invalid:
            blockers.append("CHECKLIST_EXECUTION_DATA_INVALID")
        is_complete = False

    return ChecklistExecutionRead(
        workOrderId=work_order.id,
        checklistVersionId=checklist_version.id,
        checklist=checklist_read,
        requiredForCompletion=required_for_completion,
        isComplete=is_complete,
        canCompleteWorkOrder=not blockers,
        completedItems=completed_items,
        missingRequiredItemIds=missing_required_item_ids,
        blockers=blockers,
    )


def _get_execution(
    work_order: WorkOrder, checklist_version_id: UUID
) -> tuple[_ChecklistExecutionState | None, bool]:
    raw = work_order.result.get("checklistExecution")
    if raw is None:
        return None, False
    try:
        state = _ChecklistExecutionState.model_validate(raw)
    except ValidationError:
        return None, True
    if state.checklist_version_id != checklist_version_id:
        return None, True
    return state, False
