"""Build batches track independent agents and atomically publish selections."""

from typing import Mapping, Sequence

from ..contracts import (
    AgentBuildBatch,
    BuildBatchStatus,
    BuildItem,
    BuildItemStatus,
    BuildSource,
    Scope,
)
from ._models import (
    AgentDefinition,
    AgentDraft,
    LifecycleError,
    PublishSelection,
    canonical_hash,
    new_id,
    now,
)


class BatchMixin:
    async def delete_batch_history(
        self, scope: Scope, batch_id: str, expected_revision: int
    ) -> None:
        await self.identity.check_scope_active(scope)
        async with self.repository.transaction(scope) as tx:
            batch = AgentBuildBatch.model_validate(
                await tx.get("batches", batch_id)
            )
            if batch.revision != expected_revision:
                raise LifecycleError("REVISION_CONFLICT")
            # Fence the batch with CAS before deleting only history rows.
            await tx.save(
                "batches",
                batch_id,
                batch.model_dump(mode="json"),
                expected_revision,
            )
            for item in batch.items:
                await tx.delete_batch_record(
                    "batch_items", canonical_hash([batch_id, item.item_id])
                )
            await tx.delete_batch_record("batches", batch_id)

    async def create_batch(
        self, scope: Scope, build_session_id: str, items: Sequence[BuildItem]
    ) -> AgentBuildBatch:
        await self.identity.check_scope_active(scope)
        if (
            not items
            or len({x.item_id for x in items}) != len(items)
            or len({x.agent_key for x in items}) != len(items)
        ):
            raise LifecycleError("INVALID_BATCH_ITEMS", 422)
        request_hash = canonical_hash(
            [item.model_dump(mode="json") for item in items]
        )
        receipt_id = canonical_hash(
            ["batch", scope.model_dump(), build_session_id]
        )
        checked = []
        for item in items:
            if item.source == BuildSource.REUSE:
                candidate = await self.get_candidate(
                    scope, item.reuse_agent_id, item.reuse_version_id
                )
                agent = AgentDefinition.model_validate(candidate["agent"])
                if (
                    agent.status != "published"
                    or agent.active_version_id != item.reuse_version_id
                ):
                    raise LifecycleError("REUSE_DECISION_STALE")
                version = await self.get_version(scope, item.reuse_version_id)
                await self.require_version_compatible(scope, version)
                item = item.model_copy(
                    update={"status": BuildItemStatus.COMPLETED_REUSED}
                )
            elif item.draft_id:
                raise LifecycleError("ATTACH_DRAFT_EXPLICITLY", 422)
            else:
                item = item.model_copy(
                    update={"status": BuildItemStatus.PROPOSED}
                )
            checked.append(item)
        timestamp = now()
        batch = AgentBuildBatch(
            batch_id=new_id(),
            build_session_id=build_session_id,
            revision=1,
            items=tuple(checked),
            status=self._batch_status(checked),
            created_at=timestamp,
            updated_at=timestamp,
        )
        async with self.repository.transaction(scope) as tx:
            receipt = await tx.maybe_get("receipts", receipt_id)
            if receipt:
                if receipt["request_hash"] != request_hash:
                    raise LifecycleError("IDEMPOTENCY_CONFLICT")
                return AgentBuildBatch.model_validate(
                    await tx.get("batches", receipt["batch_id"])
                )
            for item in checked:
                if item.source == BuildSource.REUSE:
                    agent = AgentDefinition.model_validate(
                        await tx.get("agents", item.reuse_agent_id)
                    )
                    if (
                        agent.status != "published"
                        or agent.active_version_id != item.reuse_version_id
                    ):
                        raise LifecycleError("REUSE_DECISION_STALE")
            await tx.insert(
                "batches", batch.batch_id, batch.model_dump(mode="json")
            )
            for item in batch.items:
                await tx.insert(
                    "batch_items",
                    canonical_hash([batch.batch_id, item.item_id]),
                    {
                        "batch_id": batch.batch_id,
                        "item": item.model_dump(mode="json"),
                    },
                )
            await tx.insert(
                "receipts",
                receipt_id,
                {"request_hash": request_hash, "batch_id": batch.batch_id},
            )
            return batch

    @staticmethod
    def _batch_status(items: Sequence[BuildItem]) -> BuildBatchStatus:
        if all(
            x.status
            in (BuildItemStatus.COMPLETED_REUSED, BuildItemStatus.PUBLISHED)
            for x in items
        ):
            return BuildBatchStatus.COMPLETED
        if all(
            x.status
            in (
                BuildItemStatus.COMPLETED_REUSED,
                BuildItemStatus.PUBLISHED,
                BuildItemStatus.PASSED,
            )
            for x in items
        ):
            return BuildBatchStatus.READY
        if any(
            x.status
            in (
                BuildItemStatus.PASSED,
                BuildItemStatus.COMPLETED_REUSED,
                BuildItemStatus.PUBLISHED,
            )
            for x in items
        ):
            return BuildBatchStatus.PARTIALLY_READY
        return BuildBatchStatus.RUNNING

    async def get_batch(self, scope: Scope, batch_id: str) -> AgentBuildBatch:
        batch = AgentBuildBatch.model_validate(
            await self.repository.get(scope, "batches", batch_id)
        )
        items = []
        async with self.repository.transaction(scope) as tx:
            evaluations = await tx.list("evaluations")
            versions = await tx.list("versions")
        for item in batch.items:
            if item.draft_id and item.status != BuildItemStatus.PUBLISHED:
                draft = await self.get_draft(scope, item.draft_id)
                if any(
                    version["evaluation_id"] == ev["report"]["evaluation_id"]
                    for ev in evaluations
                    if ev["snapshot"]["draft_id"] == item.draft_id
                    for version in versions
                ):
                    item = item.model_copy(
                        update={"status": BuildItemStatus.PUBLISHED}
                    )
                else:
                    matching = [
                        ev
                        for ev in evaluations
                        if ev["snapshot"]["draft_id"] == item.draft_id
                        and ev["snapshot"]["draft_revision"] == draft.revision
                    ]
                    matching.sort(key=lambda ev: ev["snapshot"]["created_at"])
                    if matching:
                        report = matching[-1]["report"]
                        status = {
                            "passed": BuildItemStatus.PASSED,
                            "failed": BuildItemStatus.FAILED,
                            "error": BuildItemStatus.FAILED,
                            "cancelled": BuildItemStatus.BLOCKED,
                        }.get(
                            report["status"],
                            BuildItemStatus.EVALUATING,
                        )
                        item = item.model_copy(
                            update={
                                "status": status,
                                "evaluation_id": report["evaluation_id"],
                            }
                        )
                    else:
                        item = item.model_copy(
                            update={
                                "status": BuildItemStatus.VALIDATING,
                                "evaluation_id": None,
                            }
                        )
            items.append(item)
        return batch.model_copy(
            update={"items": tuple(items), "status": self._batch_status(items)}
        )

    async def attach_draft(
        self,
        scope: Scope,
        batch_id: str,
        item_id: str,
        draft_id: str,
        expected_revision: int,
    ) -> AgentBuildBatch:
        async with self.repository.transaction(scope) as tx:
            batch = AgentBuildBatch.model_validate(
                await tx.get("batches", batch_id)
            )
            draft = AgentDraft.model_validate(await tx.get("drafts", draft_id))
            item = next((x for x in batch.items if x.item_id == item_id), None)
            if batch.revision != expected_revision:
                raise LifecycleError("REVISION_CONFLICT")
            if (
                item is None
                or item.source == BuildSource.REUSE
                or draft.batch_id != batch_id
                or draft.manifest.spec.agent_key != item.agent_key
                or (item.draft_id is not None and item.draft_id != draft_id)
            ):
                raise LifecycleError("BATCH_ITEM_MISMATCH")
            if item.source == BuildSource.REVISE and (
                draft.agent_id != item.target_agent_id
                or draft.source_version_id != item.source_version_id
            ):
                raise LifecycleError("BATCH_ITEM_MISMATCH")
            changed_item = item.model_copy(
                update={
                    "draft_id": draft_id,
                    "status": BuildItemStatus.VALIDATING,
                }
            )
            changed = batch.model_copy(
                update={
                    "items": tuple(
                        changed_item if x.item_id == item_id else x
                        for x in batch.items
                    ),
                    "revision": expected_revision + 1,
                    "updated_at": now(),
                }
            )
            await tx.save(
                "batches",
                batch_id,
                changed.model_dump(mode="json"),
                expected_revision,
            )
            await tx.save(
                "batch_items",
                canonical_hash([batch_id, item_id]),
                {
                    "batch_id": batch_id,
                    "item": changed_item.model_dump(mode="json"),
                },
                (
                    await tx.get(
                        "batch_items", canonical_hash([batch_id, item_id])
                    )
                ).get("revision", 1),
            )
            return changed

    async def publish_selected(
        self,
        scope: Scope,
        batch_id: str,
        expected_revision: int,
        selections: Sequence[Mapping[str, object]],
    ) -> AgentBuildBatch:
        await self.identity.check_scope_active(scope)
        parsed = tuple(PublishSelection.model_validate(x) for x in selections)
        if not parsed or len({x.draft_id for x in parsed}) != len(parsed):
            raise LifecycleError("INVALID_PUBLISH_SELECTION", 422)
        receipt_id = canonical_hash(
            [
                "batch-publish",
                scope.model_dump(),
                batch_id,
                expected_revision,
                [x.model_dump(mode="json") for x in parsed],
            ]
        )
        async with self.repository.transaction(scope) as tx:
            receipt = await tx.maybe_get("receipts", receipt_id)
            if receipt:
                return AgentBuildBatch.model_validate(receipt["batch"])
        records = [
            await self._preflight(scope, selection) for selection in parsed
        ]
        async with self.repository.transaction(scope) as tx:
            batch = AgentBuildBatch.model_validate(
                await tx.get("batches", batch_id)
            )
            if batch.revision != expected_revision:
                raise LifecycleError("REVISION_CONFLICT")
            selected_ids = {x.draft_id for x in parsed}
            if not selected_ids.issubset(
                {
                    x.draft_id
                    for x in batch.items
                    if x.source != BuildSource.REUSE
                }
            ):
                raise LifecycleError("BATCH_ITEM_MISMATCH")
            await self._publish_tx(
                tx, parsed, records, scope.manager_account_id
            )
            items = tuple(
                (
                    item.model_copy(
                        update={"status": BuildItemStatus.PUBLISHED}
                    )
                    if item.draft_id in selected_ids
                    else item
                )
                for item in batch.items
            )
            changed = batch.model_copy(
                update={
                    "items": items,
                    "revision": batch.revision + 1,
                    "status": self._batch_status(items),
                    "updated_at": now(),
                }
            )
            await tx.save(
                "batches",
                batch_id,
                changed.model_dump(mode="json"),
                batch.revision,
            )
            for item in items:
                if item.draft_id in selected_ids:
                    item_key = canonical_hash([batch_id, item.item_id])
                    prior = await tx.get("batch_items", item_key)
                    item_revision = prior.get("revision", 1)
                    await tx.save(
                        "batch_items",
                        item_key,
                        {
                            "batch_id": batch_id,
                            "item": item.model_dump(mode="json"),
                            "revision": item_revision + 1,
                        },
                        item_revision,
                    )
            await tx.insert(
                "receipts",
                receipt_id,
                {"batch": changed.model_dump(mode="json")},
            )
            return changed
