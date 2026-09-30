"""Read schemas for Vinhomes Incidents."""

from datetime import datetime, timezone
from enum import StrEnum
from math import ceil
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ..db.incident import Incident, IncidentStage, IncidentStatus


class IncidentSlaStatus(StrEnum):
    OVERDUE = "OVERDUE"
    ON_TRACK = "ON_TRACK"
    NO_DEADLINE = "NO_DEADLINE"


class IncidentSortField(StrEnum):
    SLA = "sla"
    SEVERITY = "severity"
    CREATED_AT = "createdAt"


class IncidentSortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


class IncidentRead(BaseModel):
    """Tenant-scoped Incident response without internal tenant identity."""

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
        validate_by_alias=True,
        validate_by_name=True,
    )

    id: UUID
    project_id: UUID = Field(alias="projectId")
    tower_id: UUID | None = Field(alias="towerId")
    category: str
    title: str
    location_json: dict[str, Any] = Field(alias="location")
    severity: str
    status: IncidentStatus
    stage: IncidentStage
    owner_user_id: UUID | None = Field(alias="ownerUserId")
    sla_due_at: datetime | None = Field(alias="slaDueAt")
    resolved_at: datetime | None = Field(alias="resolvedAt")
    closed_at: datetime | None = Field(alias="closedAt")
    sla_remaining_seconds: int | None = Field(default=None, alias="slaRemainingSeconds")
    sla_overdue: bool = Field(default=False, alias="slaOverdue")
    version: int
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class IncidentPage(BaseModel):
    """Paginated Incident queue response."""

    model_config = ConfigDict(extra="forbid", validate_by_alias=True, validate_by_name=True)

    items: list[IncidentRead]
    total: int
    limit: int
    offset: int


def incident_read(incident: Incident, *, now: datetime) -> IncidentRead:
    """Build an Incident response and calculate its SLA countdown at one instant."""
    result = IncidentRead.model_validate(incident)
    due_at = result.sla_due_at
    if due_at is None:
        return result
    if due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=timezone.utc)
    else:
        due_at = due_at.astimezone(timezone.utc)
    remaining = ceil((due_at - now.astimezone(timezone.utc)).total_seconds())
    return result.model_copy(
        update={
            "sla_due_at": due_at,
            "sla_remaining_seconds": remaining,
            "sla_overdue": due_at <= now.astimezone(timezone.utc),
        }
    )
