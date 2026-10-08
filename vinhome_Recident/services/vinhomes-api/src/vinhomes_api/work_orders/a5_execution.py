"""Attempt-pinned A5 CleaningPlan execution data."""

from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Literal
from uuid import UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field, StrictBool, ValidationError

from ..concurrency import require_expected_version
from ..db.task import Task, TaskDomainType
from ..db.work_order import WorkOrder, WorkOrderStatus
from ..tasks.schemas import CleaningPlan
from .a5_execution_schemas import A5ActionExecutionRead, A5ExecutionRead
from .authority import FieldOperationsAuthority


class InvalidA5Execution(Exception):
    """The A5 plan or its persisted attempt execution data is invalid."""


class _ActionSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: UUID
    action_type: str = Field(alias="type")
    executor_type: str = Field(alias="executorType")


class _PlanSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: Literal[1] = Field(alias="schemaVersion")
    issue_type: str = Field(alias="issueType")
    area: dict[str, str]
    actions: list[_ActionSnapshot]
    required_evidence: list[str] = Field(alias="requiredEvidence")
    qc_criteria: list[str] = Field(alias="qcCriteria")
    root_cause_check_required: StrictBool = Field(alias="rootCauseCheckRequired")


class _ActionCompletion(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    action_id: UUID = Field(alias="actionId")
    completed_at: datetime = Field(alias="completedAt")
    completed_by: str = Field(alias="completedBy")


class _ExecutionState(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: Literal[1] = Field(alias="schemaVersion")
    domain_type: TaskDomainType = Field(alias="domainType")
    domain_schema_version: int = Field(alias="domainSchemaVersion", ge=1)
    plan_snapshot: _PlanSnapshot = Field(alias="planSnapshot")
    completed_actions: dict[str, _ActionCompletion] = Field(
        alias="completedActions", default_factory=dict
    )


def _new_execution_state(work_order: WorkOrder, task: Task) -> _ExecutionState:
    if task.domain_type not in {TaskDomainType.SANITATION, TaskDomainType.LANDSCAPE}:
        raise InvalidA5Execution("A5 execution requires a SANITATION or LANDSCAPE Task")
    try:
        plan = CleaningPlan.model_validate(task.domain_data)
    except ValidationError as exc:
        raise InvalidA5Execution("CleaningPlan does not match the supported schema") from exc
    if task.domain_schema_version != plan.schema_version:
        raise InvalidA5Execution("Task domain schema version does not match CleaningPlan")

    actions = [
        _ActionSnapshot(
            id=uuid5(work_order.id, f"a5-cleaning-action-v1:{index}"),
            type=action.action_type,
            executorType=action.executor_type,
        )
        for index, action in enumerate(plan.actions, start=1)
    ]
    snapshot = _PlanSnapshot(
        schemaVersion=plan.schema_version,
        issueType=plan.issue_type,
        area=plan.area.model_dump(mode="json", by_alias=True),
        actions=actions,
        requiredEvidence=plan.required_evidence,
        qcCriteria=plan.qc_criteria,
        rootCauseCheckRequired=plan.root_cause_check_required,
    )
    return _ExecutionState(
        schemaVersion=1,
        domainType=task.domain_type,
        domainSchemaVersion=task.domain_schema_version,
        planSnapshot=snapshot,
    )


def pin_a5_execution_plan(work_order: WorkOrder, task: Task) -> None:
    """Pin validated A5 plan/action identifiers when the attempt starts."""
    if "a5Execution" in work_order.result:
        raise InvalidA5Execution("A5 execution plan is already pinned for this attempt")
    state = _new_execution_state(work_order, task)
    result = deepcopy(work_order.result)
    result["a5Execution"] = state.model_dump(mode="json", by_alias=True)
    work_order.result = result


def pin_redo_a5_execution_plan(
    work_order: WorkOrder,
    previous_work_order: WorkOrder,
    task: Task,
) -> None:
    """Pin the same A5 plan to a redo attempt with fresh action identifiers.

    A redo repeats the authorized plan from the failed attempt. Completion
    records are not copied, and action IDs are regenerated for the new attempt.
    """
    if task.domain_type not in {TaskDomainType.SANITATION, TaskDomainType.LANDSCAPE}:
        return
    if "a5Execution" in work_order.result:
        raise InvalidA5Execution("A5 execution plan is already pinned for this redo attempt")

    previous_state = _execution_state(
        previous_work_order,
        task,
        allow_unstarted_projection=False,
    )
    actions = [
        _ActionSnapshot(
            id=uuid5(work_order.id, f"a5-cleaning-action-v1:{index}"),
            type=action.action_type,
            executorType=action.executor_type,
        )
        for index, action in enumerate(previous_state.plan_snapshot.actions, start=1)
    ]
    snapshot = previous_state.plan_snapshot.model_copy(update={"actions": actions})
    next_state = _ExecutionState(
        schemaVersion=previous_state.schema_version,
        domainType=previous_state.domain_type,
        domainSchemaVersion=previous_state.domain_schema_version,
        planSnapshot=snapshot,
        completedActions={},
    )
    result = deepcopy(work_order.result)
    result["a5Execution"] = next_state.model_dump(mode="json", by_alias=True)
    work_order.result = result


def validate_pinned_a5_execution_plan(work_order: WorkOrder, task: Task) -> None:
    """Validate a redo's pre-pinned plan when its executor starts the attempt."""
    _execution_state(work_order, task, allow_unstarted_projection=False)


def _execution_state(
    work_order: WorkOrder,
    task: Task,
    *,
    allow_unstarted_projection: bool,
) -> _ExecutionState:
    raw = work_order.result.get("a5Execution")
    if raw is None:
        if allow_unstarted_projection and work_order.status in {
            WorkOrderStatus.OPEN,
            WorkOrderStatus.ASSIGNED,
        }:
            return _new_execution_state(work_order, task)
        raise InvalidA5Execution("A5 execution plan was not pinned when this attempt started")
    try:
        state = _ExecutionState.model_validate(raw)
    except ValidationError as exc:
        raise InvalidA5Execution("Stored A5 execution data is invalid") from exc

    if state.domain_type != task.domain_type:
        raise InvalidA5Execution("Stored A5 plan domain does not match its Task")
    action_ids = {str(action.id) for action in state.plan_snapshot.actions}
    if len(action_ids) != len(state.plan_snapshot.actions):
        raise InvalidA5Execution("Stored A5 action identifiers are not unique")
    for action_id, completion in state.completed_actions.items():
        try:
            valid_reference = action_id in action_ids and completion.action_id == UUID(action_id)
        except ValueError:
            valid_reference = False
        if not valid_reference:
            raise InvalidA5Execution("Stored A5 completion references an unknown action")
    return state


def complete_a5_action(
    work_order: WorkOrder,
    task: Task,
    *,
    action_id: UUID,
    expected_version: int,
    actor_id: str,
    authority: FieldOperationsAuthority,
    now: datetime | None = None,
) -> None:
    require_expected_version(work_order.version, expected_version)
    authority.require_execute(work_order)
    if work_order.status is not WorkOrderStatus.IN_PROGRESS:
        raise InvalidA5Execution("A5 actions can only be completed while IN_PROGRESS")
    state = _execution_state(work_order, task, allow_unstarted_projection=False)
    action = next(
        (item for item in state.plan_snapshot.actions if item.id == action_id),
        None,
    )
    if action is None:
        raise InvalidA5Execution("Action does not belong to the pinned CleaningPlan")
    if action.executor_type != work_order.executor_type:
        raise InvalidA5Execution("Action executorType does not match the assigned WorkOrder executor")
    key = str(action_id)
    if key in state.completed_actions:
        raise InvalidA5Execution("CleaningPlan action is already complete")

    state.completed_actions[key] = _ActionCompletion(
        actionId=action_id,
        completedAt=now or datetime.now(timezone.utc),
        completedBy=actor_id,
    )
    result = deepcopy(work_order.result)
    result["a5Execution"] = state.model_dump(mode="json", by_alias=True)
    work_order.result = result


def a5_execution_read(
    work_order: WorkOrder,
    task: Task,
    *,
    satisfied_required_evidence: list[str],
    missing_required_evidence: list[str],
    unsupported_required_evidence: list[str],
    evidence_blockers: list[str],
) -> A5ExecutionRead:
    state = _execution_state(work_order, task, allow_unstarted_projection=True)
    completed = state.completed_actions
    actions = [
        A5ActionExecutionRead(
            id=action.id,
            type=action.action_type,
            executorType=action.executor_type,
            completed=str(action.id) in completed,
            completedAt=(
                completed[str(action.id)].completed_at
                if str(action.id) in completed
                else None
            ),
            completedBy=(
                completed[str(action.id)].completed_by
                if str(action.id) in completed
                else None
            ),
        )
        for action in state.plan_snapshot.actions
    ]
    blockers = [
        f"A5_ACTION_INCOMPLETE:{action.id}"
        for action in actions
        if not action.completed
    ]
    blockers.extend(
        f"A5_ACTION_EXECUTOR_MISMATCH:{action.id}"
        for action, definition in zip(actions, state.plan_snapshot.actions, strict=True)
        if definition.executor_type != work_order.executor_type
    )
    blockers.extend(evidence_blockers)
    blockers = list(dict.fromkeys(blockers))
    return A5ExecutionRead(
        workOrderId=work_order.id,
        taskId=task.id,
        domainType=state.domain_type,
        domainSchemaVersion=state.domain_schema_version,
        workOrderVersion=work_order.version,
        issueType=state.plan_snapshot.issue_type,
        area=state.plan_snapshot.area,
        actions=actions,
        requiredEvidence=state.plan_snapshot.required_evidence,
        satisfiedRequiredEvidence=satisfied_required_evidence,
        missingRequiredEvidence=missing_required_evidence,
        unsupportedRequiredEvidence=unsupported_required_evidence,
        qcCriteria=state.plan_snapshot.qc_criteria,
        rootCauseCheckRequired=state.plan_snapshot.root_cause_check_required,
        canCompleteWorkOrder=not blockers,
        blockers=blockers,
    )


def a5_task_projection(work_order: WorkOrder, task: Task):
    """Expose the attempt-pinned plan to checklist/evidence prerequisite readers."""
    state = _execution_state(work_order, task, allow_unstarted_projection=True)
    plan_data = state.plan_snapshot.model_dump(mode="json", by_alias=True)
    return SimpleNamespace(
        id=task.id,
        domain_type=state.domain_type,
        domain_schema_version=state.domain_schema_version,
        domain_data=plan_data,
    )


def task_for_execution(work_order: WorkOrder, task: Task):
    """Use the pinned CleaningPlan wherever generic checklist/evidence guards read it."""
    if task.domain_type in {TaskDomainType.SANITATION, TaskDomainType.LANDSCAPE}:
        return a5_task_projection(work_order, task)
    return task
