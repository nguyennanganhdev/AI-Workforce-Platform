from pydantic import BaseModel, Field, ConfigDict
from typing import Literal, List, Optional, Union, Any

class Fact(BaseModel):
    key: str
    value: Any
    source: Literal["customer_report", "staff_verified", "agent_inference"]
    source_message_id: str

class Resident(BaseModel):
    resident_id: str
    resident_name: str
    phone_number: str

class Location(BaseModel):
    location_scope_id: str
    unit_id: str
    unit_number: str
    building_id: str
    building_code: str
    building_name: str

class RequestInfo(BaseModel):
    title: str
    description: str
    request_kind: Literal["incident", "service_request"]
    category_id: Optional[str] = None
    priority: Literal["low", "normal", "high", "critical"]
    severity: Literal["unknown", "minor", "moderate", "major", "critical", "not_applicable"]
    is_emergency: bool = Field(default=False)
    triage_decision_id: Optional[str] = None
    handoff_reason: Literal["needs_staff", "self_help_declined", "self_help_failed", "emergency"]

class ReceptionToSupervisorMessage(BaseModel):
    """
    Schema V2 nhận từ Lễ Tân (Reception) -> Điều Phối (Supervisor)
    Theo chuẩn chốt ngày 01/10/2026.
    """
    schema_version: Literal["2.0"]
    message_id: str
    correlation_id: str
    sent_at: str

    message_type: Literal[
        "ticket_submitted",
        "information_provided",
        "plan_approved",
        "plan_rejected",
        "plan_change_requested",
        "cancel_requested"
    ]
    message: str
    source_message_id: Optional[str] = None

    tenant_id: str
    domain_id: str
    domain_name: str
    workspace_id: str
    team_id: str

    ticket_id: str
    ticket_code: str
    ticket_generation: int
    ticket_version: str

    resident: Resident
    location: Location
    request: RequestInfo

    facts: List[Fact] = Field(default_factory=list)
    file_ids: List[str] = Field(default_factory=list)
    created_at: str

    model_config = ConfigDict(extra="forbid")

class ResultData(BaseModel):
    outcome: Literal["work_completed", "needs_human_review", "unable_to_resolve"]
    summary: str
    work_order_ids: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)

class ErrorData(BaseModel):
    code: str
    retryable: bool
    message: str

class SupervisorToReceptionResult(BaseModel):
    """
    Schema V2 trả từ Điều Phối (Supervisor) -> Lễ Tân (Reception)
    Theo chuẩn chốt ngày 01/10/2026.
    """
    schema_version: Literal["2.0"]
    message_id: str
    correlation_id: str
    sent_at: str

    message_type: Literal[
        "accepted",
        "in_progress",
        "information_requested",
        "plan_approval_requested",
        "completed",
        "failed",
        "cancelled"
    ]
    message: str

    tenant_id: str
    workspace_id: str
    team_id: str
    ticket_id: str
    ticket_code: str
    ticket_generation: int
    ticket_version: str

    supervisor_run_id: str

    result: Optional[ResultData] = None
    error: Optional[ErrorData] = None

    model_config = ConfigDict(extra="forbid")
