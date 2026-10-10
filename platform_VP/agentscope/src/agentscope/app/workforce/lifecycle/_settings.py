"""Fork/edit/rollback change deployments without rewriting pinned versions."""

from typing import Any, Dict, List

from ..contracts import ReuseAction, ReuseDecision, Scope
from ._models import (
    AgentDefinition,
    AgentDraft,
    Deployment,
    LifecycleError,
    manifest_diff,
    new_id,
    now,
)


class SettingsMixin:
    async def fork_version(self, scope: Scope, version_id: str) -> AgentDraft:
        version = await self.get_version(scope, version_id)
        agent = AgentDefinition.model_validate(
            await self.repository.get(scope, "agents", version.agent_id)
        )
        if agent.draft_id:
            raise LifecycleError(
                "AGENT_BUILD_IN_PROGRESS", details={"draft_id": agent.draft_id}
            )
        if version_id != agent.active_version_id:
            raise LifecycleError("FORK_REQUIRES_ACTIVE_VERSION")
        check = await self.find_candidates(
            scope, version.manifest.business_profile
        )
        decision = ReuseDecision(
            agent_key=version.manifest.spec.agent_key,
            action=ReuseAction.REVISE,
            reuse_check_id=check.reuse_check_id,
            agent_id=version.agent_id,
            version_id=version.version_id,
            reason="Owner requested a settings revision",
            expected_catalog_revision=check.agent_catalog_revision,
        )
        return await self.create_draft(scope, version.manifest, decision)

    async def version_history(
        self, scope: Scope, agent_id: str
    ) -> Dict[str, Any]:
        await self.repository.get(scope, "agents", agent_id)
        async with self.repository.transaction(scope) as tx:
            versions = [
                x
                for x in await tx.list("versions")
                if x["agent_id"] == agent_id
            ]
        versions.sort(key=lambda x: (x["published_at"], x["version_id"]))
        return {"items": versions, "next_cursor": None}

    async def diff_draft(
        self, scope: Scope, draft_id: str
    ) -> List[Dict[str, Any]]:
        draft = await self.get_draft(scope, draft_id)
        if not draft.source_version_id:
            return []
        source = await self.get_version(scope, draft.source_version_id)
        return manifest_diff(source.manifest, draft.manifest)

    async def rollback(
        self,
        scope: Scope,
        deployment_id: str,
        version_id: str,
        expected_revision: int,
    ) -> Deployment:
        await self.identity.check_scope_active(scope)
        version = await self.get_version(scope, version_id)
        await self.require_version_compatible(scope, version)
        async with self.repository.transaction(scope) as tx:
            await self.identity.check_scope_active(scope, uow=tx)
            deployment = Deployment.model_validate(
                await tx.get("deployments", deployment_id)
            )
            agent = AgentDefinition.model_validate(
                await tx.get("agents", deployment.agent_id)
            )
            if deployment.agent_id != version.agent_id:
                raise LifecycleError("VERSION_OWNER_MISMATCH")
            if agent.status in ("archived", "disabled", "revoked"):
                raise LifecycleError("AGENT_UNAVAILABLE")
            if deployment.revision != expected_revision:
                raise LifecycleError("REVISION_CONFLICT")
            await tx.fence_catalog(await tx.catalog_revision())
            changed = deployment.model_copy(
                update={
                    "active_version_id": version_id,
                    "revision": expected_revision + 1,
                }
            )
            await tx.save(
                "deployments",
                deployment_id,
                changed.model_dump(mode="json"),
                expected_revision,
            )
            changed_agent = agent.model_copy(
                update={
                    "active_version_id": version_id,
                    "revision": agent.revision + 1,
                }
            )
            await tx.save(
                "agents",
                agent.agent_id,
                changed_agent.model_dump(mode="json"),
                agent.revision,
            )
            await tx.insert(
                "release_events",
                new_id(),
                {
                    "agent_id": agent.agent_id,
                    "version_id": version_id,
                    "event_type": "agent.rolled_back",
                    "actor_id": scope.manager_account_id,
                    "occurred_at": now().isoformat(),
                },
            )
            return changed

    async def set_availability(
        self, scope: Scope, agent_id: str, status: str, expected_revision: int
    ) -> AgentDefinition:
        await self.identity.check_scope_active(scope)
        if status not in ("archived", "disabled", "revoked", "published"):
            raise LifecycleError("INVALID_AGENT_STATUS", 422)
        current = AgentDefinition.model_validate(
            await self.repository.get(scope, "agents", agent_id)
        )
        if status == "published":
            if not current.active_version_id or current.status == "revoked":
                raise LifecycleError("AGENT_UNAVAILABLE")
            version = await self.get_version(scope, current.active_version_id)
            await self.require_version_compatible(scope, version)
        async with self.repository.transaction(scope) as tx:
            await self.identity.check_scope_active(scope, uow=tx)
            agent = AgentDefinition.model_validate(
                await tx.get("agents", agent_id)
            )
            if (agent.status == "revoked" and status != "revoked") or (
                agent.status == "disabled" and status == "archived"
            ):
                raise LifecycleError("AGENT_UNAVAILABLE")
            if agent.revision != expected_revision:
                raise LifecycleError("REVISION_CONFLICT")
            await tx.fence_catalog(await tx.catalog_revision())
            changed = agent.model_copy(
                update={"status": status, "revision": expected_revision + 1}
            )
            await tx.save(
                "agents",
                agent_id,
                changed.model_dump(mode="json"),
                expected_revision,
            )
            deployment = await tx.maybe_get("deployments", agent_id)
            if deployment:
                deployment["status"] = (
                    "active" if status == "published" else status
                )
                await tx.save(
                    "deployments", agent_id, deployment, deployment["revision"]
                )
            return changed
