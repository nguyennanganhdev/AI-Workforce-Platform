"""Behavioral SQL/port tests for PTA-01 through PTA-13."""

from typing import Any
import asyncio
import os
from pathlib import Path
import tempfile
import unittest

from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from agentscope.app.workforce.contracts import (
    AgentReusePort,
    BuildBatchPort,
    BuildItem,
    BuildItemStatus,
    BuildSource,
    DraftPort,
    EvaluationStatus,
    PublishedCatalogPort,
    ReuseAction,
    ReuseDecision,
)
from agentscope.app.workforce.lifecycle import create_router, metadata
from agentscope.app.workforce.lifecycle._models import (
    LifecycleError,
    PublishSelection,
    canonical_hash,
    new_id,
)
from tests.workforce.lifecycle._fakes import (
    Harness,
    job_metadata,
    jobs_table,
    manifest,
    scope,
)


def selection(draft: Any, evaluation: Any) -> PublishSelection:
    return PublishSelection(
        draft_id=draft.draft_id,
        expected_revision=draft.revision,
        manifest_hash=draft.manifest_hash,
        evaluation_id=evaluation.report.evaluation_id,
    )


class SQLLifecycleCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.schema = "wf_lifecycle_test_" + new_id().replace("-", "")
        self.pg_url = os.environ.get("WORKFORCE_LIFECYCLE_TEST_DSN")
        self.url = (
            self.pg_url
            or f"sqlite+aiosqlite:///{Path(self.temp.name) / 'lifecycle.db'}"
        )
        if self.pg_url:
            bootstrap = create_async_engine(self.url)
            async with bootstrap.begin() as connection:
                await connection.execute(
                    text(f'CREATE SCHEMA "{self.schema}"')
                )
            await bootstrap.dispose()
            self.engine = create_async_engine(
                self.url,
                connect_args={
                    "server_settings": {"search_path": self.schema},
                },
            )
        else:
            self.engine = create_async_engine(self.url)
        async with self.engine.begin() as connection:
            await connection.run_sync(metadata.create_all)
            await connection.run_sync(job_metadata.create_all)
        self.factory = async_sessionmaker(self.engine, expire_on_commit=False)
        self.harness = Harness(self.factory)
        self.service = self.harness.service

    async def asyncTearDown(self) -> None:
        await self.engine.dispose()
        if self.pg_url:
            bootstrap = create_async_engine(self.url)
            async with bootstrap.begin() as connection:
                await connection.execute(
                    text(f'DROP SCHEMA "{self.schema}" CASCADE')
                )
            await bootstrap.dispose()
        self.temp.cleanup()

    async def publish_draft(self, draft: Any) -> Any:
        evaluation = await self.harness.evaluated(draft)
        self.assertEqual(evaluation.report.status, EvaluationStatus.PASSED)
        versions = await self.service.publish(
            scope(), [selection(draft, evaluation)], new_id(), "manager-A"
        )
        return versions[0], evaluation


