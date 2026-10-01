"""Mockable, attempt-local Field Operations execution state.

The state is intentionally stored inside WorkOrder.result until the shared
contract adds normalized pause, arrival, blocker and support tables.
"""

from copy import deepcopy
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError
from typing import Annotated

from ..db.work_order import WorkOrder


_Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=512)]


class PauseRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    paused_at: datetime = Field(alias="pausedAt")
    paused_by: str = Field(alias="pausedBy")
    reason: _Reason
    resumed_at: datetime | None = Field(default=None, alias="resumedAt")
    resumed_by: str | None = Field(default=None, alias="resumedBy")


class ArrivalRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    checked_in_at: datetime = Field(alias="checkedInAt")
    checked_in_by: str = Field(alias="checkedInBy")
    checked_out_at: datetime | None = Field(default=None, alias="checkedOutAt")
    checked_out_by: str | None = Field(default=None, alias="checkedOutBy")


class ArrivalPlanRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    planned_start_at: datetime = Field(alias="plannedStartAt")
    planned_end_at: datetime = Field(alias="plannedEndAt")
    planned_by: str = Field(alias="plannedBy")
    planned_at: datetime = Field(alias="plannedAt")


class BlockerRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    code: str
    note: str | None = None
    status: Literal["OPEN", "RESOLVED"]
    reported_at: datetime = Field(alias="reportedAt")
    reported_by: str = Field(alias="reportedBy")
    resolved_at: datetime | None = Field(default=None, alias="resolvedAt")
    resolved_by: str | None = Field(default=None, alias="resolvedBy")


class SupportRequestRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: UUID = Field(default_factory=uuid4)
    support_type: Literal["TECHNICAL", "MEDICAL", "FIRE_SAFETY", "MANAGEMENT", "OTHER"] = Field(alias="supportType")
    note: str | None = None
    status: Literal["OPEN", "ACKNOWLEDGED", "RESOLVED"] = "OPEN"
    requested_at: datetime = Field(alias="requestedAt")
    requested_by: str = Field(alias="requestedBy")


class ContractorResponseRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    status: Literal["PENDING", "ACCEPTED", "REJECTED"]
    responded_at: datetime | None = Field(default=None, alias="respondedAt")
    responded_by: str | None = Field(default=None, alias="respondedBy")
    reason: str | None = None


class EscalationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    target: Literal["BQL_COORDINATOR"] = "BQL_COORDINATOR"
    urgency: Literal["NORMAL", "HIGH", "URGENT"]
    reason: str
    escalated_at: datetime = Field(alias="escalatedAt")
    escalated_by: str = Field(alias="escalatedBy")


class SecurityIncidentReportRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: UUID = Field(default_factory=uuid4)
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    summary: str
    people_refs: list[str] = Field(alias="peopleRefs", default_factory=list)
    vehicle_refs: list[str] = Field(alias="vehicleRefs", default_factory=list)
    asset_refs: list[str] = Field(alias="assetRefs", default_factory=list)
    reported_at: datetime = Field(alias="reportedAt")
    reported_by: str = Field(alias="reportedBy")


class SecurityAreaActionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    area_id: str = Field(alias="areaId")
    action: Literal["SECURE", "RELEASE"]
    note: str | None = None
    recorded_at: datetime = Field(alias="recordedAt")
    recorded_by: str = Field(alias="recordedBy")


class HandoverRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    recipient: str
    note: str
    handed_over_at: datetime = Field(alias="handedOverAt")
    handed_over_by: str = Field(alias="handedOverBy")


