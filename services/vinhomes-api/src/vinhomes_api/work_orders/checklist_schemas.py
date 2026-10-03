"""Reviewed version-one checklist definition and execution response shapes."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StringConstraints, model_validator


_Code = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]
_Title = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=256),
]


class ChecklistItemDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: _Code
    title: _Title
    required: StrictBool


class ChecklistCriteria(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    items: list[ChecklistItemDefinition] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def item_ids_must_be_unique(self) -> "ChecklistCriteria":
        ids = [item.id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("checklist item ids must be unique within a version")
        return self


class PinChecklistInput(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    checklist_version_id: UUID = Field(alias="checklistVersionId")
    expected_version: int = Field(alias="expectedVersion", ge=1, strict=True)


class CompleteChecklistItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    expected_version: int = Field(alias="expectedVersion", ge=1, strict=True)


class ChecklistItemCompletionRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    item_id: str = Field(alias="itemId")
    completed_at: datetime = Field(alias="completedAt")
    completed_by: str = Field(alias="completedBy")


class ChecklistVersionRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    checklist_id: UUID = Field(alias="checklistId")
    code: str
    name: str
    category: str
    version_no: int = Field(alias="versionNo")
    criteria: ChecklistCriteria


class ChecklistExecutionRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    work_order_id: UUID = Field(alias="workOrderId")
    checklist_version_id: UUID | None = Field(alias="checklistVersionId")
    checklist: ChecklistVersionRead | None
    required_for_completion: bool = Field(alias="requiredForCompletion")
    is_complete: bool = Field(alias="isComplete")
    can_complete_work_order: bool = Field(alias="canCompleteWorkOrder")
    completed_items: list[ChecklistItemCompletionRead] = Field(alias="completedItems")
    missing_required_item_ids: list[str] = Field(alias="missingRequiredItemIds")
    blockers: list[str]


class _ChecklistExecutionState(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    checklist_version_id: UUID = Field(alias="checklistVersionId")
    completed_items: dict[str, ChecklistItemCompletionRead] = Field(alias="completedItems")

    @model_validator(mode="after")
    def completion_keys_must_match_items(self) -> "_ChecklistExecutionState":
        if any(key != completion.item_id for key, completion in self.completed_items.items()):
            raise ValueError("checklist completion keys must match item ids")
        return self
