"""WorkOrder persistence model for execution attempts."""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, UUIDPrimaryKeyMixin


class WorkOrderStatus(StrEnum):
    OPEN = "OPEN"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


def _enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_class]


class WorkOrder(UUIDPrimaryKeyMixin, Base):
    """One immutable execution attempt associated with a Task and action."""

    __tablename__ = "vh_work_order"
    __table_args__ = (
        UniqueConstraint(
            "task_id",
            "attempt_no",
            name="uq_vh_work_order_task_attempt_no",
        ),
    )

    incident_id: Mapped[UUID] = mapped_column(
        ForeignKey("vh_incident.id", name="fk_vh_work_order_incident_id_vh_incident"),
        nullable=False,
    )
    task_id: Mapped[UUID] = mapped_column(
        ForeignKey("vh_task.id", name="fk_vh_work_order_task_id_vh_task"),
        nullable=False,
    )
    action_request_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "vh_action_request.id",
            name="fk_vh_work_order_action_request_id_vh_action_request",
        ),
        nullable=False,
    )
    executor_type: Mapped[str] = mapped_column(String(), nullable=False)
    executor_id: Mapped[UUID | None] = mapped_column(nullable=True)
    status: Mapped[WorkOrderStatus] = mapped_column(
        SAEnum(
            WorkOrderStatus,
            name="ck_vh_work_order_status",
            native_enum=False,
            create_constraint=True,
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    redo_of_work_order_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "vh_work_order.id",
            name="fk_vh_work_order_redo_of_work_order_id_vh_work_order",
        ),
        nullable=True,
    )
    checklist_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "vh_checklist_version.id",
            name="fk_vh_work_order_checklist_version_id_vh_checklist_version",
        ),
        nullable=True,
    )
    execution_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    execution_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    result: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False
    )
    version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=1, server_default=text("1")
    )

    __mapper_args__ = {"version_id_col": version}
