"""Append-only measurement, material, and equipment records for one WorkOrder attempt."""

from copy import deepcopy
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ValidationError

from ..concurrency import require_expected_version
from ..db.work_order import WorkOrder, WorkOrderStatus
from .authority import FieldOperationsAuthority
from .lifecycle import InvalidWorkOrderTransition
from .execution_details_schemas import (
    AddEquipmentUsageInput,
    AddExecutionNoteInput,
    AddMaterialUsageInput,
    AddMeasurementInput,
    EquipmentUsageRecordRead,
    ExecutionNoteRecordRead,
    ExecutionDetailsRead,
    MeasurementRecordRead,
    MaterialUsageRecordRead,
    _ExecutionDetailsState,
)


class InvalidExecutionDetails(Exception):
    """Stored execution detail data is not valid for the current schema version."""


def execution_details_read(work_order: WorkOrder) -> ExecutionDetailsRead:
    raw = work_order.result.get("executionDetails")
    if raw is None:
        state = _ExecutionDetailsState(schemaVersion=1)
    else:
        try:
            state = _ExecutionDetailsState.model_validate(raw)
        except ValidationError as exc:
            raise InvalidExecutionDetails("Stored execution details are invalid") from exc
    return ExecutionDetailsRead.model_validate(
        {
            **state.model_dump(mode="python", by_alias=True),
            "workOrderId": work_order.id,
            "workOrderVersion": work_order.version,
        }
    )


def append_execution_detail(
    work_order: WorkOrder,
    *,
    detail_kind: Literal[
        "measurements", "materialUsage", "equipmentUsage", "executionNotes"
    ],
    record: BaseModel,
    expected_version: int,
    authority: FieldOperationsAuthority,
) -> ExecutionDetailsRead:
    authority.require_execute(work_order)
    if (
        work_order.status is not WorkOrderStatus.IN_PROGRESS
        or work_order.execution_started_at is None
    ):
        raise InvalidWorkOrderTransition(
            "Execution details may be added only while the WorkOrder is IN_PROGRESS"
        )
    require_expected_version(work_order.version, expected_version)

    state = _state_for_write(work_order)
    state_attribute = {
        "measurements": "measurements",
        "materialUsage": "material_usage",
        "equipmentUsage": "equipment_usage",
        "executionNotes": "execution_notes",
    }[detail_kind]
    current = list(getattr(state, state_attribute))
    if detail_kind == "measurements":
        record_read = MeasurementRecordRead.model_validate(record.model_dump(mode="python", by_alias=True))
    elif detail_kind == "materialUsage":
        record_read = MaterialUsageRecordRead.model_validate(record.model_dump(mode="python", by_alias=True))
    elif detail_kind == "equipmentUsage":
        record_read = EquipmentUsageRecordRead.model_validate(record.model_dump(mode="python", by_alias=True))
    else:
        record_read = ExecutionNoteRecordRead.model_validate(record.model_dump(mode="python", by_alias=True))
    current.append(record_read)

    state_data = state.model_dump(mode="python", by_alias=True)
    state_data[detail_kind] = current
    next_state = _ExecutionDetailsState.model_validate(state_data)
    next_result = deepcopy(work_order.result)
    next_result["executionDetails"] = next_state.model_dump(mode="json", by_alias=True)
    work_order.result = next_result
    return execution_details_read(work_order)


def make_measurement_record(
    payload: AddMeasurementInput, *, actor_id: str, now: datetime | None = None
) -> MeasurementRecordRead:
    return MeasurementRecordRead(
        id=uuid4(),
        type=payload.measurement_type,
        value=payload.value,
        unit=payload.unit,
        timestamp=now or datetime.now(timezone.utc),
        recordedBy=actor_id,
    )


def make_material_usage_record(
    payload: AddMaterialUsageInput, *, actor_id: str, now: datetime | None = None
) -> MaterialUsageRecordRead:
    return MaterialUsageRecordRead(
        id=uuid4(),
        material=payload.material,
        quantity=payload.quantity,
        unit=payload.unit,
        timestamp=now or datetime.now(timezone.utc),
        recordedBy=actor_id,
    )


def make_equipment_usage_record(
    payload: AddEquipmentUsageInput, *, actor_id: str, now: datetime | None = None
) -> EquipmentUsageRecordRead:
    return EquipmentUsageRecordRead(
        action=payload.action,
        equipment=payload.equipment,
        replacedEquipment=payload.replaced_equipment,
        replacementEquipment=payload.replacement_equipment,
        id=uuid4(),
        timestamp=now or datetime.now(timezone.utc),
        recordedBy=actor_id,
    )


def make_execution_note_record(
    payload: AddExecutionNoteInput, *, actor_id: str, now: datetime | None = None
) -> ExecutionNoteRecordRead:
    return ExecutionNoteRecordRead(
        id=uuid4(),
        note=payload.note,
        methodUsed=payload.method_used,
        timestamp=now or datetime.now(timezone.utc),
        recordedBy=actor_id,
    )


def _state_for_write(work_order: WorkOrder) -> _ExecutionDetailsState:
    raw = work_order.result.get("executionDetails")
    if raw is None:
        return _ExecutionDetailsState(schemaVersion=1)
    try:
        return _ExecutionDetailsState.model_validate(raw)
    except ValidationError as exc:
        raise InvalidExecutionDetails("Stored execution details are invalid") from exc
