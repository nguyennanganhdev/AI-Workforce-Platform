"""ActionRequest persistence model for Vinhomes domain actions."""

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
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, UUIDPrimaryKeyMixin


class RequestedByType(StrEnum):
    HUMAN = "HUMAN"
    SYSTEM = "SYSTEM"
    AUTOMATION = "AUTOMATION"
    AGENT = "AGENT"
    EXTERNAL_SERVICE = "EXTERNAL_SERVICE"


class ActionRequestStatus(StrEnum):
    PROPOSED = "PROPOSED"
    DENIED = "DENIED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    AUTHORIZED = "AUTHORIZED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    EXECUTING = "EXECUTING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


def _enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_class]


class ActionRequest(UUIDPrimaryKeyMixin, Base):
    """An accepted proposal boundary before rule and approval processing."""

    __tablename__ = "vh_action_request"
    __table_args__ = (
        Index("ix_vh_action_request_incident_status", "incident_id", "status"),
    )

    incident_id: Mapped[UUID] = mapped_column(
        ForeignKey("vh_incident.id", name="fk_vh_action_request_incident_id_vh_incident"),
        nullable=False,
    )
    task_id: Mapped[UUID] = mapped_column(
        ForeignKey("vh_task.id", name="fk_vh_action_request_task_id_vh_task"),
        nullable=False,
    )
    requested_by_type: Mapped[RequestedByType] = mapped_column(
        SAEnum(
            RequestedByType,
            name="ck_vh_action_request_requested_by_type",
            native_enum=False,
            create_constraint=True,
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    requested_by_id: Mapped[str] = mapped_column(String(), nullable=False)
    requested_by_version: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    action_type: Mapped[str] = mapped_column(String(), nullable=False)
    target_type: Mapped[str] = mapped_column(String(), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False
    )
    payload_hash: Mapped[str] = mapped_column(String(), nullable=False)
    status: Mapped[str] = mapped_column(String(), nullable=False)
    version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=1, server_default=text("1")
    )
    correlation_id: Mapped[str] = mapped_column(String(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __mapper_args__ = {"version_id_col": version}
