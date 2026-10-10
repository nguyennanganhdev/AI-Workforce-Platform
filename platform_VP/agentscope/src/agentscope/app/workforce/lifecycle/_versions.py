"""Availability guards for immutable workflow pins and retention handoff."""

from typing import Any, Dict, Protocol, Tuple

from ..contracts import Scope
from ._models import (
    AgentDefinition,
    LifecycleError,
    PublishedVersion,
    ValidationReport,
)


class VersionUsagePort(Protocol):
    """Orchestration supplies persisted usage; Lifecycle never writes
    workflows."""

    async def get_version_references(
        self, scope: Scope, version_id: str
    ) -> Tuple[Dict[str, Any], ...]: ...


class VersionMixin:
    async def version_compatibility(
        self, scope: Scope, version: PublishedVersion
    ) -> ValidationReport:
        report, refs, policy = await self.validator.freeze(
            scope, version.manifest
        )
        if (
            refs != version.protocol_refs
            or policy != version.policy_snapshot
            or report != version.validation
        ):
            report = report.model_copy(
                update={
                    "valid": False,
                    "blockers": tuple(
                        sorted(
                            set(report.blockers).union(
                                {"PINNED_DEPENDENCY_DRIFT"}
                            )
                        )
                    ),
                }
            )
        return report

    async def require_version_compatible(
        self, scope: Scope, version: PublishedVersion
    ) -> None:
        report = await self.version_compatibility(scope, version)
        if not report.valid:
            raise LifecycleError(
                "AGENT_INCOMPATIBLE",
                details={"blockers": list(report.blockers)},
            )

    async def require_compatible(self, scope: Scope, manifest: Any) -> None:
        report = await self.validator.validate(scope, manifest)
        if not report.valid:
            raise LifecycleError(
                "AGENT_INCOMPATIBLE",
                details={"blockers": list(report.blockers)},
            )

    async def check_continuation(
        self, scope: Scope, version_id: str
    ) -> PublishedVersion:
        await self.identity.check_scope_active(scope)
        version = await self.get_version(scope, version_id)
        agent = AgentDefinition.model_validate(
            await self.repository.get(scope, "agents", version.agent_id)
        )
        if agent.status in ("disabled", "revoked"):
            raise LifecycleError("CONTINUATION_BLOCKED", 403)
        # Archive prevents new selection; existing pins stay readable and
        # usable.
        await self.require_version_compatible(scope, version)
        return version

    async def retention_info(
        self, scope: Scope, version_id: str
    ) -> Dict[str, Any]:
        version = await self.get_version(scope, version_id)
        refs = await self.usage.get_version_references(scope, version_id)
        return {
            "version_id": version_id,
            "agent_id": version.agent_id,
            "retained": True,
            "hard_delete_allowed": False,
            "references": list(refs),
            "protocol_refs": list(version.protocol_refs),
        }
