"""File metadata and append-only evidence references for Field Operations."""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    JSON,
    String,
    UniqueConstraint,
    event,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, UUIDPrimaryKeyMixin


class EvidenceCapturePhase(StrEnum):
    BEFORE = "BEFORE"
    AFTER = "AFTER"
    QC = "QC"
    OTHER = "OTHER"


class FileObject(UUIDPrimaryKeyMixin, Base):
    """Metadata for a binary stored by the trusted file-storage service."""

    __tablename__ = "vh_file_object"
    __table_args__ = (
        CheckConstraint("size_bytes > 0", name="ck_vh_file_object_size_positive"),
        UniqueConstraint(
            "tenant_id", "storage_provider", "storage_key", name="uq_vh_file_object_tenant_key"
        ),
        UniqueConstraint("tenant_id", "id", name="uq_vh_file_object_tenant_id"),
    )

    # Tenant ownership is an implementation extension needed to authorize opaque file IDs.
    tenant_id: Mapped[UUID] = mapped_column(nullable=False)
    storage_provider: Mapped[str] = mapped_column(String(), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum: Mapped[str] = mapped_column(String(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class EvidenceRef(UUIDPrimaryKeyMixin, Base):
    """Append-only association between field evidence and a business attempt."""

    __tablename__ = "vh_evidence_ref"
    __table_args__ = (
        Index("ix_vh_evidence_ref_work_order_phase_created", "work_order_id", "capture_phase", "created_at"),
        Index("ix_vh_evidence_ref_incident_created", "incident_id", "created_at"),
    )

    incident_id: Mapped[UUID] = mapped_column(
        ForeignKey("vh_incident.id", name="fk_vh_evidence_ref_incident_id_vh_incident"),
        nullable=False,
    )
    task_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("vh_task.id", name="fk_vh_evidence_ref_task_id_vh_task"),
        nullable=True,
    )
    work_order_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("vh_work_order.id", name="fk_vh_evidence_ref_work_order_id_vh_work_order"),
        nullable=True,
    )
    file_id: Mapped[UUID] = mapped_column(
        ForeignKey("vh_file_object.id", name="fk_vh_evidence_ref_file_id_vh_file_object"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(), nullable=False)
    capture_phase: Mapped[EvidenceCapturePhase] = mapped_column(
        SAEnum(
            EvidenceCapturePhase,
            name="ck_vh_evidence_ref_capture_phase",
            native_enum=False,
            create_constraint=True,
            values_callable=lambda enum_class: [member.value for member in enum_class],
        ),
        nullable=False,
    )
    evidence_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON().with_variant(JSONB(), "postgresql"), nullable=False
    )
    uploaded_by: Mapped[str] = mapped_column(String(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


@event.listens_for(FileObject, "before_update")
def _reject_file_object_update(_mapper, _connection, _target) -> None:
    raise RuntimeError("FileObject metadata is immutable")


@event.listens_for(FileObject, "before_delete")
def _reject_file_object_delete(_mapper, _connection, _target) -> None:
    raise RuntimeError("FileObject metadata is immutable")


@event.listens_for(EvidenceRef, "before_update")
def _reject_evidence_ref_update(_mapper, _connection, _target) -> None:
    raise RuntimeError("EvidenceRef is append-only")


@event.listens_for(EvidenceRef, "before_delete")
def _reject_evidence_ref_delete(_mapper, _connection, _target) -> None:
    raise RuntimeError("EvidenceRef is append-only")
