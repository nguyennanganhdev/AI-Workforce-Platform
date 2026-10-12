"""Lifecycle-owned release DTOs; shared contracts remain unchanged."""

from typing import Any, Dict, Protocol, Sequence, Tuple

from pydantic import AwareDatetime, Field, StrictInt

from ...contracts import AgentManifest, OpaqueId, Scope, WorkforceModel
from .._models import ValidationReport
from ..async_evaluation import FrozenEvaluation, LifecycleSuite


class ReleaseSelection(WorkforceModel):
    draft_id: str = Field(min_length=1, max_length=200)
    draft_revision: StrictInt = Field(ge=1)
    evaluation_id: str = Field(min_length=1, max_length=200)
    deployment_revision: StrictInt = Field(ge=0)


class ReleaseContext(WorkforceModel):
    """Current server configuration, never configuration supplied by a client."""

    runtime_profile: Dict[str, Any]
    test_context: Dict[str, Any]
    suite: LifecycleSuite


class PublishedVersion(WorkforceModel):
    scope: Scope
    agent_id: OpaqueId
    version_id: OpaqueId
    evaluation_id: OpaqueId
    frozen: FrozenEvaluation
    published_by: OpaqueId
    published_at: AwareDatetime

    @property
    def manifest(self) -> AgentManifest:
        return AgentManifest.model_validate(
            self.frozen.read(self.scope)["snapshot"]["manifest"]
        )


class ReleaseValidator(Protocol):
    """Resolve current dependencies using the supplied transaction.

    Composition must lock/CAS the dependency heads and availability rows until
    commit. An independent AsyncDraftValidator read is insufficient for an
    atomic publish. The callback must not call a model/provider or commit.
    """

    async def validate(
        self, scope: Scope, manifest: AgentManifest, uow: Any
    ) -> Tuple[ValidationReport, Dict[str, Any]]: ...


class VersionUsageReader(Protocol):
    """Orchestration provides workflow/checkpoint usage; Lifecycle never scans it."""

    async def references(self, scope: Scope, version_id: str) -> Sequence[str]: ...
