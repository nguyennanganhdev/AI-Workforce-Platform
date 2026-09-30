"""A5 CleaningPlan execution read and command contracts."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ..db.task import TaskDomainType
from ..tasks.schemas import CleaningArea


class A5ActionExecutionRead(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: UUID
    action_type: str = Field(alias="type")
    executor_type: str = Field(alias="executorType")
    completed: bool
    completed_at: datetime | None = Field(alias="completedAt")
    completed_by: str | None = Field(alias="completedBy")


class A5ExecutionRead(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    work_order_id: UUID = Field(alias="workOrderId")
    task_id: UUID = Field(alias="taskId")
    domain_type: TaskDomainType = Field(alias="domainType")
    domain_schema_version: int = Field(alias="domainSchemaVersion")
    work_order_version: int = Field(alias="workOrderVersion")
    issue_type: str = Field(alias="issueType")
    area: CleaningArea
    actions: list[A5ActionExecutionRead]
    required_evidence: list[str] = Field(alias="requiredEvidence")
    satisfied_required_evidence: list[str] = Field(alias="satisfiedRequiredEvidence")
    missing_required_evidence: list[str] = Field(alias="missingRequiredEvidence")
    unsupported_required_evidence: list[str] = Field(alias="unsupportedRequiredEvidence")
    qc_criteria: list[str] = Field(alias="qcCriteria")
    root_cause_check_required: bool = Field(alias="rootCauseCheckRequired")
    can_complete_work_order: bool = Field(alias="canCompleteWorkOrder")
    blockers: list[str]


class CompleteA5ActionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    expected_version: int = Field(alias="expectedVersion", ge=1)
