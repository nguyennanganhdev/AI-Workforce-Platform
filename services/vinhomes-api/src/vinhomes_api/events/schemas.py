"""Business event timeline read models."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ..db.business_event import BusinessEvent


class BusinessEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    incident_id: UUID = Field(alias="incidentId")
    subject_type: str = Field(alias="subjectType")
    subject_id: str = Field(alias="subjectId")
    event_type: str = Field(alias="eventType")
    actor_type: str = Field(alias="actorType")
    actor_id: str = Field(alias="actorId")
    actor_version: int | None = Field(alias="actorVersion")
    data: dict[str, Any]
    correlation_id: str = Field(alias="correlationId")
    occurred_at: datetime = Field(alias="occurredAt")


class BusinessEventPage(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    items: list[BusinessEventRead]
    total: int
    limit: int
    offset: int
