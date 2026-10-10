"""Draft creation/editing preserves identity and invalidates stale
evaluation."""

from typing import Optional

from ..contracts import (
    AgentManifest,
    BuildSource,
    ReuseAction,
    ReuseDecision,
    Scope,
)
from ._deduplication import business_key
from ._models import (
    AgentDefinition,
    AgentDraft,
    LifecycleError,
    ValidationReport,
    canonical_hash,
    new_id,
    now,
)


class DraftMixin:
    async def create_draft(
        self,
        scope: Scope,
        manifest: AgentManifest,
        reuse_decision: ReuseDecision,
        batch_id: Optional[str] = None,
    ) -> AgentDraft:
        return await self._create_draft(
            scope, manifest, reuse_decision, batch_id
        )

    async def _create_draft(
        self,
        scope: Scope,
        manifest: AgentManifest,
        reuse_decision: ReuseDecision,
        batch_id: Optional[str],
        legacy_agent_id: Optional[str] = None,
    ) -> AgentDraft:
        await self.identity.check_scope_active(scope)
        if reuse_decision.agent_key != manifest.spec.agent_key:
            raise LifecycleError("AGENT_KEY_MISMATCH", 422)
        if reuse_decision.action == ReuseAction.REUSE:
            raise LifecycleError("REUSE_DOES_NOT_CREATE_DRAFT", 422)
        async with self.repository.transaction(scope) as tx:
            await self.identity.check_scope_active(scope, uow=tx)
            agent = await self._decision(
                tx, manifest.business_profile, reuse_decision
            )
            if reuse_decision.action == ReuseAction.RESUME:
                return AgentDraft.model_validate(
                    await tx.get("drafts", reuse_decision.draft_id)
                )
            if agent and agent.draft_id:
                raise LifecycleError(
                    "AGENT_BUILD_IN_PROGRESS",
                    details={"draft_id": agent.draft_id},
                )
            if batch_id:
                batch = await tx.get("batches", batch_id)
                item = next(
                    (
                        item
                        for item in batch["items"]
                        if item["agent_key"] == manifest.spec.agent_key
                    ),
                    None,
                )
                if item is None or item["source"] == BuildSource.REUSE:
                    raise LifecycleError("BATCH_ITEM_MISMATCH")
                if (
                    item["source"] == BuildSource.CREATE
                    and reuse_decision.action != ReuseAction.CREATE
                ):
                    raise LifecycleError("BATCH_ITEM_MISMATCH")
                if item["source"] == BuildSource.REVISE and (
                    reuse_decision.action != ReuseAction.REVISE
                    or item["target_agent_id"] != reuse_decision.agent_id
                    or item["source_version_id"] != reuse_decision.version_id
                ):
                    raise LifecycleError("BATCH_ITEM_MISMATCH")
            await tx.fence_catalog(reuse_decision.expected_catalog_revision)
            timestamp = now()
            draft_id = new_id()
            if agent is None:
                agent = AgentDefinition(
                    agent_id=new_id(),
                    scope=scope,
                    name=manifest.spec.name,
                    business_key=business_key(manifest.business_profile),
                    business_profile=manifest.business_profile,
                    revision=1,
                    draft_id=draft_id,
                    legacy_agent_id=legacy_agent_id,
                )
                await tx.insert(
                    "agents", agent.agent_id, agent.model_dump(mode="json")
                )
            else:
                changed = agent.model_copy(
                    update={
                        "draft_id": draft_id,
                        "revision": agent.revision + 1,
                    }
                )
                await tx.save(
                    "agents",
                    agent.agent_id,
                    changed.model_dump(mode="json"),
                    agent.revision,
                )
            draft = AgentDraft(
                draft_id=draft_id,
                agent_id=agent.agent_id,
                scope=scope,
                revision=1,
                manifest=manifest,
                manifest_hash=canonical_hash(manifest),
                reuse_decision=reuse_decision,
                batch_id=batch_id,
                source_version_id=reuse_decision.version_id,
                created_at=timestamp,
                updated_at=timestamp,
            )
            await tx.insert("drafts", draft_id, draft.model_dump(mode="json"))
            return draft

    async def get_draft(self, scope: Scope, draft_id: str) -> AgentDraft:
        return AgentDraft.model_validate(
            await self.repository.get(scope, "drafts", draft_id)
        )

    async def update_draft(
        self,
        scope: Scope,
        draft_id: str,
        expected_revision: int,
        manifest: AgentManifest,
        reuse_decision: ReuseDecision,
    ) -> AgentDraft:
        await self.identity.check_scope_active(scope)
        async with self.repository.transaction(scope) as tx:
            await self.identity.check_scope_active(scope, uow=tx)
            draft = AgentDraft.model_validate(await tx.get("drafts", draft_id))
            if draft.revision != expected_revision:
                raise LifecycleError("REVISION_CONFLICT")
            agent = AgentDefinition.model_validate(
                await tx.get("agents", draft.agent_id)
            )
            if agent.status in ("archived", "disabled", "revoked"):
                raise LifecycleError("AGENT_UNAVAILABLE")
            if (
                agent.draft_id != draft_id
                or manifest.spec.agent_key != draft.manifest.spec.agent_key
                or reuse_decision != draft.reuse_decision
            ):
                raise LifecycleError("DRAFT_IDENTITY_MISMATCH")
            if business_key(manifest.business_profile) != agent.business_key:
                raise LifecycleError("BUSINESS_IDENTITY_MISMATCH")
            await tx.fence_catalog(await tx.catalog_revision())
            changed = draft.model_copy(
                update={
                    "manifest": manifest,
                    "manifest_hash": canonical_hash(manifest),
                    "revision": expected_revision + 1,
                    "validation_report": None,
                    "updated_at": now(),
                }
            )
            await tx.save(
                "drafts",
                draft_id,
                changed.model_dump(mode="json"),
                expected_revision,
            )
            changed_agent = agent.model_copy(
                update={
                    "business_profile": manifest.business_profile,
                    "revision": agent.revision + 1,
                }
            )
            await tx.save(
                "agents",
                agent.agent_id,
                changed_agent.model_dump(mode="json"),
                agent.revision,
            )
            return changed

    async def validate_draft(
        self, scope: Scope, draft_id: str
    ) -> ValidationReport:
        draft = await self.get_draft(scope, draft_id)
        report = await self.validator.validate(scope, draft.manifest)
        async with self.repository.transaction(scope) as tx:
            current = AgentDraft.model_validate(
                await tx.get("drafts", draft_id)
            )
            if current.revision != draft.revision:
                raise LifecycleError("REVISION_CONFLICT")
            # Validation is evidence, not a manifest edit; CAS still advances
            # revision.
            changed = current.model_copy(
                update={
                    "validation_report": report,
                    "revision": current.revision + 1,
                    "updated_at": now(),
                }
            )
            await tx.save(
                "drafts",
                draft_id,
                changed.model_dump(mode="json"),
                current.revision,
            )
        return report
