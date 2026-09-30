"""Append-only Vinhomes business event persistence model."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, JSON, String, event, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, UUIDPrimaryKeyMixin


class AppendOnlyBusinessEventError(RuntimeError):
    """Raised when application code tries to mutate a recorded event."""


class BusinessEvent(UUIDPrimaryKeyMixin, Base):
    """Immutable record of a business state change."""

    __tablename__ = "vh_business_event"
    __table_args__ = (
        Index(
            "ix_vh_business_event_incident_occurred_at",
            "incident_id",
            text("occurred_at DESC"),
        ),
    )

    tenant_id: Mapped[UUID] = mapped_column(nullable=False)
    incident_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "vh_incident.id",
            name="fk_vh_business_event_incident_id_vh_incident",
        ),
        nullable=True,
    )
    subject_type: Mapped[str] = mapped_column(String(), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(), nullable=False)
    event_type: Mapped[str] = mapped_column(String(), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(), nullable=False)
    actor_version: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    data: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False
    )
    correlation_id: Mapped[str] = mapped_column(String(), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


@event.listens_for(BusinessEvent, "before_update")
def _reject_business_event_update(_mapper, _connection, _target) -> None:
    raise AppendOnlyBusinessEventError("Business events cannot be updated")


@event.listens_for(BusinessEvent, "before_delete")
def _reject_business_event_delete(_mapper, _connection, _target) -> None:
    raise AppendOnlyBusinessEventError("Business events cannot be deleted")
