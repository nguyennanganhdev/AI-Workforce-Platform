"""Release/reuse/API regressions and versioned gate/quality evidence."""

from typing import Any

from agentscope.app.workforce.contracts import (
    BuildItem,
    BuildItemStatus,
    BuildSource,
    EvaluationStatus,
    ReuseAction,
    ReuseDecision,
)
from agentscope.app.workforce.lifecycle import EvaluationSuite, SuiteCatalog
from agentscope.app.workforce.lifecycle._models import (
    AgentDefinition,
    LifecycleError,
    new_id,
)
from agentscope.app.workforce.lifecycle.async_evaluation import lifecycle_suite
from tests.workforce.lifecycle._fakes import manifest, scope
from tests.workforce.lifecycle.test_lifecycle import (
    SQLLifecycleCase,
    selection,
)


class LifecycleRegressionTests(SQLLifecycleCase):
    async def test_tool_schema_cannot_fetch_external_refs_during_eval(
        self,
    ) -> None:
        original = self.harness.registry.get_tool_snapshot

        async def snapshot(owner: Any, tool_version_id: str) -> Any:
            tool = await original(owner, tool_version_id)
            return tool.model_copy(
                update={
                    "input_schema": {"$ref": "https://invalid.test/schema"}
                }
            )

        self.harness.registry.get_tool_snapshot = snapshot
        report = await self.service.validator.validate(scope(), manifest())
        self.assertFalse(report.valid)
        self.assertIn("EXTERNAL_SCHEMA_REFERENCE_FORBIDDEN", report.blockers)

    async def test_publish_outbox_failure_rolls_back_versions_and_pointer(
        self,
    ) -> None:
        draft = await self.harness.draft()
        evaluation = await self.harness.evaluated(draft)
        self.harness.jobs.fail = True
        with self.assertRaises(RuntimeError):
            await self.service.publish(
                scope(), [selection(draft, evaluation)], "key", "manager-A"
            )
        async with self.service.repository.transaction(scope()) as tx:
            self.assertEqual(await tx.list("versions"), [])
            self.assertEqual(await tx.list("release_events"), [])
        self.assertEqual(
            (await self.service.get_draft(scope(), draft.draft_id)).revision, 1
        )

    async def test_delete_batch_history_keeps_library_and_version(
        self,
    ) -> None:
        draft = await self.harness.draft()
        version, _ = await self.publish_draft(draft)
        item = BuildItem(
            item_id=new_id(),
            agent_key="hotel",
            source=BuildSource.REUSE,
            reuse_action=ReuseAction.REUSE,
            reuse_agent_id=draft.agent_id,
            reuse_version_id=version.version_id,
            status=BuildItemStatus.PROPOSED,
        )
        batch = await self.service.create_batch(scope(), "build", [item])
        await self.service.delete_batch_history(scope(), batch.batch_id, 1)
        self.assertEqual(
            await self.service.get_version(scope(), version.version_id),
            version,
        )
        self.assertEqual(
            len(await self.service.list_candidates(scope(), [])), 1
        )
        with self.assertRaisesRegex(LifecycleError, "RESOURCE_NOT_FOUND"):
            await self.service.get_batch(scope(), batch.batch_id)

    async def test_legacy_mapping_is_scoped_and_requires_eval(self) -> None:
        value = manifest()
        check = await self.service.find_candidates(
            scope(), value.business_profile
        )
        decision = ReuseDecision(
            agent_key="hotel",
            action=ReuseAction.CREATE,
            reuse_check_id=check.reuse_check_id,
            reason="Verified legacy import",
            expected_catalog_revision=check.agent_catalog_revision,
        )
        draft = await self.service.index_legacy(
            scope(), "legacy-hotel", value, decision
        )
        self.assertEqual(
            await self.service.index_legacy(
                scope(), "legacy-hotel", value, decision
            ),
            draft,
        )
        self.assertEqual(await self.service.list_candidates(scope(), []), ())
        agent = (await self.service.list_agents(scope()))["items"][0]
        self.assertEqual(agent["legacy_agent_id"], "legacy-hotel")
        self.assertEqual(
            (await self.service.list_agents(scope("manager-B")))["items"], []
        )

    async def test_all_four_scope_fields_filter_reads(self) -> None:
        draft = await self.harness.draft()
        for key in scope().model_dump():
            foreign = scope().model_copy(update={key: "other"})
            with self.subTest(field=key):
                with self.assertRaisesRegex(
                    LifecycleError, "RESOURCE_NOT_FOUND"
                ):
                    await self.service.get_draft(foreign, draft.draft_id)

    async def test_unbound_tool_cannot_forge_bound_flag(self) -> None:
        def mutate(case: Any, metrics: Any) -> None:
            metrics["tool_calls"] = [
                {
                    "tool_version_id": "foreign",
                    "bound": True,
                    "arguments_valid": True,
                    "effect": "read",
                    "arguments": {},
                }
            ]

        self.harness.runner.mutate = mutate
        evaluation = await self.harness.evaluated(await self.harness.draft())
        self.assertIn("unbound_tool", evaluation.report.hard_gate_failures)

    async def test_live_eval_transport_is_a_hard_failure(self) -> None:
        self.harness.runner.mutate = lambda case, metrics: metrics.update(
            live_provider_calls=1
        )
        evaluation = await self.harness.evaluated(await self.harness.draft())
        self.assertIn(
            "EVAL_TRANSPORT_NOT_ISOLATED", evaluation.report.hard_gate_failures
        )

    async def test_report_records_repeat_variance(self) -> None:
        draft = await self.harness.draft()
        await self.harness.evaluated(draft)
        evaluation = await self.harness.evaluated(draft)
        self.assertEqual(evaluation.report.metrics["repeat_count"], 2)
        self.assertEqual(evaluation.report.metrics["completion_variance"], 0)

    async def test_revoke_cannot_be_downgraded_to_archive(self) -> None:
        version, _ = await self.publish_draft(await self.harness.draft())
        agent = AgentDefinition.model_validate(
            await self.service.repository.get(
                scope(), "agents", version.agent_id
            )
        )
        revoked = await self.service.set_availability(
            scope(), agent.agent_id, "revoked", agent.revision
        )
        with self.assertRaisesRegex(LifecycleError, "AGENT_UNAVAILABLE"):
            await self.service.set_availability(
                scope(), agent.agent_id, "archived", revoked.revision
            )

    async def test_quality_judge_runs_only_after_hard_gates(self) -> None:
        cases = list(lifecycle_suite().cases)
        for case in cases:
            case["quality_required"] = True
        self.service.suites = SuiteCatalog(
            [EvaluationSuite("quality-v1", cases)]
        )
        self.service.runtime_profile["judge_profile_hash"] = "judge-v1"
        calls = []

        class Judge:
            async def judge(
                self, owner: Any, snapshot: Any, case: Any, result: Any
            ) -> Any:
                calls.append(case["case_id"])
                return {
                    "score": 1.0,
                    "judge_profile_hash": "judge-v1",
                    "cost": "0.001",
                    "latency_ms": 1,
                }

        self.service.judge = Judge()
        draft = await self.harness.draft()
        self.harness.runner.mutate = lambda case, metrics: metrics[
            "violations"
        ].update(secret_leak=1)
        record = await self.service.start_evaluation(
            scope(), draft.draft_id, 1, "quality-v1", "key"
        )
        failed = await self.service.run_evaluation(
            scope(), record.report.evaluation_id
        )
        self.assertEqual(calls, [])
        self.assertEqual(failed.report.status, EvaluationStatus.FAILED)
        self.harness.runner.mutate = None
        record = await self.service.start_evaluation(
            scope(), draft.draft_id, 1, "quality-v1", "key2"
        )
        passed = await self.service.run_evaluation(
            scope(), record.report.evaluation_id
        )
        self.assertEqual(len(calls), 5)
        self.assertEqual(passed.report.status, EvaluationStatus.PASSED)
