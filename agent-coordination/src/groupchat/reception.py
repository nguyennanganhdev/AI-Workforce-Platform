"""Local V2 boundary models; backend routing and authorization stay out of the wire."""
from datetime import datetime
from typing import Annotated, List, Literal, Optional, Union

from pydantic import Field, StrictBool, StrictFloat, StrictInt, StrictStr, field_validator, model_validator

from .models import Id, Model, Text

InputType = Literal['ticket_submitted', 'information_provided', 'plan_approved',
                    'plan_rejected', 'plan_change_requested', 'cancel_requested']
OutputType = Literal['accepted', 'in_progress', 'information_requested',
                     'plan_approval_requested', 'completed', 'failed', 'cancelled']


class Fact(Model):
    key: Id
    value: Optional[Union[StrictStr, StrictInt, StrictFloat, StrictBool]]
    source: Literal['customer_report', 'staff_verified', 'agent_inference']
    source_message_id: Id


class Resident(Model):
    resident_id: Id
    resident_name: Text
    phone_number: Text


class Location(Model):
    location_scope_id: Id
    unit_id: Id
    unit_number: Text
    building_id: Id
    building_code: Text
    building_name: Text


class Request(Model):
    title: Text
    description: Text
    request_kind: Literal['incident', 'service_request']
    category_id: Optional[Id] = None
    priority: Literal['low', 'normal', 'high', 'critical']
    severity: Literal['unknown', 'minor', 'moderate', 'major', 'critical', 'not_applicable']
    is_emergency: StrictBool
    triage_decision_id: Optional[Id] = None
    handoff_reason: Literal['needs_staff', 'self_help_declined', 'self_help_failed', 'emergency']


class Envelope(Model):
    schema_version: Literal['2.0']
    message_id: Id
    correlation_id: Id
    sent_at: str
    message: Text
    tenant_id: Id
    workspace_id: Id
    team_id: Id
    ticket_id: Id
    ticket_code: Id
    ticket_generation: Annotated[int, Field(ge=0, strict=True)]
    ticket_version: Id

    @field_validator('sent_at')
    @classmethod
    def timestamp(cls, value: str) -> str:
        if datetime.fromisoformat(value.replace('Z', '+00:00')).utcoffset() is None:
            raise ValueError('timestamp requires timezone')
        return value


class ReceptionMessage(Envelope):
    message_type: InputType
    source_message_id: Optional[Id] = None
    domain_id: Id
    domain_name: Text
    resident: Resident
    location: Location
    request: Request
    facts: List[Fact]
    file_ids: List[Id]
    created_at: str

    @field_validator('created_at')
    @classmethod
    def created_timestamp(cls, value: str) -> str:
        return cls.timestamp(value)

    @model_validator(mode='after')
    def source_required(self) -> 'ReceptionMessage':
        if self.message_type != 'ticket_submitted' and self.source_message_id is None:
            raise ValueError('source_message_id required for resident responses')
        return self


class ReceptionResult(Model):
    outcome: Literal['work_completed', 'needs_human_review', 'unable_to_resolve']
    summary: Text
    work_order_ids: List[Id]
    evidence_ids: List[Id]


class ReceptionError(Model):
    code: Id
    retryable: StrictBool
    message: Text


class SupervisorMessage(Envelope):
    message_type: OutputType
    supervisor_run_id: Id
    result: Optional[ReceptionResult] = None
    error: Optional[ReceptionError] = None

    @model_validator(mode='after')
    def completed_result(self) -> 'SupervisorMessage':
        if self.message_type == 'completed' and (
            self.result is None or self.result.outcome != 'work_completed'
        ):
            raise ValueError('completed requires work_completed result')
        return self
