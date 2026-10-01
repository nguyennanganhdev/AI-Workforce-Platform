"""Read and command contracts for independent WorkOrder QC."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StringConstraints, model_validator

from ..db.incident import Incident
from ..db.qc_result import QCOutcome, QCResult
from ..db.task import Task, TaskDomainType
from ..db.work_order import WorkOrder
from ..evidence.schemas import EvidenceRefRead, WorkOrderEvidenceRead
from ..work_orders.a5_execution_schemas import A5ExecutionRead
from ..work_orders.execution_details_schemas import ExecutionDetailsRead
from ..work_orders.schemas import WorkOrderRead


_QCCode = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
_QCNote = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class SubmitQCInput(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    outcome: QCOutcome
    expected_version: int = Field(alias="expectedVersion", ge=1, strict=True)
    failed_criteria: list[_QCCode] = Field(alias="failedCriteria", max_length=500)
    redo_required: StrictBool = Field(alias="redoRequired")
    note: _QCNote | None = None
    evidence_ref_ids: list[UUID] = Field(default_factory=list, alias="evidenceRefIds", max_length=100)

    @model_validator(mode="after")
    def request_lists_must_be_unique(self) -> "SubmitQCInput":
        if len(self.failed_criteria) != len(set(self.failed_criteria)):
            raise ValueError("failedCriteria must not contain duplicates")
        if len(self.evidence_ref_ids) != len(set(self.evidence_ref_ids)):
            raise ValueError("evidenceRefIds must not contain duplicates")
        if self.redo_required and self.outcome is not QCOutcome.FAIL:
            raise ValueError("redoRequired is only valid for a FAIL outcome")
        if self.outcome is QCOutcome.PASS and self.failed_criteria:
            raise ValueError("PASS cannot include failedCriteria")
        if self.outcome is QCOutcome.FAIL and not self.failed_criteria:
            raise ValueError("FAIL requires at least one failed criterion")
        return self


class QCQueueItem(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    work_order: WorkOrderRead = Field(alias="workOrder")
    incident_id: UUID = Field(alias="incidentId")
    incident_title: str = Field(alias="incidentTitle")
    incident_severity: str = Field(alias="incidentSeverity")
    task_title: str = Field(alias="taskTitle")
    domain_type: TaskDomainType = Field(alias="domainType")


class QCQueuePage(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    items: list[QCQueueItem]
    total: int
    limit: int
    offset: int


class QCResultRead(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: UUID
    work_order_id: UUID = Field(alias="workOrderId")
    outcome: QCOutcome
    criteria: list[str]
    failed_criteria: list[str] = Field(alias="failedCriteria")
    redo_required: bool = Field(alias="redoRequired")
    note: str | None
    checked_by: str = Field(alias="checkedBy")
    checked_at: datetime = Field(alias="checkedAt")
    evidence: list[EvidenceRefRead]


class QCSubmissionRead(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    result: QCResultRead
    redo_work_order: WorkOrderRead | None = Field(alias="redoWorkOrder")


class QCWorkOrderDetail(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    work_order: WorkOrderRead = Field(alias="workOrder")
    a5_execution: A5ExecutionRead | None = Field(alias="a5Execution")
    qc_criteria: list[str] | None = Field(alias="qcCriteria")
    execution_details: ExecutionDetailsRead = Field(alias="executionDetails")
    evidence: WorkOrderEvidenceRead
    qc_results: list[QCResultRead] = Field(alias="qcResults")
    can_submit_qc: bool = Field(alias="canSubmitQC")
    blockers: list[str]


def queue_item_read(work_order: WorkOrder, task: Task, incident: Incident) -> QCQueueItem:
    return QCQueueItem(
        workOrder=WorkOrderRead.model_validate(work_order),
        incidentId=incident.id,
        incidentTitle=incident.title,
        incidentSeverity=incident.severity,
        taskTitle=task.title,
        domainType=task.domain_type,
    )


def qc_result_read(
    result: QCResult,
    *,
    evidence: list[EvidenceRefRead],
) -> QCResultRead:
    return QCResultRead(
        id=result.id,
        workOrderId=result.work_order_id,
        outcome=result.outcome,
        criteria=result.criteria_json,
        failedCriteria=result.failed_criteria_json,
        redoRequired=result.redo_required,
        note=result.note,
        checkedBy=result.checked_by,
        checkedAt=result.checked_at,
        evidence=evidence,
    )
