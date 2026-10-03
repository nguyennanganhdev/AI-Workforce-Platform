"""Tenant-owned checklist templates and immutable published versions."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, UUIDPrimaryKeyMixin


class Checklist(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "vh_checklist"
    __table_args__ = (
        Index("ix_vh_checklist_tenant_category", "tenant_id", "category"),
    )

    tenant_id: Mapped[UUID] = mapped_column(nullable=False)
    code: Mapped[str] = mapped_column(String(), nullable=False)
    name: Mapped[str] = mapped_column(String(), nullable=False)
    category: Mapped[str] = mapped_column(String(), nullable=False)
    status: Mapped[str] = mapped_column(String(), nullable=False)


class ChecklistVersion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "vh_checklist_version"
    __table_args__ = (
        CheckConstraint("version_no > 0", name="ck_vh_checklist_version_positive"),
        UniqueConstraint(
            "checklist_id", "version_no", name="uq_vh_checklist_version_no"
        ),
        Index("ix_vh_checklist_version_checklist_status", "checklist_id", "status"),
    )

    checklist_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "vh_checklist.id",
            name="fk_vh_checklist_version_checklist_id_vh_checklist",
        ),
        nullable=False,
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    criteria_json: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[str] = mapped_column(String(), nullable=False)
