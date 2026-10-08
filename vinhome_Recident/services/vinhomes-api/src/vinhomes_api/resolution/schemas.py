"""Incident resolution check and command DTOs."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ..db.incident import IncidentStatus


class ResolutionBlocker(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    code: str
    subject_type: str = Field(alias="subjectType")
    subject_id: str = Field(alias="subjectId")
    message: str


class IncidentResolutionRead(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    incident_id: UUID = Field(alias="incidentId")
    status: IncidentStatus
    resolved_at: datetime | None = Field(alias="resolvedAt")
    can_resolve: bool = Field(alias="canResolve")
    blockers: list[ResolutionBlocker]


class ResolveIncidentInput(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    expected_version: int = Field(alias="expectedVersion", ge=1, strict=True)
