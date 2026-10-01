"""Business Task persistence model for Vinhomes workflows."""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, Enum as SAEnum, ForeignKey, Index, JSON, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class TaskStatus(StrEnum):
    OPEN = "OPEN"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    DONE = "DONE"
    CANCELLED = "CANCELLED"


class TaskDomainType(StrEnum):
    SANITATION = "SANITATION"
    LANDSCAPE = "LANDSCAPE"
    TECHNICAL = "TECHNICAL"
    SECURITY = "SECURITY"


def _enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_class]


class Task(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A business task attached to one canonical Incident."""

    __tablename__ = "vh_task"
    __table_args__ = (
        Index("ix_vh_task_incident_status", "incident_id", "status"),
    )

    incident_id: Mapped[UUID] = mapped_column(
        ForeignKey("vh_incident.id", name="fk_vh_task_incident_id_vh_incident"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(), nullable=False)
    domain_type: Mapped[TaskDomainType] = mapped_column(
        SAEnum(
            TaskDomainType,
            name="ck_vh_task_domain_type",
            native_enum=False,
            create_constraint=True,
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    domain_data: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False
    )
    domain_schema_version: Mapped[int] = mapped_column(nullable=False)
    assignee_type: Mapped[str] = mapped_column(String(), nullable=False)
    assignee_id: Mapped[UUID | None] = mapped_column(nullable=True)
    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(
            TaskStatus,
            name="ck_vh_task_status",
            native_enum=False,
            create_constraint=True,
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    priority: Mapped[str] = mapped_column(String(), nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=1, server_default=text("1")
    )

    __mapper_args__ = {"version_id_col": version}
