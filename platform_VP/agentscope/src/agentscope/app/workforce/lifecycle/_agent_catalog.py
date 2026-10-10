"""Published candidate catalog reads the whole manager library, never a
batch."""

from typing import Any, Dict, Optional, Sequence, Tuple

from ..contracts import AgentManifest, ReuseDecision, Scope
from ._models import (
    AgentDefinition,
    AgentDraft,
    Deployment,
    LifecycleError,
    PublishedVersion,
)


class CatalogMixin:
    async def index_legacy(
        self,
        scope: Scope,
        legacy_agent_id: str,
        manifest: AgentManifest,
        decision: ReuseDecision,
    ) -> AgentDraft:
        """Trusted migration adapter supplies verified owner/profile, never
        guesses area ownership.

        A legacy mapping does not bypass evaluation or synthesize a published
        version.
        """
        async with self.repository.transaction(scope) as tx:
            existing = [
                agent
                for agent in await tx.list("agents")
                if agent.get("legacy_agent_id") == legacy_agent_id
            ]
            if existing:
                agent = existing[0]
                if agent.get("draft_id"):
                    return AgentDraft.model_validate(
                        await tx.get("drafts", agent["draft_id"])
                    )
                raise LifecycleError(
                    "AGENT_ALREADY_EXISTS",
                    details={"agent_id": agent["agent_id"]},
                )
        return await self._create_draft(
            scope, manifest, decision, None, legacy_agent_id
        )

    async def get_version(
        self, scope: Scope, version_id: str
    ) -> PublishedVersion:
        return PublishedVersion.model_validate(
            await self.repository.get(scope, "versions", version_id)
        )

    async def get_deployment(
        self, scope: Scope, deployment_id: str
    ) -> Deployment:
        return Deployment.model_validate(
            await self.repository.get(scope, "deployments", deployment_id)
        )

    async def list_candidates(
        self, scope: Scope, capabilities: Sequence[str]
    ) -> Tuple[PublishedVersion, ...]:
        await self.identity.check_scope_active(scope)
        async with self.repository.transaction(scope) as tx:
            agents = [
                AgentDefinition.model_validate(x)
                for x in await tx.list("agents")
            ]
        result = []
        for agent in agents:
            if agent.status != "published" or not agent.active_version_id:
                continue
            version = await self.get_version(scope, agent.active_version_id)
            if not set(capabilities).issubset(
                version.manifest.spec.capabilities
            ):
                continue
            validation = await self.version_compatibility(scope, version)
            if validation.valid:
                result.append(version)
        return tuple(result)

    async def list_agents(
        self, scope: Scope, cursor: Optional[str] = None, limit: int = 50
    ) -> Dict[str, Any]:
        if not 1 <= limit <= 200:
            raise LifecycleError("INVALID_PAGE_SIZE", 422)
        async with self.repository.transaction(scope) as tx:
            rows = await tx.list("agents")
        if cursor:
            if cursor not in [row["agent_id"] for row in rows]:
                raise LifecycleError("INVALID_CURSOR", 422)
            rows = [row for row in rows if row["agent_id"] > cursor]
        page = rows[:limit]
        return {
            "items": page,
            "next_cursor": page[-1]["agent_id"] if len(rows) > limit else None,
        }

    async def list_deployments(self, scope: Scope) -> Dict[str, Any]:
        async with self.repository.transaction(scope) as tx:
            return {"items": await tx.list("deployments"), "next_cursor": None}
