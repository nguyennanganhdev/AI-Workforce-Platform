"""Immutable quality-control decisions and their linked QC evidence."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    JSON,
    String,
    event,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, UUIDPrimaryKeyMixin


class QCOutcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"


class QCResult(UUIDPrimaryKeyMixin, Base):
    """One immutable QC decision for a completed WorkOrder attempt."""

    __tablename__ = "vh_qc_result"
    __table_args__ = (
        Index("ix_vh_qc_result_work_order_checked_at", "work_order_id", "checked_at"),
    )

    work_order_id: Mapped[UUID] = mapped_column(
        ForeignKey("vh_work_order.id", name="fk_vh_qc_result_work_order_id_vh_work_order"),
        nullable=False,
    )
    outcome: Mapped[QCOutcome] = mapped_column(
        SAEnum(
            QCOutcome,
            name="ck_vh_qc_result_outcome",
            native_enum=False,
            create_constraint=True,
            values_callable=lambda enum_class: [member.value for member in enum_class],
        ),
        nullable=False,
    )
    criteria_json: Mapped[list[str]] = mapped_column(
        "criteria", JSON().with_variant(JSONB(), "postgresql"), nullable=False
    )
    failed_criteria_json: Mapped[list[str]] = mapped_column(
        "failed_criteria", JSON().with_variant(JSONB(), "postgresql"), nullable=False
    )
    redo_required: Mapped[bool] = mapped_column(nullable=False)
    note: Mapped[str | None] = mapped_column(String(), nullable=True)
    checked_by: Mapped[str] = mapped_column(String(), nullable=False)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class QCResultEvidence(Base):
    """Append-only link between one immutable decision and QC evidence."""

    __tablename__ = "vh_qc_result_evidence"

    qc_result_id: Mapped[UUID] = mapped_column(
        ForeignKey("vh_qc_result.id", name="fk_vh_qc_result_evidence_qc_result_id_vh_qc_result"),
        primary_key=True,
        nullable=False,
    )
    evidence_ref_id: Mapped[UUID] = mapped_column(
        ForeignKey("vh_evidence_ref.id", name="fk_vh_qc_result_evidence_evidence_ref_id_vh_evidence_ref"),
        primary_key=True,
        nullable=False,
    )


@event.listens_for(QCResult, "before_update")
def _reject_qc_result_update(_mapper, _connection, _target) -> None:
    raise RuntimeError("QCResult is immutable")


@event.listens_for(QCResult, "before_delete")
def _reject_qc_result_delete(_mapper, _connection, _target) -> None:
    raise RuntimeError("QCResult is immutable")


@event.listens_for(QCResultEvidence, "before_update")
def _reject_qc_result_evidence_update(_mapper, _connection, _target) -> None:
    raise RuntimeError("QCResult evidence links are append-only")


@event.listens_for(QCResultEvidence, "before_delete")
def _reject_qc_result_evidence_delete(_mapper, _connection, _target) -> None:
    raise RuntimeError("QCResult evidence links are append-only")
