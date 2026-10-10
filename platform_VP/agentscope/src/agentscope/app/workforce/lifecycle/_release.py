"""Atomic explicit publish, matching the exact evaluated candidate version."""

from typing import Any, Sequence, Tuple

from ..contracts import EvaluationStatus, Scope
from ._graders import GATE_V1, grade_suite
from ._models import (
    AgentDefinition,
    AgentDraft,
    Deployment,
    EvaluationRecord,
    LifecycleError,
    PublishedVersion,
    PublishSelection,
    canonical_hash,
    new_id,
    now,
)
from ._suites import grading_cases


class ReleaseMixin:
    async def _preflight(
        self, scope: Scope, selection: PublishSelection
    ) -> EvaluationRecord:
        record = await self.get_evaluation(scope, selection.evaluation_id)
        validation = await self.validator.validate(
            scope, record.snapshot.manifest
        )
        suite = self.suites.get(record.report.suite_version)
        passed, _, failures = grade_suite(
            grading_cases(suite, record.validation.tool_snapshots),
            record.report.cases,
            record.gate_config,
        )
        if (
            record.report.status != EvaluationStatus.PASSED
            or not passed
            or failures
            or canonical_hash(record.gate_config) != canonical_hash(GATE_V1)
        ):
            raise LifecycleError("EVALUATION_NOT_PASSED")
        if (
            not validation.valid
            or validation != record.validation
            or suite.content_hash != record.suite_hash
            or canonical_hash(self.runtime_profile)
            != record.report.runtime_profile_hash
            or canonical_hash(record.test_context)
            != record.snapshot.test_context_hash
        ):
            raise LifecycleError("EVALUATION_STALE")
        return record

    async def _publish_tx(
        self,
        tx: Any,
        selections: Sequence[PublishSelection],
        records: Sequence[EvaluationRecord],
        published_by: str,
    ) -> Tuple[PublishedVersion, ...]:
        await self.identity.check_scope_active(tx.scope, uow=tx)
        prepared = []
        for selection, prefetched in zip(selections, records):
            draft = AgentDraft.model_validate(
                await tx.get("drafts", selection.draft_id)
            )
            record = EvaluationRecord.model_validate(
                await tx.get("evaluations", selection.evaluation_id)
            )
            snapshot = record.snapshot
            agent = AgentDefinition.model_validate(
                await tx.get("agents", draft.agent_id)
            )
            if agent.status in ("disabled", "revoked", "archived"):
                raise LifecycleError("AGENT_UNAVAILABLE")
            if (
                record.revision != prefetched.revision
                or record != prefetched
                or draft.revision != selection.expected_revision
                or draft.manifest_hash != selection.manifest_hash
                or canonical_hash(draft.manifest) != selection.manifest_hash
                or snapshot.draft_id != draft.draft_id
                or snapshot.agent_id != draft.agent_id
                or snapshot.draft_revision != draft.revision
                or snapshot.manifest_hash != draft.manifest_hash
                or snapshot.source_draft_hash != draft.manifest_hash
                or snapshot.manifest != draft.manifest
                or agent.draft_id != draft.draft_id
            ):
                raise LifecycleError("EVALUATION_STALE")
            prepared.append((draft, record, agent))
        await tx.fence_catalog(await tx.catalog_revision())
        versions = []
        for draft, record, agent in prepared:
            version = PublishedVersion(
                version_id=record.snapshot.candidate_version_id,
                agent_id=draft.agent_id,
                scope=tx.scope,
                manifest=record.snapshot.manifest,
                manifest_hash=record.snapshot.manifest_hash,
                source_draft_hash=draft.manifest_hash,
                evaluation_id=record.report.evaluation_id,
                published_by=published_by,
                published_at=now(),
                protocol_refs=record.protocol_refs,
                policy_snapshot=record.policy_snapshot,
                validation=record.validation,
            )
            await tx.insert(
                "versions", version.version_id, version.model_dump(mode="json")
            )
            event_id = new_id()
            await tx.insert(
                "release_events",
                event_id,
                {
                    "agent_id": agent.agent_id,
                    "version_id": version.version_id,
                    "event_type": "agent.published",
                    "published_by": published_by,
                    "published_at": version.published_at.isoformat(),
                },
            )
            await self.jobs.enqueue(
                tx.scope,
                "workforce.lifecycle.catalog_changed",
                {
                    "event_id": event_id,
                    "agent_id": agent.agent_id,
                    "version_id": version.version_id,
                },
                f"release:{event_id}",
                uow=tx,
            )
            deployment_id = agent.agent_id
            existing = await tx.maybe_get("deployments", deployment_id)
            deployment = Deployment(
                deployment_id=deployment_id,
                agent_id=agent.agent_id,
                scope=tx.scope,
                active_version_id=version.version_id,
                revision=existing["revision"] + 1 if existing else 1,
            )
            if existing:
                await tx.save(
                    "deployments",
                    deployment_id,
                    deployment.model_dump(mode="json"),
                    existing["revision"],
                )
            else:
                await tx.insert(
                    "deployments",
                    deployment_id,
                    deployment.model_dump(mode="json"),
                )
            changed = agent.model_copy(
                update={
                    "active_version_id": version.version_id,
                    "draft_id": None,
                    "status": "published",
                    "revision": agent.revision + 1,
                    "name": draft.manifest.spec.name,
                    "business_profile": draft.manifest.business_profile,
                }
            )
            await tx.save(
                "agents",
                agent.agent_id,
                changed.model_dump(mode="json"),
                agent.revision,
            )
            versions.append(version)
        return tuple(versions)

    async def publish(
        self,
        scope: Scope,
        selections: Sequence[PublishSelection],
        idempotency_key: str,
        published_by: str,
    ) -> Tuple[PublishedVersion, ...]:
        await self.identity.check_scope_active(scope)
        if published_by != scope.manager_account_id:
            raise LifecycleError("PUBLISH_ACTOR_MISMATCH", 403)
        if (
            not selections
            or len({x.draft_id for x in selections}) != len(selections)
            or not idempotency_key
        ):
            raise LifecycleError("INVALID_PUBLISH_SELECTION", 422)
        request_hash = canonical_hash(
            [x.model_dump(mode="json") for x in selections]
        )
        receipt_id = canonical_hash(
            ["publish", scope.model_dump(), idempotency_key]
        )
        async with self.repository.transaction(scope) as tx:
            receipt = await tx.maybe_get("receipts", receipt_id)
            if receipt:
                if receipt["request_hash"] != request_hash:
                    raise LifecycleError("IDEMPOTENCY_CONFLICT")
                return tuple(
                    [
                        PublishedVersion.model_validate(
                            await tx.get("versions", x)
                        )
                        for x in receipt["version_ids"]
                    ]
                )
        records = [
            await self._preflight(scope, selection) for selection in selections
        ]
        async with self.repository.transaction(scope) as tx:
            versions = await self._publish_tx(
                tx, selections, records, published_by
            )
            await tx.insert(
                "receipts",
                receipt_id,
                {
                    "request_hash": request_hash,
                    "version_ids": [x.version_id for x in versions],
                },
            )
            return versions
