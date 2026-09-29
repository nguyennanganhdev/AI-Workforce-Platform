"""Versioned module contracts. Context fields alone never establish authority."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

Id = Annotated[str, Field(min_length=1, max_length=256)]
Text = Annotated[str, Field(min_length=1, max_length=100_000)]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Context(Model):
    tenant_id: Id
    principal_id: Id
    domain_id: Id
    workspace_id: Id
    ticket_id: Id
    ticket_generation: Annotated[int, Field(ge=0, strict=True)]
    binding_id: Id
    run_id: Id

    def scope(self) -> tuple[str, str, int]:
        """Unique application room key, independent of mutable routing metadata."""
        return (self.tenant_id, self.ticket_id, self.ticket_generation)

    def same_room_scope(self, other: Context) -> bool:
        return (
            self.scope() == other.scope()
            and self.domain_id == other.domain_id
            and self.workspace_id == other.workspace_id
        )


class TurnPolicy(Model):
    max_turns: Annotated[int, Field(gt=0, le=10000, strict=True)] = 12
    max_consecutive_turns: Annotated[int, Field(gt=0, le=10000, strict=True)] = 2
    timeout_seconds: Annotated[float, Field(gt=0, le=3600, allow_inf_nan=False)] = 60


class ParticipantSpec(Model):
    agent_version_id: Id
    role: Id


class Participant(ParticipantSpec):
    platform_agent_id: Id
    member_id: Id
    binding_id: Id
    binding_generation: Annotated[int, Field(ge=1)]
    framework_agent_id: Id
    framework_reference: Id


class MessageInput(Model):
    content: Text
    delivery: Literal["broadcast", "direct"] = "broadcast"
    recipient_agent_version_id: Id | None = None
    in_reply_to_message_id: Id | None = None

    @model_validator(mode="after")
    def addressing(self) -> MessageInput:
        if (self.delivery == "direct") != (self.recipient_agent_version_id is not None):
            raise ValueError("direct requires recipient; broadcast forbids recipient")
        return self


class Message(MessageInput):
    message_id: Id
    sequence: Annotated[int, Field(ge=1)]
    sender: Id
    timestamp: datetime


class FollowUp(Model):
    recipient_agent_version_id: Id
    content: Text


class AgentOutput(Model):
    content: Text
    follow_up_requests: list[FollowUp] = Field(default_factory=list)


class OpenRoom(Model):
    version: Literal[2] = 2
    operation: Literal["open_room"] = "open_room"
    room_id: Id | None = None
    groupchat_version_id: Id
    participants: Annotated[list[ParticipantSpec], Field(min_length=1)]
    turn_policy: TurnPolicy = Field(default_factory=TurnPolicy)
    initial_message: MessageInput

    @model_validator(mode="after")
    def unique_members(self) -> OpenRoom:
        ids = [p.agent_version_id for p in self.participants]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate participant version")
        return self


class RoomCommand(Model):
    version: Literal[2] = 2
    room_id: Id
    expected_room_version: Annotated[int, Field(ge=1, strict=True)]


class AppendMessage(RoomCommand):
    operation: Literal["append_message"] = "append_message"
    message: MessageInput


class RunTurn(RoomCommand):
    operation: Literal["run_turn"] = "run_turn"
    turn_id: Id
    task_id: Id
    correlation_id: Id
    speaker_agent_version_id: Id
    instruction: Text
    in_reply_to_message_id: Id | None = None


class AddParticipant(RoomCommand):
    operation: Literal["add_participant"] = "add_participant"
    participant: ParticipantSpec


class UpdateTurnPolicy(RoomCommand):
    operation: Literal["update_turn_policy"] = "update_turn_policy"
    turn_policy: TurnPolicy


class CloseRoom(RoomCommand):
    operation: Literal["close_room"] = "close_room"


class CancelTurn(RoomCommand):
    operation: Literal["cancel_turn"] = "cancel_turn"
    target_operation_id: Id


Payload = Annotated[
    OpenRoom
    | AppendMessage
    | RunTurn
    | AddParticipant
    | UpdateTurnPolicy
    | CloseRoom
    | CancelTurn,
    Field(discriminator="operation"),
]


class Command(Model):
    contract_version: Literal["1"] = "1"
    request_id: Id
    trace_id: Id
    idempotency_key: Id
    context: Context
    payload: Payload


class Query(Model):
    contract_version: Literal["1"] = "1"
    request_id: Id
    context: Context
    room_id: Id
    operation: Literal["get_room", "list_messages"] = "get_room"
    after_sequence: Annotated[int, Field(ge=0, strict=True)] = 0
    limit: Annotated[int, Field(gt=0, le=500, strict=True)] = 100


TurnStatus = Literal["success", "failure", "timeout", "cancel", "outcome_unknown"]


class RoomData(Model):
    version: Literal[2] = 2
    room_id: Id
    ticket_id: Id
    ticket_generation: int
    room_version: int
    room_state: Literal["idle", "running", "paused", "closed"]
    pause_reason: str | None = None
    operation_id: str | None = None
    turn_id: str | None = None
    task_id: str | None = None
    source_run_id: str | None = None
    speaker_agent_version_id: str | None = None
    turn_status: TurnStatus | None = None
    messages: list[Message] = Field(default_factory=list)
    follow_up_requests: list[FollowUp] = Field(default_factory=list)
    turns_used: int
    turns_remaining: int
    consecutive_turns: int
    needs_dispatcher_decision: bool = True
    participants: list[ParticipantSpec] = Field(default_factory=list)
    transcript_cursor: int


class Error(Model):
    code: Id
    message: Text
    retryable: bool = False
    details: dict = Field(default_factory=dict)


class Success(Model):
    request_id: Id
    status: Literal["accepted", "completed"]
    data: RoomData


class Failure(Model):
    request_id: Id
    status: Literal["error"] = "error"
    error: Error


Result = Annotated[Success | Failure, Field(discriminator="status")]


class ActiveOperation(Model):
    operation_id: Id
    dedup_key: Id
    fence: int
    command: Command
    participant: Participant
    source_run_id: Id
    dispatch_started: bool = True


class Snapshot(Model):
    """Internal DEV-4 aggregate; never expose bindings/framework refs to clients."""

    room_id: Id
    scope: Context
    groupchat_version_id: Id
    participants: list[Participant]
    policy: TurnPolicy
    room_version: int = 1
    room_state: Literal["idle", "running", "paused", "closed"] = "idle"
    pause_reason: str | None = None
    turns_used: int = 0
    consecutive_turns: int = 0
    last_speaker: str | None = None
    active_operation: ActiveOperation | None = None
    transcript: list[Message] = Field(default_factory=list)
    transcript_cursor: int = 0
    framework_state_reference: str | None = None
    audit_events: list[dict] = Field(default_factory=list)
    used_turn_ids: list[str] = Field(default_factory=list)


class OperationRecord(Model):
    semantic_hash: str
    result: Success | Failure


class ScopeState(Model):
    snapshot: Snapshot | None = None
    operations: dict[str, OperationRecord] = Field(default_factory=dict)
    fence: int = 0


def new_id() -> str:
    return str(uuid4())


def now() -> datetime:
    return datetime.now(timezone.utc)


class RoomError(Exception):
    def __init__(self, code: str, message: str | None = None):
        self.code = code
        super().__init__(message or code)


class TerminalInvocationError(Exception):
    """Invocation port confirms terminal failure, with no outstanding work."""
