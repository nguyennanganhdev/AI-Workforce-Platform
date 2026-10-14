"""Long-term memory of one business agent, learned from verified tickets."""

from typing import Literal

from pydantic import Field

from ._base import _RecordBase

MemoryKind = Literal["lesson", "fact", "preference"]
MemoryStatus = Literal["active", "superseded", "rejected"]


class AgentMemoryRecord(_RecordBase):
    """One remembered item with its provenance.

    Items are approved by the agent itself (no manual review step) but only
    after a provenance check: every item cites events of a ticket whose work
    was verified. A newer item that contradicts an older one supersedes it;
    nothing is deleted, so a manager can always see what changed and why.
    """

    user_id: str
    agent_id: str
    kind: MemoryKind = "lesson"
    content: str = Field(min_length=1, max_length=2000)
    status: MemoryStatus = "active"
    source_ticket: str = Field(default="", max_length=255)
    source_event_ids: list[str] = Field(default_factory=list, max_length=20)
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    uses: int = Field(default=0, ge=0)
    supersedes: str | None = Field(default=None, max_length=255)
    reason: str = Field(default="", max_length=1000)
    """Why it was added, superseded or retired."""


__all__ = ["AgentMemoryRecord", "MemoryKind", "MemoryStatus"]
