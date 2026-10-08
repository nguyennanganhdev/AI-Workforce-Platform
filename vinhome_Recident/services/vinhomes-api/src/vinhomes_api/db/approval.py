"""Action approval persistence model."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, Enum as SAEnum, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, UUIDPrimaryKeyMixin


class ApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


def _enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_class]


class ActionApproval(UUIDPrimaryKeyMixin, Base):
    """An approval bound to the exact ActionRequest payload hash."""

    __tablename__ = "vh_action_approval"
    __table_args__ = (
        Index("ix_vh_action_approval_status_expires_at", "status", "expires_at"),
    )

    action_request_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "vh_action_request.id",
            name="fk_vh_action_approval_action_request_id_vh_action_request",
        ),
        nullable=False,
    )
    action_payload_hash: Mapped[str] = mapped_column(String(), nullable=False)
    status: Mapped[ApprovalStatus] = mapped_column(
        SAEnum(
            ApprovalStatus,
            name="ck_vh_action_approval_status",
            native_enum=False,
            create_constraint=True,
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    requested_by_id: Mapped[str] = mapped_column(String(), nullable=False)
    reviewer_id: Mapped[str | None] = mapped_column(String(), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(String(), nullable=True)
    version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=1, server_default=text("1")
    )

    __mapper_args__ = {"version_id_col": version}
