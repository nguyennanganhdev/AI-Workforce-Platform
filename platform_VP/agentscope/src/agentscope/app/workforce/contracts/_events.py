# -*- coding: utf-8 -*-
"""Durable public conversation event contracts."""

from datetime import datetime

from pydantic import Field

from ._base import JsonObject, OpaqueId, WorkforceModel


class ConversationEvent(WorkforceModel):
    schema_version: str = Field(default="1", pattern="^1$")
    event_id: OpaqueId
    sequence: int = Field(ge=1)
    event_type: str = Field(min_length=1, max_length=200)
    occurred_at: datetime
    recorded_at: datetime
    conversation_id: OpaqueId
    external_ticket_id: OpaqueId | None = None
    external_conversation_id: OpaqueId
    external_user_id: OpaqueId
    workflow_id: OpaqueId | None = None
    ticket_id: OpaqueId | None = None
    causation_id: OpaqueId | None = None
    payload: JsonObject = Field(default_factory=dict)


class EventHistoryPage(WorkforceModel):
    items: tuple[ConversationEvent, ...]
    next_cursor: OpaqueId | None = None
    has_more: bool
