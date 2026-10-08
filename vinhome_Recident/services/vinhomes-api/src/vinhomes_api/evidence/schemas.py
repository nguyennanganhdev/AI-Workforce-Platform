"""Request and read schemas for storage metadata and WorkOrder evidence."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StringConstraints

from ..db.evidence import EvidenceCapturePhase
from ..work_orders.checklist_schemas import ChecklistExecutionRead


_Code = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]
_StorageProvider = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64),
]
_StorageKey = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=2048),
]
_MimeType = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]
_Checksum = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=256),
]


class RegisterFileObjectInput(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    storage_provider: _StorageProvider = Field(alias="storageProvider")
    storage_key: _StorageKey = Field(alias="storageKey")
    mime_type: _MimeType = Field(alias="mimeType")
    size_bytes: StrictInt = Field(alias="sizeBytes", gt=0)
    checksum: _Checksum


class FileObjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    mime_type: str = Field(alias="mimeType")
    size_bytes: int = Field(alias="sizeBytes")
    checksum: str
    created_at: datetime = Field(alias="createdAt")


class EvidenceMetadata(BaseModel):
    """Open metadata object with validated dimensions/duration when available."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    width: StrictInt | None = Field(default=None, gt=0)
    height: StrictInt | None = Field(default=None, gt=0)
    duration_ms: StrictInt | None = Field(default=None, alias="durationMs", gt=0)


class CreateEvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    file_object_id: UUID = Field(alias="fileObjectId")
    kind: _Code
    capture_phase: EvidenceCapturePhase = Field(alias="capturePhase")
    metadata: EvidenceMetadata = Field(default_factory=EvidenceMetadata)


class EvidenceRefRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    file_object_id: UUID = Field(alias="fileObjectId")
    kind: str
    capture_phase: EvidenceCapturePhase = Field(alias="capturePhase")
    metadata: dict[str, object]
    mime_type: str = Field(alias="mimeType")
    size_bytes: int = Field(alias="sizeBytes")
    checksum: str
    uploaded_by: str = Field(alias="uploadedBy")
    created_at: datetime = Field(alias="createdAt")


class WorkOrderEvidenceRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    work_order_id: UUID = Field(alias="workOrderId")
    items: list[EvidenceRefRead]
    required_evidence: list[str] = Field(alias="requiredEvidence")
    satisfied_required_evidence: list[str] = Field(alias="satisfiedRequiredEvidence")
    missing_required_evidence: list[str] = Field(alias="missingRequiredEvidence")
    unsupported_required_evidence: list[str] = Field(alias="unsupportedRequiredEvidence")
    checklist: ChecklistExecutionRead | None
    can_complete_work_order: bool = Field(alias="canCompleteWorkOrder")
    blockers: list[str]
