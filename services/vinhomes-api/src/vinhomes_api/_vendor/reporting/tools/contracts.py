"""Four read-only report operations; identity is supplied by the runtime."""

from dataclasses import dataclass, field
from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def uuid_string(value: str) -> str:
    return str(UUID(value))


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Scope(StrictModel):
    scope_type: Literal["building", "zone"]
    scope_id: str
    scope_name: Annotated[str, Field(min_length=1, max_length=200)]
    building_ids: Annotated[list[str], Field(min_length=1, max_length=1000)]

    _id = field_validator("scope_id")(uuid_string)

    @field_validator("scope_name")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Blank name")
        return value

    @field_validator("building_ids")
    @classmethod
    def buildings(cls, value):
        value = [uuid_string(item) for item in value]
        if len(value) != len(set(value)):
            raise ValueError("Duplicate buildings")
        return sorted(value)

    @model_validator(mode="after")
    def single_building(self):
        if self.scope_type == "building" and self.building_ids != [self.scope_id]:
            raise ValueError("Building binding mismatch")
        return self


class FilterInput(StrictModel):
    scope_type: Literal["building", "zone"] | None = None
    scope_id: str | None = None
    name: Annotated[str, Field(min_length=1, max_length=200)] | None = None

    @field_validator("scope_id")
    @classmethod
    def identifier(cls, value):
        return uuid_string(value) if value is not None else None

    @field_validator("name")
    @classmethod
    def nonblank(cls, value):
        if value is not None and not value.strip():
            raise ValueError("Blank search name")
        return value

    @model_validator(mode="after")
    def selector(self):
        if self.scope_id is not None and self.name is not None:
            raise ValueError("Use an id or an exact name, not both")
        if (
            self.scope_id is not None or self.name is not None
        ) and self.scope_type is None:
            raise ValueError("Selection requires scope_type")
        return self


class Period(StrictModel):
    from_date: str
    to_date: str

    @field_validator("from_date", "to_date")
    @classmethod
    def iso_date(cls, value):
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError("Use YYYY-MM-DD")
        return value

    @model_validator(mode="after")
    def ordered(self):
        days = (
            date.fromisoformat(self.to_date) - date.fromisoformat(self.from_date)
        ).days
        if not 0 < days <= 3660:
            raise ValueError("Ordered period up to 3660 days required")
        return self


class SummaryInput(Period):
    scope_type: Literal["building", "zone"]
    scope_id: str

    _id = field_validator("scope_id")(uuid_string)


class RatingInput(SummaryInput):
    staff_ids: Annotated[list[str], Field(min_length=1, max_length=100)]

    @field_validator("staff_ids")
    @classmethod
    def staff(cls, value):
        ids = [uuid_string(item) for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate staff IDs")
        return ids


class ResponsePeriod(Period):
    boundary: Literal["[from,to)"]
    timezone: Literal["UTC"] | None = None


@dataclass(frozen=True)
class RuntimeContext:
    principal_id: str
    allowed_building_ids: tuple[str, ...]
    session_cookie: str = field(repr=False)
    repair_category_ids: tuple[str, ...] = ()

    def __post_init__(self):
        if type(self.principal_id) is not str or not self.principal_id.strip():
            raise ValueError("Authenticated principal required")
        if type(self.session_cookie) is not str or not self.session_cookie.strip():
            raise ValueError("Authenticated session required")
        if "\r" in self.session_cookie or "\n" in self.session_cookie:
            raise ValueError("Invalid cookie")
        if type(self.allowed_building_ids) is not tuple:
            raise TypeError("Use immutable building grants")
        ids = tuple(uuid_string(item) for item in self.allowed_building_ids)
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate grants")
        object.__setattr__(self, "allowed_building_ids", ids)
        if type(self.repair_category_ids) is not tuple:
            raise TypeError("Use immutable repair category configuration")
        categories = tuple(uuid_string(item) for item in self.repair_category_ids)
        if len(categories) != len(set(categories)):
            raise ValueError("Duplicate repair categories")
        object.__setattr__(self, "repair_category_ids", categories)


class ReportToolError(Exception):
    def __init__(self, code, *, retryable=False, candidates=None):
        super().__init__(code)
        self.code, self.retryable, self.candidates = code, retryable, candidates

    def result(self):
        result = {"outcome": "failure", "error": self.code, "retryable": self.retryable}
        if self.candidates is not None:
            result["candidates"] = self.candidates
        return result


class Failure(StrictModel):
    outcome: Literal["failure"]
    error: str
    retryable: bool
    candidates: list[Scope] | None = None


class Source(StrictModel):
    method: Literal["GET"]
    path: str


class Success(StrictModel):
    outcome: Literal["success", "empty"]
    operation: str
    sources: list[Source]
    limitations: list[str]


class FilterResult(Success):
    data: list[Scope]
    employee_options: list["EmployeeOption"]


class EmployeeOption(StrictModel):
    staff_id: str
    staff_name: str


class SummaryResult(Success):
    scope: Scope
    period: ResponsePeriod


Count = Annotated[int, Field(ge=0, le=2**63 - 1)]


class BillItem(StrictModel):
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
    invoice_count: Annotated[int, Field(ge=1, le=2**63 - 1)]
    billed_amount: str


class BillData(StrictModel):
    basis: Literal["issued_repair_invoice_grand_total"]
    items: list[BillItem]


class BillResult(SummaryResult):
    data: BillData


class TicketItem(StrictModel):
    incident_type_id: str | None
    incident_type_name: str
    ticket_count: Annotated[int, Field(ge=1, le=2**63 - 1)]
    share: Annotated[float, Field(ge=0, le=1)]


class TicketData(StrictModel):
    total_ticket_count: Count
    incident_ticket_count: Count
    non_incident_ticket_count: Count
    share_basis: Literal["incident_ticket_count"]
    items: list[TicketItem]


class TicketResult(SummaryResult):
    data: TicketData


class RatingItem(StrictModel):
    staff_id: str
    staff_name: str | None
    rating_count: Count
    star_counts: dict[str, Count]
    average_stars: str | None


class RatingData(StrictModel):
    basis: Literal["customer_review_submission"]
    total_rating_count: Count
    average_stars: str | None
    items: list[RatingItem]


class RatingResult(SummaryResult):
    data: RatingData