class LifecycleTests(SQLLifecycleCase):
    async def test_shared_ports_are_implemented(self) -> None:
        for port in (
            DraftPort,
            AgentReusePort,
            BuildBatchPort,
            PublishedCatalogPort,
        ):
            self.assertIsInstance(self.service, port)

    async def test_canonical_hash_ignores_mapping_order(self) -> None:
        self.assertEqual(
            canonical_hash({"a": 1, "b": 2}), canonical_hash({"b": 2, "a": 1})
        )

    async def test_publish_keeps_evaluated_id_and_idempotency(self) -> None:
        draft = await self.harness.draft()
        evaluation = await self.harness.evaluated(draft)
        chosen = selection(draft, evaluation)
        first = await self.service.publish(
            scope(), [chosen], "publish-key", "manager-A"
        )
        second = await self.service.publish(
            scope(), [chosen], "publish-key", "manager-A"
        )
        self.assertEqual(first, second)
        self.assertEqual(
            first[0].version_id, evaluation.snapshot.candidate_version_id
        )
        self.assertEqual(first[0].manifest_hash, draft.manifest_hash)
        self.assertEqual(
            len(await self.service.list_candidates(scope(), ["lookup"])), 1
        )

    async def test_edit_invalidates_eval_even_when_hash_reverts(self) -> None:
        draft = await self.harness.draft()
        evaluation = await self.harness.evaluated(draft)
        changed = draft.manifest.model_copy(
            update={
                "spec": draft.manifest.spec.model_copy(
                    update={"system_prompt": "New prompt"}
                )
            }
        )
        newer = await self.service.update_draft(
            scope(),
            draft.draft_id,
            draft.revision,
            changed,
            draft.reuse_decision,
        )
        await self.service.update_draft(
            scope(),
            newer.draft_id,
            newer.revision,
            draft.manifest,
            draft.reuse_decision,
        )
        with self.assertRaisesRegex(LifecycleError, "EVALUATION_STALE"):
            await self.service.publish(
                scope(), [selection(draft, evaluation)], new_id(), "manager-A"
            )

    async def test_publish_without_pass_is_rejected(self) -> None:
        draft = await self.harness.draft()
        evaluation = await self.service.start_evaluation(
            scope(), draft.draft_id, 1, "lifecycle-patterns-v1", "eval"
        )
        with self.assertRaisesRegex(LifecycleError, "EVALUATION_NOT_PASSED"):
            await self.service.publish(
                scope(), [selection(draft, evaluation)], "publish", "manager-A"
            )

    async def test_registry_drift_blocks_publish(self) -> None:
        draft = await self.harness.draft()
        evaluation = await self.harness.evaluated(draft)
        self.harness.registry.schema_hash = "drift"
        with self.assertRaisesRegex(LifecycleError, "EVALUATION_STALE"):
            await self.service.publish(
                scope(), [selection(draft, evaluation)], new_id(), "manager-A"
            )

    async def test_resource_and_runtime_drift_block_publish(self) -> None:
        draft = await self.harness.draft()
        evaluation = await self.harness.evaluated(draft)
        self.harness.resources.revision = 2
        with self.assertRaisesRegex(LifecycleError, "EVALUATION_STALE"):
            await self.service.publish(
                scope(), [selection(draft, evaluation)], new_id(), "manager-A"
            )
        self.harness.resources.revision = 1
        self.service.runtime_profile["version"] = "runtime-v2"
        with self.assertRaisesRegex(LifecycleError, "EVALUATION_STALE"):
            await self.service.publish(
                scope(), [selection(draft, evaluation)], new_id(), "manager-A"
            )

    async def test_manager_isolation_in_same_area(self) -> None:
        draft = await self.harness.draft()
        version, _ = await self.publish_draft(draft)
        self.assertEqual(
            await self.service.list_candidates(scope("manager-B"), ["lookup"]),
            (),
        )
        check = await self.service.find_candidates(
            scope("manager-B"), draft.manifest.business_profile
        )
        self.assertEqual(check.candidates, ())
        for kind, identifier in (
            ("drafts", draft.draft_id),
            ("versions", version.version_id),
            ("agents", draft.agent_id),
        ):
            with self.assertRaisesRegex(LifecycleError, "RESOURCE_NOT_FOUND"):
                await self.service.repository.get(
                    scope("manager-B"), kind, identifier
                )
        other = await self.harness.draft(owner=scope("manager-B"))
        self.assertNotEqual(other.agent_id, draft.agent_id)

    async def test_duplicate_build_and_resume_pending(self) -> None:
        value = manifest()
        checks = [
            await self.service.find_candidates(scope(), value.business_profile)
            for _ in range(2)
        ]
        decisions = [
            ReuseDecision(
                agent_key="hotel",
                action=ReuseAction.CREATE,
                reuse_check_id=check.reuse_check_id,
                reason="New business",
                expected_catalog_revision=check.agent_catalog_revision,
            )
            for check in checks
        ]
        results = await asyncio.gather(
            *(
                self.service.create_draft(scope(), value, decision)
                for decision in decisions
            ),
            return_exceptions=True,
        )
        self.assertEqual(
            sum(not isinstance(result, Exception) for result in results), 1
        )
        check = await self.service.find_candidates(
            scope(), value.business_profile
        )
        self.assertEqual(check.recommended_action, ReuseAction.RESUME)
        candidate = check.candidates[0]
        decision = ReuseDecision(
            agent_key="hotel",
            action=ReuseAction.RESUME,
            agent_id=candidate.agent_id,
            draft_id=candidate.draft_id,
            reuse_check_id=check.reuse_check_id,
            reason="Resume pending build",
            expected_catalog_revision=check.agent_catalog_revision,
        )
        resumed = await self.service.create_draft(scope(), value, decision)
        self.assertEqual(resumed.draft_id, candidate.draft_id)
        self.assertEqual(
            len((await self.service.list_agents(scope()))["items"]), 1
        )

    async def test_two_edits_do_not_lose_update(self) -> None:
        draft = await self.harness.draft()
        results = await asyncio.gather(
            *(
                self.service.update_draft(
                    scope(),
                    draft.draft_id,
                    1,
                    draft.manifest,
                    draft.reuse_decision,
                )
                for _ in range(2)
            ),
            return_exceptions=True,
        )
        self.assertEqual(
            sum(not isinstance(result, Exception) for result in results), 1
        )
        self.assertEqual(
            (await self.service.get_draft(scope(), draft.draft_id)).revision, 2
        )

    async def test_reuse_batch_does_not_create_agent_or_version(self) -> None:
        draft = await self.harness.draft()
        version, _ = await self.publish_draft(draft)
        check = await self.service.find_candidates(
            scope(), draft.manifest.business_profile
        )
        self.assertEqual(check.recommended_action, ReuseAction.REUSE)
        item = BuildItem(
            item_id=new_id(),
            agent_key="hotel",
            source=BuildSource.REUSE,
            reuse_action=ReuseAction.REUSE,
            reuse_agent_id=draft.agent_id,
            reuse_version_id=version.version_id,
            status=BuildItemStatus.PROPOSED,
        )
        batch = await self.service.create_batch(scope(), "reuse-build", [item])
        self.assertEqual(
            batch.items[0].status, BuildItemStatus.COMPLETED_REUSED
        )
        self.assertEqual(
            (
                await self.service.create_batch(scope(), "reuse-build", [item])
            ).batch_id,
            batch.batch_id,
        )
        self.assertEqual(
            len((await self.service.list_agents(scope()))["items"]), 1
        )
        self.assertEqual(
            len(
                (await self.service.version_history(scope(), draft.agent_id))[
                    "items"
                ]
            ),
            1,
        )

    async def test_batch_publish_stale_is_atomic_then_partial_selection(
        self,
    ) -> None:
        values = [manifest(), manifest("Car", "car")]
        items = [
            BuildItem(
                item_id=new_id(),
                agent_key=value.spec.agent_key,
                source=BuildSource.CREATE,
                reuse_action=ReuseAction.CREATE,
                spec=value.spec,
                status=BuildItemStatus.PROPOSED,
            )
            for value in values
        ]
        batch = await self.service.create_batch(scope(), "two-new", items)
        drafts, evaluations = [], []
        for item, value in zip(items, values):
            draft = await self.harness.draft(value, batch_id=batch.batch_id)
            batch = await self.service.attach_draft(
                scope(),
                batch.batch_id,
                item.item_id,
                draft.draft_id,
                batch.revision,
            )
            drafts.append(draft)
            evaluations.append(await self.harness.evaluated(draft))
        await self.service.update_draft(
            scope(),
            drafts[1].draft_id,
            1,
            drafts[1].manifest,
            drafts[1].reuse_decision,
        )
        selections = [
            selection(draft, ev).model_dump()
            for draft, ev in zip(drafts, evaluations)
        ]
        with self.assertRaisesRegex(LifecycleError, "EVALUATION_STALE"):
            await self.service.publish_selected(
                scope(), batch.batch_id, batch.revision, selections
            )
        self.assertEqual(await self.service.list_candidates(scope(), []), ())
        published = await self.service.publish_selected(
            scope(), batch.batch_id, batch.revision, selections[:1]
        )
        self.assertEqual(published.items[0].status, BuildItemStatus.PUBLISHED)
        self.assertNotEqual(
            published.items[1].status, BuildItemStatus.PUBLISHED
        )
        repeated = await self.service.publish_selected(
            scope(), batch.batch_id, batch.revision, selections[:1]
        )
        self.assertEqual(repeated, published)
        self.assertEqual(
            len(await self.service.list_candidates(scope(), [])), 1
        )

    async def test_eval_job_enqueue_failure_rolls_back(self) -> None:
        draft = await self.harness.draft()
        self.harness.jobs.fail = True
        with self.assertRaises(RuntimeError):
            await self.service.start_evaluation(
                scope(), draft.draft_id, 1, "lifecycle-patterns-v1", "key"
            )
        async with self.factory() as session:
            self.assertEqual(
                (
                    await session.execute(
                        select(func.count()).select_from(jobs_table)
                    )
                ).scalar(),
                0,
            )
        async with self.service.repository.transaction(scope()) as tx:
            self.assertEqual(await tx.list("evaluations"), [])

    async def test_eval_idempotency_payload_conflict(self) -> None:
        draft = await self.harness.draft()
        first = await self.service.start_evaluation(
            scope(), draft.draft_id, 1, "lifecycle-patterns-v1", "key"
        )
        second = await self.service.start_evaluation(
            scope(), draft.draft_id, 1, "lifecycle-patterns-v1", "key"
        )
        self.assertEqual(
            first.report.evaluation_id, second.report.evaluation_id
        )
        with self.assertRaisesRegex(LifecycleError, "IDEMPOTENCY_CONFLICT"):
            await self.service.start_evaluation(
                scope(), draft.draft_id, 2, "lifecycle-patterns-v1", "key"
            )

    async def test_validation_rejects_secret_roster_and_permission(
        self,
    ) -> None:
        value = manifest()
        spec = value.spec.model_copy(
            update={
                "model_config_ref": {
                    "model_id": "m",
                    "credential_ref": "c",
                    "api_key": "fake",
                },
                "collaboration_policy": {"roster": ["peer"]},
            }
        )
        report = await self.service.validator.validate(
            scope(), value.model_copy(update={"spec": spec})
        )
        self.assertFalse(report.valid)
        self.assertIn("INLINE_SECRET_FORBIDDEN", report.blockers)
        self.assertIn("FIXED_RUNTIME_ROSTER_FORBIDDEN", report.blockers)

    async def test_router_manager_scope_error_envelope_and_partner_denial(
        self,
    ) -> None:
        app = FastAPI()

        async def manager() -> Any:
            return scope()

        app.include_router(create_router(self.service, manager))
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/workforce/v1/drafts/foreign")
            self.assertEqual(response.status_code, 404)
            self.assertEqual(
                response.json()["error"]["code"], "RESOURCE_NOT_FOUND"
            )
            response = await client.get("/workforce/v1/agents")
            self.assertEqual(response.status_code, 200)

        async def deny_partner() -> Any:
            raise HTTPException(
                status_code=403, detail="Manager principal required"
            )

        partner_app = FastAPI()
        partner_app.include_router(create_router(self.service, deny_partner))
        async with AsyncClient(
            transport=ASGITransport(app=partner_app), base_url="http://test"
        ) as client:
            self.assertEqual(
                (await client.get("/workforce/v1/agents")).status_code, 403
            )
