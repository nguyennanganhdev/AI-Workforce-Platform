"""Builder-owned proposal/readiness views, not new inter-module DTOs."""

from typing import Literal, Protocol

from pydantic import Field

from ...contracts import (
    AsyncProtocolSnapshotRef,
    ReuseCandidate,
    ReuseDecision,
    Scope,
    ToolBinding,
    WorkforceModel,
)
from ._requirements import AgentRequirement


class Blocker(WorkforceModel):
    code: str
    message: str
    capability: str | None = None


class ProtocolReadiness(WorkforceModel):
    """Exact-pinned metadata supplied by an injected adapter pending shared accessor."""

    snapshot: AsyncProtocolSnapshotRef
    correlation_supported: bool
    event_types: tuple[str, ...] = ()
    fact_fields: tuple[str, ...] = ()
    event_fact_fields: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    completion_policy: Literal["read_only_auto_close", "explicit_close"]
    timeout_seconds: int | None = Field(default=None, gt=0)
    status_query_tool_version_id: str | None = None


class ProtocolReadinessReader(Protocol):
    async def read(
        self, scope: Scope, snapshot: AsyncProtocolSnapshotRef
    ) -> ProtocolReadiness: ...


class CapabilitySelection(WorkforceModel):
    bindings: tuple[ToolBinding, ...] = ()
    protocols: tuple[AsyncProtocolSnapshotRef, ...] = ()
    covered: tuple[str, ...] = ()
    missing_optional: tuple[str, ...] = ()
    blockers: tuple[Blocker, ...] = ()
    support: tuple[str, ...] = ()
    tracking_channel: Literal["none", "provider_events", "status_query"] = "none"
    completion_policy: str | None = None


class AgentProposal(WorkforceModel):
    requirement: AgentRequirement
    selection: CapabilitySelection
    reuse_decision: ReuseDecision
    candidates: tuple[ReuseCandidate, ...] = ()
    blockers: tuple[Blocker, ...] = ()
    duplicate_keys: tuple[str, ...] = ()


class BuildProposal(WorkforceModel):
    proposal_id: str
    revision: int = Field(ge=1)
    items: tuple[AgentProposal, ...]
    status: Literal["needs_input", "ready", "confirmed", "completed_reused"]
    questions: tuple[str, ...] = ()
    notices: tuple[str, ...] = ()

    @property
    def can_confirm(self) -> bool:
        return (
            self.status == "ready"
            and not self.questions
            and bool(self.items)
            and all(
                not item.blockers and not item.selection.blockers for item in self.items
            )
        )
