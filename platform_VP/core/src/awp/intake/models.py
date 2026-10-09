"""The neutral contract between a domain and the platform."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class IntakeFact(BaseModel):
    key: str
    value: str
    source: str = "reported"  # who said it: reported | verified | inferred


class CaseIntake(BaseModel):
    """A request a domain hands to the platform."""

    message_id: str = Field(description="Unique per message; sending it again is harmless.")
    external_ref: str = Field(description="The domain's own id for the case (a ticket id).")
    summary: str
    description: str = ""
    facts: list[IntakeFact] = Field(default_factory=list)
    requester_ref: str | None = None
    priority: str = "normal"
    # Opaque domain data that domain tools may read (ids, codes, versions).
    attributes: dict = Field(default_factory=dict)
    # Which published leader profile handles it; the domain's default if empty.
    leader_profile: str | None = None
    budget_usd: float | None = None
    budget_tokens: int | None = None
    # Push domains may ask for a signed callback; pull domains leave it empty.
    callback_url: str | None = None


class FollowUp(BaseModel):
    """More information for an open case (the person answered, a plan was decided...)."""

    message_id: str
    kind: str = "information"
    text: str
    attributes: dict = Field(default_factory=dict)


class CaseResult(BaseModel):
    case_id: str
    external_ref: str
    outcome: Literal["resolved", "needs_human", "cannot_resolve", "failed"]
    answer: str = ""
    cites: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    cost: dict = Field(default_factory=dict)
