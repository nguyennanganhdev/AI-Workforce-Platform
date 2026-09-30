"""Transactional outbox copies of append-only BusinessEvents."""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    JSON,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, UUIDPrimaryKeyMixin


class OutboxStatus(StrEnum):
    PENDING = "PENDING"
    PUBLISHED = "PUBLISHED"
    DEAD_LETTER = "DEAD_LETTER"


def _enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_class]


class OutboxMessage(UUIDPrimaryKeyMixin, Base):
    """One durable delivery record for a committed BusinessEvent."""

    __tablename__ = "vh_outbox_message"
    __table_args__ = (
        UniqueConstraint("business_event_id", name="uq_vh_outbox_business_event"),
        Index("ix_vh_outbox_status_created", "status", "created_at"),
    )

    tenant_id: Mapped[UUID] = mapped_column(nullable=False)
    business_event_id: Mapped[UUID] = mapped_column(
        ForeignKey("vh_business_event.id", name="fk_vh_outbox_business_event_id_vh_business_event"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False
    )
    status: Mapped[OutboxStatus] = mapped_column(
        SAEnum(
            OutboxStatus,
            name="ck_vh_outbox_message_status",
            native_enum=False,
            create_constraint=True,
            values_callable=_enum_values,
        ),
        nullable=False,
        default=OutboxStatus.PENDING,
        server_default=OutboxStatus.PENDING.value,
    )
    attempt_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(String(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
