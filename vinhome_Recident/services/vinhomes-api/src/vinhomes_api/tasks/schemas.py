"""Pydantic schemas for versioned A5 Task domain data."""

from datetime import datetime
from typing import Annotated, Literal, TypeAlias
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StringConstraints,
    field_validator,
)

from ..db.task import TaskDomainType, TaskStatus


class _CleaningSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_alias=True,
        validate_by_name=True,
    )


# The ERD gives representative codes but does not define closed vocabularies.
_NonEmptyCode: TypeAlias = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]
RequiredEvidence: TypeAlias = _NonEmptyCode
QcCriterion: TypeAlias = _NonEmptyCode


class CleaningArea(_CleaningSchema):
    site_id: _NonEmptyCode = Field(alias="siteId")
    location_id: _NonEmptyCode = Field(alias="locationId")


class CleaningAction(_CleaningSchema):
    action_type: _NonEmptyCode = Field(alias="type")
    executor_type: _NonEmptyCode = Field(alias="executorType")


class CleaningPlan(_CleaningSchema):
    """Version 1 CleaningPlan shape stored in ``Task.domain_data``."""

    schema_version: Literal[1] = Field(alias="schemaVersion")
    issue_type: _NonEmptyCode = Field(alias="issueType")
    area: CleaningArea
    actions: list[CleaningAction]
    required_evidence: list[RequiredEvidence] = Field(alias="requiredEvidence")
    qc_criteria: list[QcCriterion] = Field(alias="qcCriteria")
    root_cause_check_required: StrictBool = Field(alias="rootCauseCheckRequired")


class TechnicalWorkPlan(_CleaningSchema):
    """Explicit demo contract for internal technician work; not a ratified ERD extension."""

    schema_version: Literal[1] = Field(alias="schemaVersion")
    work_type: _NonEmptyCode = Field(alias="workType")
    trade: _NonEmptyCode
    area: CleaningArea
    instructions: list[_NonEmptyCode] = Field(min_length=1)
    required_evidence: list[RequiredEvidence] = Field(alias="requiredEvidence", default_factory=list)
    checklist_required: StrictBool = Field(alias="checklistRequired", default=False)
    qc_criteria: list[QcCriterion] = Field(alias="qcCriteria", default_factory=list)


class SecurityWorkPlan(_CleaningSchema):
    """Explicit demo contract for patrol and incident response work."""

    schema_version: Literal[1] = Field(alias="schemaVersion")
    activity_type: Literal["PATROL", "INCIDENT_RESPONSE"] = Field(alias="activityType")
    area: CleaningArea
    instructions: list[_NonEmptyCode] = Field(min_length=1)
    required_evidence: list[RequiredEvidence] = Field(alias="requiredEvidence", default_factory=list)
    checklist_required: StrictBool = Field(alias="checklistRequired", default=True)
    qc_criteria: list[QcCriterion] = Field(alias="qcCriteria", default_factory=list)


class CreateTaskInput(_CleaningSchema):
    """Client-settable Task fields; status and identity are server-owned."""

    title: _NonEmptyCode
    domain_type: TaskDomainType = Field(alias="domainType")
    domain_data: CleaningPlan | TechnicalWorkPlan | SecurityWorkPlan = Field(alias="domainData")
    assignee_type: _NonEmptyCode = Field(alias="assigneeType")
    priority: _NonEmptyCode
    due_at: datetime | None = Field(default=None, alias="dueAt")

    @field_validator("domain_data", mode="before")
    @classmethod
    def validate_domain_data(cls, value, info):
        domain_type = info.data.get("domain_type")
        schema = (
            TechnicalWorkPlan if domain_type is TaskDomainType.TECHNICAL
            else SecurityWorkPlan if domain_type is TaskDomainType.SECURITY
            else CleaningPlan
        )
        return schema.model_validate(value)

    @field_validator("due_at")
    @classmethod
    def due_at_must_include_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("dueAt must include a timezone offset")
        return value


class AssignTaskInput(_CleaningSchema):
    """Task assignment command with an optimistic version precondition."""

    assignee_type: _NonEmptyCode = Field(alias="assigneeType")
    assignee_id: UUID = Field(alias="assigneeId")
    expected_version: int = Field(alias="expectedVersion", gt=0, strict=True)


class TaskRead(_CleaningSchema):
    """Tenant-scoped Task response shape."""

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
        validate_by_alias=True,
        validate_by_name=True,
    )

    id: UUID
    incident_id: UUID = Field(alias="incidentId")
    title: str
    domain_type: TaskDomainType = Field(alias="domainType")
    domain_data: dict[str, object] = Field(alias="domainData")
    domain_schema_version: int = Field(alias="domainSchemaVersion")
    assignee_type: str = Field(alias="assigneeType")
    assignee_id: UUID | None = Field(alias="assigneeId")
    status: TaskStatus
    priority: str
    due_at: datetime | None = Field(alias="dueAt")
    version: int
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
