"""Evidence authorization, media metadata validation and prerequisite checks."""

from uuid import UUID

from fastapi import HTTPException

from ..db.evidence import EvidenceCapturePhase, EvidenceRef, FileObject
from ..db.task import Task
from ..db.work_order import WorkOrder, WorkOrderStatus
from ..work_orders.authority import FieldOperationsAuthority, FieldOperationsRole
from ..work_orders.checklist_execution import checklist_execution_read
from ..work_orders.checklist_schemas import ChecklistExecutionRead
from .schemas import EvidenceMetadata, EvidenceRefRead, WorkOrderEvidenceRead


class InvalidEvidenceMetadata(Exception):
    pass


def authorize_evidence_write(
    authority: FieldOperationsAuthority,
    work_order: WorkOrder,
    *,
    capture_phase: EvidenceCapturePhase,
    actor_id: str,
) -> None:
    if capture_phase is EvidenceCapturePhase.QC:
        if authority.actor_type != "user" or FieldOperationsRole.QC not in authority.roles:
            raise HTTPException(status_code=403, detail="QC role required for QC evidence")
        if work_order.status is not WorkOrderStatus.COMPLETED:
            raise HTTPException(status_code=409, detail="QC evidence requires a COMPLETED WorkOrder")
        try:
            actor_uuid = UUID(actor_id)
        except ValueError:
            actor_uuid = None
        if actor_uuid is not None and actor_uuid == work_order.executor_id:
            raise HTTPException(status_code=403, detail="Executor cannot provide independent QC evidence")
        return

    authority.require_execute(work_order)
    if work_order.status is not WorkOrderStatus.IN_PROGRESS:
        raise HTTPException(status_code=409, detail="Execution evidence requires an IN_PROGRESS WorkOrder")


def validate_image_video_metadata(mime_type: str, metadata: EvidenceMetadata) -> None:
    media_type = mime_type.strip().lower()
    if media_type.startswith("image/"):
        if metadata.width is None or metadata.height is None:
            raise InvalidEvidenceMetadata("Image evidence requires positive width and height metadata")
    elif media_type.startswith("video/"):
        if metadata.width is None or metadata.height is None or metadata.duration_ms is None:
            raise InvalidEvidenceMetadata(
                "Video evidence requires positive width, height, and durationMs metadata"
            )


def work_order_evidence_read(
    work_order: WorkOrder,
    *,
    task: Task,
    rows: list[tuple[EvidenceRef, FileObject]],
    checklist: ChecklistExecutionRead,
) -> WorkOrderEvidenceRead:
    evidence_codes: list[str] = []
    invalid_requirement_data = False
    raw_requirements = task.domain_data.get("requiredEvidence")
    if raw_requirements is None:
        raw_requirements = []
    if not isinstance(raw_requirements, list) or any(
        not isinstance(code, str) or not code.strip() for code in raw_requirements
    ):
        invalid_requirement_data = True
    else:
        evidence_codes = list(dict.fromkeys(code.strip() for code in raw_requirements))

    items = [
        EvidenceRefRead(
            id=reference.id,
            fileObjectId=file_object.id,
            kind=reference.kind,
            capturePhase=reference.capture_phase,
            metadata=reference.evidence_metadata,
            mimeType=file_object.mime_type,
            sizeBytes=file_object.size_bytes,
            checksum=file_object.checksum,
            uploadedBy=reference.uploaded_by,
            createdAt=reference.created_at,
        )
        for reference, file_object in rows
    ]

    satisfied: list[str] = []
    missing: list[str] = []
    unsupported: list[str] = []
    requirements = {
        "IMAGE_BEFORE": (EvidenceCapturePhase.BEFORE, "image/"),
        "IMAGE_AFTER": (EvidenceCapturePhase.AFTER, "image/"),
    }
    for code in evidence_codes:
        if code == "CHECKLIST":
            if checklist.can_complete_work_order:
                satisfied.append(code)
            continue
        requirement = requirements.get(code)
        if requirement is None:
            unsupported.append(code)
            continue
        phase, mime_prefix = requirement
        if any(
            item.capture_phase is phase and item.mime_type.lower().startswith(mime_prefix)
            for item in items
        ):
            satisfied.append(code)
        else:
            missing.append(code)

    blockers: list[str] = []
    if invalid_requirement_data:
        blockers.append("REQUIRED_EVIDENCE_CONTRACT_INVALID")
    blockers.extend(f"MISSING_REQUIRED_EVIDENCE:{code}" for code in missing)
    blockers.extend(f"UNSUPPORTED_REQUIRED_EVIDENCE:{code}" for code in unsupported)
    blockers.extend(checklist.blockers)
    return WorkOrderEvidenceRead(
        workOrderId=work_order.id,
        items=items,
        requiredEvidence=evidence_codes,
        satisfiedRequiredEvidence=satisfied,
        missingRequiredEvidence=missing,
        unsupportedRequiredEvidence=unsupported,
        checklist=checklist,
        canCompleteWorkOrder=not blockers,
        blockers=blockers,
    )
