# -*- coding: utf-8 -*-
"""The chat endpoint schema."""

from pydantic import BaseModel, Field, model_validator

from ....message import Msg
from ....event import UserConfirmResultEvent, ExternalExecutionResultEvent


class ChatRequest(BaseModel):
    """Request body for the chat endpoint."""

    agent_id: str = Field(
        description="Agent ID for the chat endpoint.",
    )

    session_id: str = Field(
        description="The session to send the message to.",
    )

    target_agent_id: str | None = Field(
        default=None,
        description=(
            "Optional explicit team member for this one turn. The backend "
            "also resolves a leading ``@Agent Name`` from message text."
        ),
    )

    task_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Existing logical task inside this team/ticket.",
    )
    new_task: bool = Field(
        default=False,
        description="Start a separate logical task in the same ticket.",
    )
    in_reply_to: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Shared event/question id this customer message answers.",
    )

    input: (
        Msg
        | list[Msg]
        | UserConfirmResultEvent
        | ExternalExecutionResultEvent
        | None
    ) = Field(
        description="The input message(s), or agent event, or None.",
    )

    @model_validator(mode="after")
    def _task_selector(self) -> "ChatRequest":
        if self.new_task and self.task_id is not None:
            raise ValueError("new_task and task_id are mutually exclusive")
        if (self.task_id is not None or self.new_task or self.in_reply_to) and not isinstance(
            self.input,
            (Msg, list),
        ):
            raise ValueError("task selectors are only valid for user messages")
        return self


class ChatTriggerResponse(BaseModel):
    """Response body for the fire-and-forget chat trigger.

    Confirms that the chat run was scheduled. Events produced by the
    run arrive separately via the session's SSE stream endpoint.
    """

    status: str = Field(
        default="started",
        description='"started" for a scheduled run; "awaiting_confirmation" for clarification.',
    )
    session_id: str = Field(
        description="Echo of the session id the run was started for.",
    )
    message: Msg | None = Field(
        default=None,
        description="A persisted clarification when chat consent is ambiguous.",
    )
