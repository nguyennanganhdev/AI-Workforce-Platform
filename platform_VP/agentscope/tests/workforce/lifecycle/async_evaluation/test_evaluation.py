"""PTA-14/15 multi-pattern hard gates and durable worker recovery."""

import asyncio
from typing import Any, Dict

from agentscope.app.workforce.contracts import EvaluationStatus, ToolEffect
from agentscope.app.workforce.lifecycle._models import LifecycleError
from tests.workforce.lifecycle._fakes import Harness, manifest, scope
from tests.workforce.lifecycle.test_lifecycle import (
    SQLLifecycleCase,
    selection,
)


class AsyncEvaluationTests(SQLLifecycleCase):
    """Multi-event suites use an isolated SQL database per test."""

    async def test_worker_restart_resumes_committed_cases(self) -> None:
        draft = await self.harness.draft()
        record = await self.service.start_evaluation(
            scope(), draft.draft_id, 1, "lifecycle-patterns-v1", "key"
        )
        self.harness.runner.crash_case = "interactive"
        with self.assertRaises(asyncio.CancelledError):
            await self.service.run_evaluation(
                scope(), record.report.evaluation_id
            )
        persisted = await self.service.get_evaluation(
            scope(), record.report.evaluation_id
        )
        self.assertEqual(len(persisted.report.cases), 1)
        self.assertEqual(persisted.report.status, EvaluationStatus.RUNNING)
        # New service/repository simulates process state loss; DB snapshot
        # survives.
        restarted = Harness(self.factory)
        finished = await restarted.service.run_evaluation(
            scope(), record.report.evaluation_id
        )
        self.assertEqual(finished.report.status, EvaluationStatus.PASSED)
        self.assertEqual(len(restarted.runner.calls), 4)
        self.assertEqual(finished.snapshot, persisted.snapshot)
        self.assertTrue(
            all(
                call[2] == persisted.test_context["session_namespace"]
                for call in restarted.runner.calls
            )
        )

    async def test_no_trigger_or_duplicate_cannot_run_llm(self) -> None:
        for trigger in ("none", "duplicate", "out_of_order"):
            with self.subTest(trigger=trigger):

                def mutate(case: Any, metrics: Any) -> Any:
                    for turn in metrics["turns"]:
                        if turn["trigger"] == trigger:
                            turn["llm_calls"] = 1

                self.harness.runner.mutate = mutate
                draft = await self.harness.draft(manifest(trigger, trigger))
                record = await self.harness.evaluated(draft)
                self.assertEqual(record.report.status, EvaluationStatus.FAILED)
                self.assertIn(
                    "UNTRIGGERED_EXECUTION", record.report.hard_gate_failures
                )

    async def test_wrong_continuation_and_sync_tracking_fail(self) -> None:
        def mutate(case: Any, metrics: Any) -> Any:
            if case["case_id"] == "response-only":
                metrics["turns"][0]["next_action"] = "watch_events"
                metrics["turns"][0]["tracking_created"] = True

        self.harness.runner.mutate = mutate
        draft = await self.harness.draft()
        record = await self.harness.evaluated(draft)
        self.assertIn("INVALID_NEXT_ACTION", record.report.hard_gate_failures)
        self.assertIn(
            "SYNC_TRACKING_CREATED", record.report.hard_gate_failures
        )

    async def test_zero_hard_gates_cannot_be_overridden_by_score(self) -> None:
        def mutate(case: Any, metrics: Any) -> Any:
            metrics["answer_quality"] = 1.0
            metrics["violations"]["booking_without_consent"] = 1

        self.harness.runner.mutate = mutate
        draft = await self.harness.draft()
        record = await self.harness.evaluated(draft)
        self.assertEqual(record.report.status, EvaluationStatus.FAILED)
        self.assertTrue(
            all(
                case.metrics["answer_quality"] == 1.0
                for case in record.report.cases
            )
        )
        self.assertTrue(
            all(
                case.status == EvaluationStatus.FAILED
                for case in record.report.cases
            )
        )
        with self.assertRaisesRegex(LifecycleError, "EVALUATION_NOT_PASSED"):
            await self.service.publish(
                scope(), [selection(draft, record)], "key", "manager-A"
            )

    async def test_missing_evidence_cannot_pass(self) -> None:
        self.harness.runner.mutate = lambda case, metrics: metrics.pop(
            "violations"
        )
        draft = await self.harness.draft()
        record = await self.harness.evaluated(draft)
        self.assertIn(
            "MISSING_HARD_GATE_EVIDENCE", record.report.hard_gate_failures
        )

    async def test_cross_audience_and_unknown_recreate_fail(self) -> None:
        def mutate(case: Any, metrics: Any) -> Any:
            metrics["turns"][0]["audience_verified"] = False
            metrics["create_calls"] = 2

        self.harness.runner.mutate = mutate
        draft = await self.harness.draft()
        record = await self.harness.evaluated(draft)
        self.assertIn("cross_audience", record.report.hard_gate_failures)
        self.assertIn(
            "duplicate_side_effect", record.report.hard_gate_failures
        )

    async def test_tool_trace_checks_approval_budget_provider_and_binding(
        self,
    ) -> None:
        def mutate(case: Any, metrics: Any) -> Any:
            metrics["tool_calls"] = [
                {
                    "tool_version_id": "unbound",
                    "bound": False,
                    "arguments_valid": False,
                    "effect": "write",
                    "consent_verified": False,
                    "audience_verified": False,
                    "amount_minor": 11,
                    "approved_amount_minor": 10,
                    "claimed_success": True,
                    "provider_confirmed": False,
                },
            ]

        self.harness.runner.mutate = mutate
        record = await self.harness.evaluated(await self.harness.draft())
        self.assertTrue(
            set(
                (
                    "unbound_tool",
                    "booking_without_consent",
                    "budget_exceeded",
                    "unverified_booking",
                    "wrong_user",
                )
            ).issubset(record.report.hard_gate_failures)
        )

    async def test_cancelled_eval_cannot_publish_or_run_again(self) -> None:
        draft = await self.harness.draft()
        record = await self.service.start_evaluation(
            scope(), draft.draft_id, 1, "lifecycle-patterns-v1", "key"
        )
        cancelled = await self.service.cancel_evaluation(
            scope(), record.report.evaluation_id
        )
        self.assertEqual(cancelled.report.status, EvaluationStatus.CANCELLED)
        self.assertEqual(len(self.harness.runner.cancelled), 5)
        self.assertEqual(
            await self.service.run_evaluation(
                scope(), record.report.evaluation_id
            ),
            cancelled,
        )
        self.assertEqual(self.harness.runner.calls, [])

    async def test_async_policy_snapshot_and_protocol_drift(self) -> None:
        self.harness.registry.effect = ToolEffect.EXTERNAL_OPERATION
        draft = await self.harness.draft(manifest(external=True))
        record = await self.harness.evaluated(draft)
        self.assertEqual(record.protocol_refs[0]["schema_hash"], "protocol-v1")
        self.assertEqual(
            record.policy_snapshot["timeout_behavior"], "status_query"
        )
        self.harness.policies.policy["timeout_behavior"] = "needs_attention"
        self.assertEqual(
            record.policy_snapshot["timeout_behavior"], "status_query"
        )
        with self.assertRaisesRegex(LifecycleError, "EVALUATION_STALE"):
            await self.service.publish(
                scope(), [selection(draft, record)], "key", "manager-A"
            )
        self.harness.protocols.schema_hash = "protocol-v2"
        report = await self.service.validator.validate(scope(), draft.manifest)
        self.assertIn("PROTOCOL_SNAPSHOT_DRIFT", report.blockers)

    async def test_async_policy_invalid_and_runtime_data_rejected(
        self,
    ) -> None:
        self.harness.registry.effect = ToolEffect.EXTERNAL_OPERATION
        self.harness.policies.policy["ticket_id"] = "fixed-runtime-ticket"
        self.harness.policies.policy["event_types"] = []
        report = await self.service.validator.validate(
            scope(), manifest(external=True)
        )
        self.assertIn("RUNTIME_DATA_IN_POLICY", report.blockers)
        self.assertIn("ASYNC_POLICY_INVALID", report.blockers)

    async def test_redactor_runs_before_result_is_stored(self) -> None:
        self.harness.runner.mutate = lambda case, metrics: metrics.update(
            transcript=["fixture-sensitive"]
        )

        def redact(value: Dict[str, Any]) -> Dict[str, Any]:
            value["metrics"]["transcript"] = ["[REDACTED]"]
            return value

        self.service.redact = redact
        record = await self.harness.evaluated(await self.harness.draft())
        self.assertNotIn("fixture-sensitive", record.model_dump_json())
