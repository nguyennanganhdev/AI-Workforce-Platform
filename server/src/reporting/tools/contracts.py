"""Strict model inputs. Identity and grants are injected by the runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Annotated, Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


def uuid_string(value: str) -> str:
    return str(UUID(value))


class FilterInput(Input):
    pass


class BuildingInput(Input):
    building_id: str

    _building = field_validator("building_id")(uuid_string)


class PeriodInput(BuildingInput):
    from_date: str
    to_date: str
    timezone: str = "Asia/Ho_Chi_Minh"

    @field_validator("from_date", "to_date")
    @classmethod
    def valid_date(cls, value):
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError("Use YYYY-MM-DD")
        return value

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Unknown IANA timezone") from None
        return value

    @model_validator(mode="after")
    def ordered_period(self):
        days = (
            date.fromisoformat(self.to_date) - date.fromisoformat(self.from_date)
        ).days
        if not 0 < days <= 3660:
            raise ValueError("Period must be ordered and no longer than 3660 days")
        return self


class EmployeeInput(PeriodInput):
    pass


class FeedbackInput(BuildingInput):
    staff_id: str
    limit: Annotated[int, Field(ge=1, le=100)] = 50
    offset: Annotated[int, Field(ge=0, le=1_000_000)] = 0

    _staff = field_validator("staff_id")(uuid_string)


class RevenueInput(PeriodInput):
    category_id: str

    _category = field_validator("category_id")(uuid_string)


class FrequencyInput(PeriodInput):
    interval: Literal["day", "week", "month"] = "month"
    category_id: str | None = None

    @field_validator("category_id")
    @classmethod
    def valid_category(cls, value):
        return uuid_string(value) if value is not None else None


class SupportingInput(PeriodInput):
    kind: Literal["tickets", "work_orders", "invoices"] = "tickets"
    limit: Annotated[int, Field(ge=1, le=100)] = 50
    offset: Annotated[int, Field(ge=0, le=1_000_000)] = 0


class ExportInput(PeriodInput):
    # Current backend exports issued invoice revenue, not collected revenue.
    kind: Literal["incident_frequency", "issued_revenue"]
    category_id: str | None = None
    format: Literal["docx"] = "docx"
    idempotency_key: Annotated[str, Field(min_length=1, max_length=160)]

    @field_validator("category_id")
    @classmethod
    def valid_category(cls, value):
        return uuid_string(value) if value is not None else None

    @field_validator("idempotency_key")
    @classmethod
    def valid_key(cls, value):
        if not value.strip() or any(ord(c) < 32 for c in value):
            raise ValueError("Invalid idempotency key")
        return value

    @model_validator(mode="after")
    def supported_export(self):
        if self.kind == "issued_revenue" and self.category_id is None:
            raise ValueError("Revenue export requires category_id")
        if self.kind == "incident_frequency" and self.category_id is not None:
            raise ValueError("Backend incident export cannot filter category")
        return self


class ExportStatusInput(Input):
    export_id: str

    _export = field_validator("export_id")(uuid_string)


@dataclass(frozen=True)
class RuntimeContext:
    """Construct after authentication; never include this in an LLM tool schema."""

    principal_id: str
    allowed_building_ids: tuple[str, ...]
    session_cookie: str = field(repr=False)

    def __post_init__(self):
        if not self.principal_id.strip() or not self.session_cookie.strip():
            raise ValueError("Authenticated runtime context required")
        if "\r" in self.session_cookie or "\n" in self.session_cookie:
            raise ValueError("Invalid session cookie")
        if not isinstance(self.allowed_building_ids, tuple):
            raise TypeError("Use an immutable building grant tuple")
        object.__setattr__(
            self,
            "allowed_building_ids",
            tuple(uuid_string(item) for item in self.allowed_building_ids),
        )


class ReportToolError(Exception):
    def __init__(self, code: str, *, retryable=False, execution_unknown=False):
        super().__init__(code)
        self.code = code
        self.retryable = retryable
        self.execution_unknown = execution_unknown

    def result(self):
        return {
            "outcome": "failure",
            "error": self.code,
            "retryable": self.retryable,
            "execution_unknown": self.execution_unknown,
        }
