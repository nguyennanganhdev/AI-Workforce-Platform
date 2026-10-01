"""Versioned, attempt-scoped execution detail records stored on WorkOrder.result."""

from datetime import datetime
from math import isfinite
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictFloat,
    StrictInt,
    StringConstraints,
    field_validator,
    model_validator,
)


_Code = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]
_Label = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=256),
]
_Note = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=2000),
]
_Numeric = StrictInt | StrictFloat


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class AddMeasurementInput(_Input):
    measurement_type: _Code = Field(alias="type")
    value: _Numeric
    unit: _Code
    expected_version: int = Field(alias="expectedVersion", gt=0, strict=True)

    @field_validator("value")
    @classmethod
    def value_must_be_finite(cls, value: int | float) -> int | float:
        if isinstance(value, float) and not isfinite(value):
            raise ValueError("value must be finite")
        return value


class AddMaterialUsageInput(_Input):
    material: _Label
    quantity: _Numeric
    unit: _Code
    expected_version: int = Field(alias="expectedVersion", gt=0, strict=True)

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_positive(cls, value: int | float) -> int | float:
        if (isinstance(value, float) and not isfinite(value)) or value <= 0:
            raise ValueError("quantity must be positive")
        return value


class AddEquipmentUsageInput(_Input):
    action: Literal["USED", "REPLACED"]
    equipment: _Label | None = None
    replaced_equipment: _Label | None = Field(default=None, alias="replacedEquipment")
    replacement_equipment: _Label | None = Field(default=None, alias="replacementEquipment")
    expected_version: int = Field(alias="expectedVersion", gt=0, strict=True)

    @model_validator(mode="after")
    def fields_must_match_action(self) -> "AddEquipmentUsageInput":
        if self.action == "USED":
            if not self.equipment or self.replaced_equipment or self.replacement_equipment:
                raise ValueError("USED requires equipment and forbids replacement fields")
        elif (
            self.equipment
            or not self.replaced_equipment
            or not self.replacement_equipment
        ):
            raise ValueError(
                "REPLACED requires replacedEquipment and replacementEquipment only"
            )
        return self


class AddExecutionNoteInput(_Input):
    note: _Note | None = None
    method_used: _Label | None = Field(default=None, alias="methodUsed")
    expected_version: int = Field(alias="expectedVersion", gt=0, strict=True)

    @model_validator(mode="after")
    def note_or_method_required(self) -> "AddExecutionNoteInput":
        if self.note is None and self.method_used is None:
            raise ValueError("note or methodUsed is required")
        return self


class _StoredRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: UUID
    timestamp: datetime
    recorded_by: str = Field(alias="recordedBy")


class MeasurementRecordRead(_StoredRecord):
    measurement_type: _Code = Field(alias="type")
    value: _Numeric
    unit: _Code

    @field_validator("value")
    @classmethod
    def value_must_be_finite(cls, value: int | float) -> int | float:
        if isinstance(value, float) and not isfinite(value):
            raise ValueError("stored measurement value must be finite")
        return value


class MaterialUsageRecordRead(_StoredRecord):
    material: _Label
    quantity: _Numeric
    unit: _Code

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_positive(cls, value: int | float) -> int | float:
        if (isinstance(value, float) and not isfinite(value)) or value <= 0:
            raise ValueError("stored material quantity must be positive and finite")
        return value


class EquipmentUsageRecordRead(_StoredRecord):
    action: Literal["USED", "REPLACED"]
    equipment: _Label | None = None
    replaced_equipment: _Label | None = Field(default=None, alias="replacedEquipment")
    replacement_equipment: _Label | None = Field(default=None, alias="replacementEquipment")

    @model_validator(mode="after")
    def fields_must_match_action(self) -> "EquipmentUsageRecordRead":
        if self.action == "USED":
            if not self.equipment or self.replaced_equipment or self.replacement_equipment:
                raise ValueError("invalid USED equipment record")
        elif (
            self.equipment
            or not self.replaced_equipment
            or not self.replacement_equipment
        ):
            raise ValueError("invalid REPLACED equipment record")
        return self


class ExecutionNoteRecordRead(_StoredRecord):
    note: _Note | None = None
    method_used: _Label | None = Field(default=None, alias="methodUsed")

    @model_validator(mode="after")
    def note_or_method_required(self) -> "ExecutionNoteRecordRead":
        if self.note is None and self.method_used is None:
            raise ValueError("invalid execution note record")
        return self


class _ExecutionDetailsState(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: Literal[1] = Field(alias="schemaVersion")
    measurements: list[MeasurementRecordRead] = Field(default_factory=list)
    material_usage: list[MaterialUsageRecordRead] = Field(
        default_factory=list, alias="materialUsage"
    )
    equipment_usage: list[EquipmentUsageRecordRead] = Field(
        default_factory=list, alias="equipmentUsage"
    )
    execution_notes: list[ExecutionNoteRecordRead] = Field(
        default_factory=list, alias="executionNotes"
    )


class ExecutionDetailsRead(_ExecutionDetailsState):
    work_order_id: UUID = Field(alias="workOrderId")
    work_order_version: int = Field(alias="workOrderVersion")
