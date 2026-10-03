"""Append-only persistence record for a deterministic rule decision."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, UUIDPrimaryKeyMixin


class RuleDecisionValue(StrEnum):
    ALLOW = "ALLOW"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    DENY = "DENY"


def _enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_class]


class RuleEvaluationRecord(UUIDPrimaryKeyMixin, Base):
    """Durable policy result attached to one immutable ActionRequest."""

    __tablename__ = "vh_rule_evaluation"
    __table_args__ = (
        Index("ix_vh_rule_evaluation_action_evaluated", "action_request_id", "evaluated_at"),
    )

    action_request_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "vh_action_request.id",
            name="fk_vh_rule_evaluation_action_request_id_vh_action_request",
        ),
        nullable=False,
    )
    decision: Mapped[RuleDecisionValue] = mapped_column(
        SAEnum(
            RuleDecisionValue,
            name="ck_vh_rule_evaluation_decision",
            native_enum=False,
            create_constraint=True,
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    reason_code: Mapped[str] = mapped_column(String(), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(), nullable=False)