class FieldOperationsState(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: Literal[1] = Field(default=1, alias="schemaVersion")
    execution_state: Literal["NOT_STARTED", "ACTIVE", "PAUSED", "COMPLETED"] = Field(
        default="NOT_STARTED", alias="executionState"
    )
    arrival: ArrivalRecord | None = None
    arrival_plan: ArrivalPlanRecord | None = Field(default=None, alias="arrivalPlan")
    pauses: list[PauseRecord] = Field(default_factory=list)
    blocker: BlockerRecord | None = None
    support_requests: list[SupportRequestRecord] = Field(default_factory=list, alias="supportRequests")
    contractor_response: ContractorResponseRecord | None = Field(default=None, alias="contractorResponse")
    escalations: list[EscalationRecord] = Field(default_factory=list)
    security_reports: list[SecurityIncidentReportRecord] = Field(default_factory=list, alias="securityReports")
    security_area_actions: list[SecurityAreaActionRecord] = Field(default_factory=list, alias="securityAreaActions")
    handovers: list[HandoverRecord] = Field(default_factory=list)


class InvalidFieldOperationsState(Exception):
    pass


def read_field_operations_state(work_order: WorkOrder) -> FieldOperationsState:
    raw = work_order.result.get("fieldOperations")
    if raw is None:
        execution_state = "ACTIVE" if work_order.execution_started_at else "NOT_STARTED"
        if work_order.status.value == "COMPLETED":
            execution_state = "COMPLETED"
        return FieldOperationsState(executionState=execution_state)
    try:
        state = FieldOperationsState.model_validate(raw)
        if state.execution_state == "NOT_STARTED" and work_order.execution_started_at is not None:
            state.execution_state = "ACTIVE"
        if work_order.status.value == "COMPLETED":
            state.execution_state = "COMPLETED"
        return state
    except ValidationError as exc:
        raise InvalidFieldOperationsState("Stored Field Operations state is invalid") from exc


def write_field_operations_state(work_order: WorkOrder, state: FieldOperationsState) -> None:
    updated_result = deepcopy(work_order.result)
    updated_result["fieldOperations"] = state.model_dump(mode="json", by_alias=True)
    work_order.result = updated_result


def require_active_execution(work_order: WorkOrder) -> FieldOperationsState:
    state = read_field_operations_state(work_order)
    if state.execution_state == "PAUSED":
        raise InvalidFieldOperationsState("Execution is paused; resume before continuing")
    if state.blocker is not None and state.blocker.status == "OPEN":
        raise InvalidFieldOperationsState("Execution is blocked; supervisor must resolve the blocker")
    return state


def pause_execution(work_order: WorkOrder, *, actor_id: str, reason: str, now=None) -> FieldOperationsState:
    state = read_field_operations_state(work_order)
    if work_order.status.value != "IN_PROGRESS" or state.execution_state != "ACTIVE":
        raise InvalidFieldOperationsState("Only active IN_PROGRESS execution can be paused")
    state.pauses.append(PauseRecord(pausedAt=now or datetime.now(timezone.utc), pausedBy=actor_id, reason=reason))
    state.execution_state = "PAUSED"
    write_field_operations_state(work_order, state)
    return state


def resume_execution(work_order: WorkOrder, *, actor_id: str, now=None) -> FieldOperationsState:
    state = read_field_operations_state(work_order)
    if work_order.status.value != "IN_PROGRESS" or state.execution_state != "PAUSED" or not state.pauses:
        raise InvalidFieldOperationsState("Only paused IN_PROGRESS execution can be resumed")
    previous_pause = state.pauses[-1]
    if previous_pause.resumed_at is not None:
        raise InvalidFieldOperationsState("Latest pause is already resumed")
    state.pauses[-1] = previous_pause.model_copy(
        update={"resumed_at": now or datetime.now(timezone.utc), "resumed_by": actor_id}
    )
    state.execution_state = "ACTIVE"
    write_field_operations_state(work_order, state)
    return state


def check_in(work_order: WorkOrder, *, actor_id: str, now=None) -> FieldOperationsState:
    if work_order.status.value != "ASSIGNED":
        raise InvalidFieldOperationsState("Arrival check-in is only allowed for an ASSIGNED WorkOrder")
    state = read_field_operations_state(work_order)
    if state.arrival is not None:
        raise InvalidFieldOperationsState("WorkOrder already has an arrival check-in")
    state.arrival = ArrivalRecord(checkedInAt=now or datetime.now(timezone.utc), checkedInBy=actor_id)
    write_field_operations_state(work_order, state)
    return state


def plan_arrival(
    work_order: WorkOrder,
    *,
    actor_id: str,
    planned_start_at: datetime,
    planned_end_at: datetime,
    now=None,
) -> FieldOperationsState:
    state = read_field_operations_state(work_order)
    if work_order.status.value != "ASSIGNED" or work_order.executor_type != "CONTRACTOR":
        raise InvalidFieldOperationsState("Arrival planning requires an ASSIGNED contractor WorkOrder")
    if state.arrival is not None:
        raise InvalidFieldOperationsState("Arrival plan cannot change after check-in")
    if planned_start_at.utcoffset() is None or planned_end_at.utcoffset() is None:
        raise InvalidFieldOperationsState("Arrival plan timestamps must include a timezone")
    if planned_start_at >= planned_end_at:
        raise InvalidFieldOperationsState("Arrival plan end must be after its start")
    state.arrival_plan = ArrivalPlanRecord(
        plannedStartAt=planned_start_at,
        plannedEndAt=planned_end_at,
        plannedBy=actor_id,
        plannedAt=now or datetime.now(timezone.utc),
    )
    write_field_operations_state(work_order, state)
    return state


def report_blocker(
    work_order: WorkOrder,
    *,
    actor_id: str,
    code: str,
    note: str | None,
    now=None,
) -> FieldOperationsState:
    state = require_active_execution(work_order)
    if work_order.status.value != "IN_PROGRESS":
        raise InvalidFieldOperationsState("A blocker can only be reported for IN_PROGRESS execution")
    if state.blocker is not None and state.blocker.status == "OPEN":
        raise InvalidFieldOperationsState("Resolve the current blocker before reporting another")
    state.blocker = BlockerRecord(
        code=code,
        note=note,
        status="OPEN",
        reportedAt=now or datetime.now(timezone.utc),
        reportedBy=actor_id,
    )
    write_field_operations_state(work_order, state)
    return state


def resolve_blocker(work_order: WorkOrder, *, actor_id: str, now=None) -> FieldOperationsState:
    state = read_field_operations_state(work_order)
    if state.blocker is None or state.blocker.status != "OPEN":
        raise InvalidFieldOperationsState("WorkOrder has no open blocker")
    state.blocker = state.blocker.model_copy(
        update={"status": "RESOLVED", "resolved_at": now or datetime.now(timezone.utc), "resolved_by": actor_id}
    )
    write_field_operations_state(work_order, state)
    return state


def request_support(
    work_order: WorkOrder,
    *,
    actor_id: str,
    support_type: str,
    note: str | None,
    now=None,
) -> SupportRequestRecord:
    state = read_field_operations_state(work_order)
    if state.execution_state == "PAUSED":
        raise InvalidFieldOperationsState("Resume execution before requesting support")
    if work_order.status.value != "IN_PROGRESS":
        raise InvalidFieldOperationsState("Support can only be requested during IN_PROGRESS execution")
    record = SupportRequestRecord(
        supportType=support_type,
        note=note,
        requestedAt=now or datetime.now(timezone.utc),
        requestedBy=actor_id,
    )
    state.support_requests.append(record)
    write_field_operations_state(work_order, state)
    return record


def reset_contractor_response(work_order: WorkOrder) -> FieldOperationsState:
    state = read_field_operations_state(work_order)
    state.contractor_response = (
        ContractorResponseRecord(status="PENDING")
        if work_order.executor_type == "CONTRACTOR"
        else None
    )
    write_field_operations_state(work_order, state)
    return state


def respond_to_contractor_work(
    work_order: WorkOrder,
    *,
    actor_id: str,
    decision: Literal["ACCEPTED", "REJECTED"],
    reason: str | None,
    now=None,
) -> FieldOperationsState:
    state = read_field_operations_state(work_order)
    if work_order.executor_type != "CONTRACTOR" or state.contractor_response is None:
        raise InvalidFieldOperationsState("WorkOrder has no pending contractor response")
    if state.contractor_response.status != "PENDING":
        raise InvalidFieldOperationsState("Contractor has already responded to this assignment")
    if decision == "REJECTED" and not reason:
        raise InvalidFieldOperationsState("A rejection reason is required")
    state.contractor_response = ContractorResponseRecord(
        status=decision,
        respondedAt=now or datetime.now(timezone.utc),
        respondedBy=actor_id,
        reason=reason,
    )
    write_field_operations_state(work_order, state)
    return state


def escalate_work_order(
    work_order: WorkOrder,
    *,
    actor_id: str,
    urgency: Literal["NORMAL", "HIGH", "URGENT"],
    reason: str,
    now=None,
) -> FieldOperationsState:
    state = read_field_operations_state(work_order)
    if work_order.status.value in {"COMPLETED", "CANCELLED", "FAILED"}:
        raise InvalidFieldOperationsState("A terminal WorkOrder cannot be escalated")
    state.escalations.append(
        EscalationRecord(
            urgency=urgency,
            reason=reason,
            escalatedAt=now or datetime.now(timezone.utc),
            escalatedBy=actor_id,
        )
    )
    write_field_operations_state(work_order, state)
    return state


def check_out(work_order: WorkOrder, *, actor_id: str, now=None) -> FieldOperationsState:
    state = require_active_execution(work_order)
    if work_order.status.value != "IN_PROGRESS" or state.arrival is None:
        raise InvalidFieldOperationsState("Security check-out requires an active checked-in WorkOrder")
    if state.arrival.checked_out_at is not None:
        raise InvalidFieldOperationsState("WorkOrder already has a security check-out")
    state.arrival = state.arrival.model_copy(
        update={"checked_out_at": now or datetime.now(timezone.utc), "checked_out_by": actor_id}
    )
    write_field_operations_state(work_order, state)
    return state


def add_security_report(
    work_order: WorkOrder,
    *,
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"],
    summary: str,
    people_refs: list[str],
    vehicle_refs: list[str],
    asset_refs: list[str],
    actor_id: str,
    now=None,
) -> FieldOperationsState:
    state = require_active_execution(work_order)
    if work_order.status.value != "IN_PROGRESS" or state.arrival is None:
        raise InvalidFieldOperationsState("A security report requires a checked-in IN_PROGRESS patrol")
    state.security_reports.append(
        SecurityIncidentReportRecord(
            severity=severity,
            summary=summary,
            peopleRefs=people_refs,
            vehicleRefs=vehicle_refs,
            assetRefs=asset_refs,
            reportedAt=now or datetime.now(timezone.utc),
            reportedBy=actor_id,
        )
    )
    write_field_operations_state(work_order, state)
    return state


def record_security_area_action(
    work_order: WorkOrder,
    *,
    area_id: str,
    action: Literal["SECURE", "RELEASE"],
    note: str | None,
    actor_id: str,
    now=None,
) -> FieldOperationsState:
    state = require_active_execution(work_order)
    if work_order.status.value != "IN_PROGRESS" or state.arrival is None:
        raise InvalidFieldOperationsState("Area actions require a checked-in IN_PROGRESS patrol")
    state.security_area_actions.append(
        SecurityAreaActionRecord(
            areaId=area_id,
            action=action,
            note=note,
            recordedAt=now or datetime.now(timezone.utc),
            recordedBy=actor_id,
        )
    )
    write_field_operations_state(work_order, state)
    return state


def record_handover(
    work_order: WorkOrder,
    *,
    recipient: str,
    note: str,
    actor_id: str,
    now=None,
) -> FieldOperationsState:
    state = read_field_operations_state(work_order)
    if work_order.status.value != "IN_PROGRESS":
        raise InvalidFieldOperationsState("Handover must be recorded while the WorkOrder is IN_PROGRESS")
    state.handovers.append(
        HandoverRecord(
            recipient=recipient,
            note=note,
            handedOverAt=now or datetime.now(timezone.utc),
            handedOverBy=actor_id,
        )
    )
    write_field_operations_state(work_order, state)
    return state
