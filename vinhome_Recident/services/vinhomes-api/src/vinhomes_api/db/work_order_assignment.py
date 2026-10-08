"""Append-only history of WorkOrder assignment changes."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, UniqueConstraint, event, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, UUIDPrimaryKeyMixin


class WorkOrderAssignment(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "vh_work_order_assignment"
    __table_args__ = (
        UniqueConstraint("work_order_id", "work_order_version", name="uq_vh_work_order_assignment_version"),
        Index("ix_vh_work_order_assignment_order_assigned_at", "work_order_id", "assigned_at"),
    )

    work_order_id: Mapped[UUID] = mapped_column(
        ForeignKey("vh_work_order.id", name="fk_vh_work_order_assignment_work_order_id_vh_work_order"),
        nullable=False,
    )
    work_order_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    executor_type: Mapped[str] = mapped_column(String(), nullable=False)
    executor_id: Mapped[UUID] = mapped_column(nullable=False)
    assigned_by_type: Mapped[str] = mapped_column(String(), nullable=False)
    assigned_by_id: Mapped[str] = mapped_column(String(), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


@event.listens_for(WorkOrderAssignment, "before_update")
def _reject_update(_mapper, _connection, _target) -> None:
    raise RuntimeError("WorkOrder assignment history is append-only")


@event.listens_for(WorkOrderAssignment, "before_delete")
def _reject_delete(_mapper, _connection, _target) -> None:
    raise RuntimeError("WorkOrder assignment history is append-only")
