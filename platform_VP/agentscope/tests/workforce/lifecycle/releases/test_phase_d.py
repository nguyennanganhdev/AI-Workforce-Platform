"""D4 release/retention regressions over real C1/C2/C4/C5 SQL."""

import asyncio
from typing import Any
import unittest
from unittest.mock import patch

from sqlalchemy import select, update

from agentscope.app.workforce.lifecycle.async_evaluation import canonical_hash
from agentscope.app.workforce.lifecycle.async_evaluation._tables import case_runs, steps
from agentscope.app.workforce.lifecycle.releases import (
    SqlReleaseService,
    get_release_metadata,
)
from agentscope.app.workforce.lifecycle.releases._tables import (
    candidates,
    commands,
    deployments,
    versions,
)
from tests.workforce.lifecycle.async_evaluation.runtime_fixture import SqlCaseDriver
from tests.workforce.lifecycle.releases._fixture import ReleaseSupport, SCOPE


class ReleaseTests(ReleaseSupport, unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.driver = SqlCaseDriver()
        await self.driver.setup()
        await self.setup_release()

    async def asyncTearDown(self) -> None:
        await self.driver.cleanup()

    async def rows(self, table: Any) -> Any:
        async with self.driver.env.uows() as tx:
            return (await tx.execute(select(table))).mappings().all()

    async def test_explicit_publish_keeps_evaluated_id_hash_and_catalog_scope(
        self,
    ) -> None:
        self.assertFalse(await self.releases.list_candidates(SCOPE, ()))
        await self.evaluate()
        self.assertFalse(await self.releases.list_candidates(SCOPE, ()))
        result = await self.releases.publish_selected(
            SCOPE, [self.selection()], self.context, "publish"
        )
        self.assertEqual(result, (self.initial_snapshot.candidate_version_id,))
        version = await self.releases.get_version(SCOPE, result[0])
        self.assertEqual(version.frozen, self.frozen)
        self.assertEqual(version.manifest, self.initial_snapshot.manifest)
        self.assertEqual(version.published_by, SCOPE.manager_account_id)
        self.assertEqual(await self.releases.list_candidates(SCOPE, ()), (version,))
        self.assertFalse(await self.releases.list_candidates(SCOPE, ("missing",)))
        for field in SCOPE.model_dump():
            foreign = SCOPE.model_copy(update={field: "foreign"})
            self.assertFalse(await self.releases.list_candidates(foreign, ()))
            with self.assertRaises(KeyError):
                await self.releases.get_version(foreign, result[0])

    async def test_publish_replay_after_edit_archive_and_reload_has_no_new_version(
        self,
    ) -> None:
        version_id = await self.publish()
        new = self.next_candidate()
        await self.releases.stage_candidate(
            SCOPE, new, self.initial_snapshot.draft_revision
        )
        await self.releases.set_availability(
            SCOPE, self.initial_snapshot.agent_id, 1, archived=True, enabled=True
        )
        service = SqlReleaseService(
            self.driver.env.uows, self.validator, self.driver.env.ingress.identity
        )
        result = await service.publish_selected(
            SCOPE, [self.selection()], self.context, "publish-v1"
        )
        self.assertEqual(result, (version_id,))
        self.assertEqual(len(await self.rows(versions)), 1)
        with self.assertRaisesRegex(ValueError, "IDEMPOTENCY_CONFLICT"):
            await service.publish_selected(
                SCOPE,
                [self.selection(deployment_revision=2)],
                self.context,
                "publish-v1",
            )

    async def test_direct_publish_without_evaluation_is_rejected(self) -> None:
        with self.assertRaises(KeyError):
            await self.releases.publish_selected(
                SCOPE, [self.selection()], self.context, "publish"
            )
        self.assertFalse(await self.rows(versions))
        self.assertFalse(await self.rows(commands))

    async def test_candidate_staging_joins_canonical_uow_without_committing(
        self,
    ) -> None:
        second = self.next_candidate(agent_id="other", draft_id="draft-other")
        async with self.driver.env.uows() as tx:
            await self.releases.stage_candidate(SCOPE, second, uow=tx)
            staged = (await tx.execute(select(candidates))).mappings().all()
            self.assertEqual(len(staged), 2)
        self.assertEqual(len(await self.rows(candidates)), 1)
        self.assertEqual(len(await self.rows(deployments)), 1)

    async def test_membership_revoke_blocks_even_an_idempotent_publish_replay(
        self,
    ) -> None:
        await self.publish()

        async def revoked(*args: Any, **kwargs: Any) -> None:
            raise PermissionError("TEST-membership-revoked")

        with patch.object(self.releases.identity, "check_scope_active", revoked):
            with self.assertRaisesRegex(PermissionError, "membership-revoked"):
                await self.releases.publish_selected(
                    SCOPE, [self.selection()], self.context, "publish-v1"
                )
        self.assertEqual(len(await self.rows(versions)), 1)

    async def test_policy_payload_drift_blocks_passed_evaluation(self) -> None:
        await self.evaluate()
        self.validator.dependencies["policy"]["completion_condition"] = "new policy"
        with self.assertRaisesRegex(ValueError, "STALE_EVALUATION"):
            await self.releases.publish_selected(
                SCOPE, [self.selection()], self.context, "publish"
            )
        self.assertFalse(await self.rows(versions))

    async def test_empty_duplicate_and_multiple_drafts_per_agent_are_rejected(
        self,
    ) -> None:
        for selection in ([], [self.selection(), self.selection()]):
            with self.assertRaisesRegex(ValueError, "DISTINCT_RELEASE_SELECTIONS"):
                await self.releases.publish_selected(
                    SCOPE, selection, self.context, "publish"
                )
        other_draft = self.next_candidate(draft_id="same-agent-other-draft")
        await self.releases.stage_candidate(SCOPE, other_draft)
        with self.assertRaisesRegex(ValueError, "ONE_SELECTION_PER_AGENT"):
            await self.releases.publish_selected(
                SCOPE,
                [self.selection(), self.selection(frozen=other_draft)],
                self.context,
                "publish",
            )
        self.assertFalse(await self.rows(versions))

    async def test_edit_cas_blocks_stale_evaluation(self) -> None:
        await self.evaluate()
        new = self.next_candidate()
        await self.releases.stage_candidate(
            SCOPE, new, self.initial_snapshot.draft_revision
        )
        with self.assertRaisesRegex(ValueError, "DRAFT_REVISION_CONFLICT"):
            await self.releases.stage_candidate(
                SCOPE, new, self.initial_snapshot.draft_revision
            )
        with self.assertRaisesRegex(ValueError, "STALE_EVALUATION"):
            await self.releases.publish_selected(
                SCOPE, [self.selection(frozen=new)], self.context, "publish"
            )
        self.assertFalse(await self.rows(versions))

    async def test_server_runtime_suite_and_test_context_drift_block_publish(
        self,
    ) -> None:
        await self.evaluate()
        for field, value in (
            ("runtime_profile", {"model_ref": "changed"}),
            ("test_context", {"audience": "changed"}),
            (
                "suite",
                self.context.suite.model_copy(update={"suite_version": "changed"}),
            ),
        ):
            context = self.context.model_copy(update={field: value})
            with self.assertRaisesRegex(ValueError, "STALE_EVALUATION"):
                await self.releases.publish_selected(
                    SCOPE, [self.selection()], context, "publish-" + field
                )
        self.assertFalse(await self.rows(versions))

    async def test_protocol_revision_mapping_and_ordering_drift_block_publish(
        self,
    ) -> None:
        await self.evaluate()
        old = self.driver.protocol
        new = old.model_copy(
            update={
                "protocol_version": "2",
                "event_mode": "delta",
                "ordering": "provider_version",
            }
        )
        await self.driver.registry_provider.repository.publish(
            SCOPE, new, old.snapshot_ref
        )
        with self.assertRaisesRegex(ValueError, "VALIDATION_BLOCKED"):
            await self.releases.publish_selected(
                SCOPE, [self.selection()], self.context, "publish"
            )
        pinned = await self.driver.registry_provider.resolve_detail(
            SCOPE, old.snapshot_ref
        )
        self.assertEqual(pinned, old)
        self.assertFalse(await self.rows(versions))

    async def test_disabled_protocol_and_tool_block_publish(self) -> None:
        await self.evaluate()
        await self.driver.registry_provider.repository.set_enabled(
            SCOPE, "repair-v1", False, self.driver.protocol.snapshot_ref
        )
        with self.assertRaisesRegex(PermissionError, "PROTOCOL_DISABLED"):
            await self.releases.publish_selected(
                SCOPE, [self.selection()], self.context, "a"
            )
        await self.driver.registry_provider.repository.set_enabled(
            SCOPE, "repair-v1", True, self.driver.protocol.snapshot_ref
        )
        self.validator.tools = [
            self.validator.tools[0].model_copy(update={"available": False})
        ]
        with self.assertRaisesRegex(ValueError, "VALIDATION_BLOCKED"):
            await self.releases.publish_selected(
                SCOPE, [self.selection()], self.context, "b"
            )
        self.assertFalse(await self.rows(versions))

    async def test_cancelled_case_and_tampered_evidence_block_publish(self) -> None:
        await self.evaluate()
        async with self.driver.env.uows() as tx:
            await tx.execute(update(case_runs).values(cancelled=True))
            await tx.commit()
        with self.assertRaisesRegex(ValueError, "CANCELLED"):
            await self.releases.publish_selected(
                SCOPE, [self.selection()], self.context, "a"
            )
        async with self.driver.env.uows() as tx:
            await tx.execute(update(case_runs).values(cancelled=False))
            await tx.execute(update(steps).values(content_hash="tampered"))
            await tx.commit()
        with self.assertRaisesRegex(ValueError, "DRIFT"):
            await self.releases.publish_selected(
                SCOPE, [self.selection()], self.context, "b"
            )
        self.assertFalse(await self.rows(versions))

    async def test_selected_publish_is_atomic_with_one_stale_agent(self) -> None:
        await self.evaluate()
        second = self.next_candidate(agent_id="other-agent", draft_id="z-other-draft")
        await self.releases.stage_candidate(SCOPE, second)
        with self.assertRaisesRegex(ValueError, "STALE_EVALUATION"):
            await self.releases.publish_selected(
                SCOPE,
                [self.selection(), self.selection(frozen=second)],
                self.context,
                "both",
            )
        self.assertFalse(await self.rows(versions))
        self.assertFalse(await self.rows(commands))
        self.assertTrue(
            all(
                row["active_version_id"] is None for row in await self.rows(deployments)
            )
        )
        await self.releases.publish_selected(
            SCOPE, [self.selection()], self.context, "one"
        )
        self.assertEqual(len(await self.rows(versions)), 1)
        self.assertIsNone(
            (await self.releases.get_deployment(SCOPE, "other-agent"))[
                "active_version_id"
            ]
        )

    async def test_crash_before_commit_rolls_back_version_deployment_and_command(
        self,
    ) -> None:
        await self.evaluate()
        finish = self.releases._finish

        async def crash(*args: Any) -> None:
            raise asyncio.CancelledError("TEST process stopped before commit")

        with patch.object(self.releases, "_finish", crash):
            with self.assertRaises(asyncio.CancelledError):
                await self.releases.publish_selected(
                    SCOPE, [self.selection()], self.context, "publish"
                )
        self.assertFalse(await self.rows(versions))
        self.assertFalse(await self.rows(commands))
        self.releases._finish = finish
        result = await self.releases.publish_selected(
            SCOPE, [self.selection()], self.context, "publish"
        )
        self.assertEqual(result, (self.initial_snapshot.candidate_version_id,))

    async def test_commit_before_response_replay_returns_original_version(self) -> None:
        await self.evaluate()
        finish = self.releases._finish

        async def lost_response(*args: Any) -> None:
            await finish(*args)
            raise asyncio.CancelledError("TEST response lost after commit")

        with patch.object(self.releases, "_finish", lost_response):
            with self.assertRaises(asyncio.CancelledError):
                await self.releases.publish_selected(
                    SCOPE, [self.selection()], self.context, "publish"
                )
        result = await self.releases.publish_selected(
            SCOPE, [self.selection()], self.context, "publish"
        )
        self.assertEqual(result, (self.initial_snapshot.candidate_version_id,))
        self.assertEqual(len(await self.rows(versions)), 1)

    async def test_two_instances_publish_one_winner_without_duplicate_version(
        self,
    ) -> None:
        await self.evaluate()
        other = SqlReleaseService(
            self.driver.env.uows, self.validator, self.driver.env.ingress.identity
        )
        results = await asyncio.wait_for(
            asyncio.gather(
                self.releases.publish_selected(
                    SCOPE, [self.selection()], self.context, "one"
                ),
                other.publish_selected(SCOPE, [self.selection()], self.context, "two"),
                return_exceptions=True,
            ),
            timeout=10,
        )
        self.assertEqual(sum(isinstance(result, tuple) for result in results), 1)
        loser = next(result for result in results if isinstance(result, Exception))
        self.assertIsInstance(loser, ValueError)
        self.assertIn("DEPLOYMENT_REVISION_CONFLICT", str(loser))
        self.assertEqual(len(await self.rows(versions)), 1)

    async def test_concurrent_retry_same_command_returns_one_result(self) -> None:
        await self.evaluate()
        other = SqlReleaseService(
            self.driver.env.uows, self.validator, self.driver.env.ingress.identity
        )
        results = await asyncio.wait_for(
            asyncio.gather(
                self.releases.publish_selected(
                    SCOPE, [self.selection()], self.context, "same"
                ),
                other.publish_selected(SCOPE, [self.selection()], self.context, "same"),
            ),
            timeout=10,
        )
        self.assertEqual(results[0], results[1])
        self.assertEqual(len(await self.rows(versions)), 1)
        self.assertEqual(len(await self.rows(commands)), 1)

    async def test_edit_waits_for_publish_then_preserves_the_released_snapshot(
        self,
    ) -> None:
        await self.evaluate()
        entered, release, editing = asyncio.Event(), asyncio.Event(), asyncio.Event()
        validate = self.validator.validate
        second = self.next_candidate()

        async def paused(*args: Any) -> Any:
            entered.set()
            await asyncio.wait_for(release.wait(), timeout=5)
            return await validate(*args)

        async def edit() -> None:
            editing.set()
            await self.releases.stage_candidate(
                SCOPE, second, self.initial_snapshot.draft_revision
            )

        with patch.object(self.validator, "validate", paused):
            publish = asyncio.create_task(
                self.releases.publish_selected(
                    SCOPE, [self.selection()], self.context, "publish"
                )
            )
            editor = None
            try:
                await asyncio.wait_for(entered.wait(), timeout=5)
                editor = asyncio.create_task(edit())
                await asyncio.wait_for(editing.wait(), timeout=5)
                done, _ = await asyncio.wait({editor}, timeout=0.05)
                self.assertFalse(done)
                release.set()
                await asyncio.wait_for(asyncio.gather(publish, editor), timeout=10)
            finally:
                release.set()
                for task in (publish, editor):
                    if task is not None and not task.done():
                        task.cancel()
                await asyncio.gather(
                    *[task for task in (publish, editor) if task is not None],
                    return_exceptions=True
                )
        version = await self.releases.get_version(
            SCOPE, self.initial_snapshot.candidate_version_id
        )
        self.assertEqual(version.frozen, self.frozen)
        with self.assertRaisesRegex(ValueError, "DRAFT_REVISION_CONFLICT"):
            await self.releases.publish_selected(
                SCOPE, [self.selection()], self.context, "stale"
            )

    async def test_evaluation_cancel_waits_until_publish_commit(self) -> None:
        await self.evaluate()
        entered, release, cancelling = asyncio.Event(), asyncio.Event(), asyncio.Event()
        finish = self.releases._finish

        async def paused(*args: Any) -> None:
            entered.set()
            await asyncio.wait_for(release.wait(), timeout=5)
            await finish(*args)

        async def cancel() -> None:
            cancelling.set()
            async with self.driver.env.uows() as tx:
                await tx.execute(update(case_runs).values(cancelled=True))
                await tx.commit()

        with patch.object(self.releases, "_finish", paused):
            publish = asyncio.create_task(
                self.releases.publish_selected(
                    SCOPE, [self.selection()], self.context, "publish"
                )
            )
            cancellation = None
            try:
                await asyncio.wait_for(entered.wait(), timeout=5)
                cancellation = asyncio.create_task(cancel())
                await asyncio.wait_for(cancelling.wait(), timeout=5)
                done, _ = await asyncio.wait({cancellation}, timeout=0.05)
                self.assertFalse(done)
                release.set()
                await asyncio.wait_for(
                    asyncio.gather(publish, cancellation), timeout=10
                )
            finally:
                release.set()
                for task in (publish, cancellation):
                    if task is not None and not task.done():
                        task.cancel()
                await asyncio.gather(
                    *[task for task in (publish, cancellation) if task is not None],
                    return_exceptions=True
                )
        self.assertEqual(len(await self.rows(versions)), 1)
        self.assertTrue(all(row["cancelled"] for row in await self.rows(case_runs)))

    async def test_rollback_retains_versions_and_revalidates_compatibility(
        self,
    ) -> None:
        old_id = await self.publish()
        second = self.next_candidate()
        await self.releases.stage_candidate(
            SCOPE, second, self.initial_snapshot.draft_revision
        )
        await self.evaluate(second, "eval-v2")
        new_id = (
            await self.releases.publish_selected(
                SCOPE,
                [
                    self.selection(
                        frozen=second, evaluation_id="eval-v2", deployment_revision=1
                    )
                ],
                self.context,
                "publish-v2",
            )
        )[0]
        self.assertNotEqual(old_id, new_id)
        result = await self.releases.rollback(
            SCOPE, self.initial_snapshot.agent_id, old_id, 2, self.context, "rollback"
        )
        self.assertEqual(result, old_id)
        self.assertEqual(len(await self.rows(versions)), 2)
        self.assertEqual(
            await self.releases.rollback(
                SCOPE,
                self.initial_snapshot.agent_id,
                old_id,
                2,
                self.context,
                "rollback",
            ),
            old_id,
        )
        changed = self.context.model_copy(
            update={"runtime_profile": {"model": "changed"}}
        )
        with self.assertRaisesRegex(ValueError, "STALE_EVALUATION"):
            await self.releases.rollback(
                SCOPE,
                self.initial_snapshot.agent_id,
                new_id,
                3,
                changed,
                "bad-rollback",
            )
        self.assertEqual(
            (await self.releases.get_deployment(SCOPE, self.initial_snapshot.agent_id))[
                "active_version_id"
            ],
            old_id,
        )

    async def test_archive_allows_old_pin_disable_denies_without_deleting(self) -> None:
        version_id = await self.publish()
        agent_id = self.initial_snapshot.agent_id
        revision = await self.releases.set_availability(
            SCOPE, agent_id, 1, archived=True, enabled=True
        )
        self.assertFalse(await self.releases.list_candidates(SCOPE, ()))
        await self.releases.assert_usable(SCOPE, version_id, agent_id)
        with self.assertRaises(PermissionError):
            await self.releases.rollback(
                SCOPE, agent_id, version_id, revision, self.context, "rollback"
            )
        await self.releases.set_availability(
            SCOPE, agent_id, revision, archived=True, enabled=False
        )
        with self.assertRaisesRegex(PermissionError, "DISABLED_OR_REVOKED"):
            await self.releases.assert_usable(SCOPE, version_id, agent_id)
        self.assertEqual(
            (await self.releases.get_version(SCOPE, version_id)).frozen, self.frozen
        )
        self.assertIsNotNone(await self.driver.repo.load_record(SCOPE, "eval-D4"))

    async def test_version_payload_identity_and_hash_drift_fail_closed(self) -> None:
        version_id = await self.publish()
        row = (await self.rows(versions))[0]
        row["payload"]["agent_id"] = "forged"
        async with self.driver.env.uows() as tx:
            await tx.execute(
                update(versions).values(
                    payload=row["payload"], content_hash=canonical_hash(row["payload"])
                )
            )
            await tx.commit()
        with self.assertRaisesRegex(ValueError, "IDENTITY_DRIFT"):
            await self.releases.get_version(SCOPE, version_id)

    def test_metadata_compiles_for_sqlite_and_postgres(self) -> None:
        from sqlalchemy.dialects import postgresql, sqlite
        from sqlalchemy.schema import CreateTable

        self.assertEqual(len(get_release_metadata().tables), 4)
        for table in get_release_metadata().sorted_tables:
            for dialect in (postgresql.dialect(), sqlite.dialect()):
                self.assertIn(
                    "CREATE TABLE", str(CreateTable(table).compile(dialect=dialect))
                )

    def test_exported_d4_schema_matches_handoff_artifact(self) -> None:
        import json
        from pathlib import Path
        from jsonschema import Draft202012Validator
        from agentscope.app.workforce.lifecycle.releases import phase_d_schema_bundle

        artifact = (
            Path(__file__).resolve().parents[4]
            / "docs/workforce/handoffs/pho-tien-anh/phase_d/schemas.json"
        )
        bundle = phase_d_schema_bundle()
        self.assertEqual(json.loads(artifact.read_text()), bundle)
        for schema in bundle["schemas"].values():
            Draft202012Validator.check_schema(schema)
