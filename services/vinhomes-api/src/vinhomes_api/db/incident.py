"""Canonical Vinhomes Incident persistence model."""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import Enum as SAEnum
from sqlalchemy import BigInteger, DateTime, Index, JSON, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class IncidentStatus(StrEnum):
    NEW = "NEW"
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class IncidentStage(StrEnum):
    INTAKE = "INTAKE"
    TRIAGE = "TRIAGE"
    PLANNING = "PLANNING"
    EXECUTION = "EXECUTION"
    QC = "QC"
    RESIDENT_CONFIRMATION = "RESIDENT_CONFIRMATION"


def _enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_class]


class Incident(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One canonical ticket aggregate for Vinhomes business incidents."""

    __tablename__ = "vh_incident"
    __table_args__ = (
        Index(
            "ix_vh_incident_tenant_project_status_severity",
            "tenant_id",
            "project_id",
            "status",
            "severity",
        ),
        Index("ix_vh_incident_tower_status", "tower_id", "status"),
    )

    tenant_id: Mapped[UUID] = mapped_column(nullable=False)
    project_id: Mapped[UUID] = mapped_column(nullable=False)
    tower_id: Mapped[UUID | None] = mapped_column(nullable=True)
    category: Mapped[str] = mapped_column(String(), nullable=False)
    title: Mapped[str] = mapped_column(String(), nullable=False)
    location_json: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False
    )
    severity: Mapped[str] = mapped_column(String(), nullable=False)
    status: Mapped[IncidentStatus] = mapped_column(
        SAEnum(
            IncidentStatus,
            name="ck_vh_incident_status",
            native_enum=False,
            create_constraint=True,
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    stage: Mapped[IncidentStage] = mapped_column(
        SAEnum(
            IncidentStage,
            name="ck_vh_incident_stage",
            native_enum=False,
            create_constraint=True,
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    owner_user_id: Mapped[UUID | None] = mapped_column(nullable=True)
    sla_due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=1, server_default=text("1")
    )

    __mapper_args__ = {"version_id_col": version}
