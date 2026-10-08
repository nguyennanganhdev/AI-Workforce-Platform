"""Demo extension schemas for Field Operations progress outside canonical status."""

from typing import Literal

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from typing import Annotated

from .field_operations_state import FieldOperationsState

_Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=512)]
_Code = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]


class FieldOperationsVersionCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    expected_version: int = Field(alias="expectedVersion", ge=1)


class PauseExecutionInput(FieldOperationsVersionCommand):
    reason: _Text


class ReportBlockerInput(FieldOperationsVersionCommand):
    code: _Code
    note: str | None = Field(default=None, max_length=2000)


class RequestFieldSupportInput(FieldOperationsVersionCommand):
    support_type: Literal["TECHNICAL", "MEDICAL", "FIRE_SAFETY", "MANAGEMENT", "OTHER"] = Field(alias="supportType")
    note: str | None = Field(default=None, max_length=2000)


class ContractorResponseInput(FieldOperationsVersionCommand):
    decision: Literal["ACCEPTED", "REJECTED"]
    reason: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def rejection_needs_reason(self):
        if self.decision == "REJECTED" and not (self.reason and self.reason.strip()):
            raise ValueError("A rejection reason is required")
        return self


class ContractorArrivalPlanInput(FieldOperationsVersionCommand):
    planned_start_at: datetime = Field(alias="plannedStartAt")
    planned_end_at: datetime = Field(alias="plannedEndAt")

    @model_validator(mode="after")
    def validate_window(self):
        if self.planned_start_at.utcoffset() is None or self.planned_end_at.utcoffset() is None:
            raise ValueError("Arrival plan timestamps must include timezone offsets")
        if self.planned_start_at >= self.planned_end_at:
            raise ValueError("plannedEndAt must be after plannedStartAt")
        return self


class EscalateWorkOrderInput(FieldOperationsVersionCommand):
    urgency: Literal["NORMAL", "HIGH", "URGENT"] = "NORMAL"
    reason: _Text


class SecurityIncidentReportInput(FieldOperationsVersionCommand):
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    summary: _Text
    people_refs: list[_Code] = Field(alias="peopleRefs", default_factory=list, max_length=100)
    vehicle_refs: list[_Code] = Field(alias="vehicleRefs", default_factory=list, max_length=100)
    asset_refs: list[_Code] = Field(alias="assetRefs", default_factory=list, max_length=100)


class SecurityAreaActionInput(FieldOperationsVersionCommand):
    area_id: _Code = Field(alias="areaId")
    action: Literal["SECURE", "RELEASE"]
    note: str | None = Field(default=None, max_length=2000)


class HandoverInput(FieldOperationsVersionCommand):
    recipient: _Text
    note: _Text


class FieldOperationsStateRead(FieldOperationsState):
    """Current attempt-local execution state; contract status is explicitly demo."""
