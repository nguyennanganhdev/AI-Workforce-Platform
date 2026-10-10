"""Behavior tests with an explicitly test-only runner and fixed clock."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any, Dict, Mapping, Tuple
import unittest

from agentscope.app.workforce.contracts import (
    AgentManifest,
    AsyncProtocolSnapshotRef,
    EvaluationCaseResult,
    EvaluationSnapshot,
    EvaluationStatus,
    Scope,
    ToolDescriptor,
    ToolEffect,
)
from agentscope.app.workforce.lifecycle import ValidationReport
from agentscope.app.workforce.registry.event_protocols import AsyncToolProtocol
from agentscope.app.workforce.lifecycle.async_evaluation import (
    AsyncEvaluationService,
    FrozenEvaluation,
    canonical_hash,
    check_release_evidence,
    freeze_evaluation,
    grade_case,
    lifecycle_suite,
    validate_async_draft,
)

HANDOFF = (
    Path(__file__).resolve().parents[4] / "docs/workforce/handoffs/pho-tien-anh/phase_a"
)


class FakeClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 10, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now


class FakeRunner:
    def __init__(self, clock: FakeClock) -> None:
        self.clock = clock
        self.calls = []
        self.mutation = None
        self.error_case = None

    async def run_case(
        self,
        scope: Scope,
        version_snapshot: EvaluationSnapshot,
        test_case: Mapping[str, object],
        execution_mode: str,
    ) -> EvaluationCaseResult:
        self.calls.append(
            (scope, version_snapshot.candidate_version_id, execution_mode)
        )
        if self.error_case == test_case["case_id"]:
            raise RuntimeError("private credential must not appear in report")
        case = next(
            c for c in lifecycle_suite().cases if c.case_id == test_case["case_id"]
        )
        turns = []
        for expected in case.turns:
            turn = expected.model_dump(mode="json")
            turn.update(
                audience_key="ticket-A",
                notification_audiences=["ticket-A"],
                unbound_tool_calls=0,
                argument_checks=expected.side_effect_calls,
                argument_passes=expected.side_effect_calls,
                secret_leaked=False,
                budget_exceeded=False,
                claimed_completion=expected.provider_confirmed,
                cost=0.01 if expected.llm_calls else 0,
                latency_ms=10,
            )
            turns.append(turn)
            self.clock.now += timedelta(seconds=10)
        if self.mutation:
            self.mutation(case, turns)
        return EvaluationCaseResult(
            case_id=case.case_id,
            status=EvaluationStatus.PASSED,
            metrics={"turns": turns},
        )

    async def cancel_case(self, scope: Scope, case_run_id: str) -> None:
        pass


def fixture() -> Dict[str, Any]:
    sample = json.loads((HANDOFF / "samples.json").read_text())
    snapshot = EvaluationSnapshot.model_validate(sample["EvaluationSnapshot"])
    scope = snapshot.scope
    protocol = AsyncToolProtocol(
        protocol_id="repair",
        protocol_version="1",
        tool_version_id="repair-v1",
        provider_integration_id="provider-A",
        effect=ToolEffect.EXTERNAL_OPERATION,
        result_mode="pending",
        completion_policy="explicit_close",
        requires_approval=True,
        client_reference_field="client_reference",
        status_field="status",
        status_query_tool_version_id="query-v1",
        event_mappings={
            "completed": {
                "status": "completed",
                "data_schema": {"type": "object"},
                "fact_fields": ["confirmed"],
            }
        },
        transitions={"pending": ["completed"]},
        terminal_statuses=("completed",),
        timeout_seconds=60,
    )
    tool = ToolDescriptor(
        tool_id="repair",
        tool_version_id="repair-v1",
        source_kind="mcp",
        provider_tool_name="create_repair",
        llm_alias="repair",
        input_schema={"type": "object"},
        schema_hash="tool-hash",
        capabilities=("repair",),
        effect=ToolEffect.EXTERNAL_OPERATION,
        available=True,
    )
    manifest_data = snapshot.manifest.model_dump(mode="json")
    manifest_data["business_profile"]["capabilities"] = ["repair"]
    manifest_data["spec"]["tool_bindings"] = [
        {
            "tool_id": "repair",
            "tool_version_id": "repair-v1",
            "schema_hash": "tool-hash",
            "required_capability": "repair",
            "selection_reason": "repair request",
        }
    ]
    manifest_data.update(
        async_policy_ref="policy-v1",
        protocol_snapshot_hashes=[protocol.snapshot_ref.schema_hash],
    )
    policy = {
        "schema_version": "1",
        "capabilities": ["repair"],
        "event_types": ["completed"],
        "required_facts": ["confirmed"],
        "completion_condition": "provider reports confirmed completion",
        "human_confirmation": True,
        "timeout_behavior": "status_query",
    }
    return dict(
        snapshot=snapshot,
        scope=scope,
        manifest=AgentManifest.model_validate(manifest_data),
        tools=[tool],
        protocols=[protocol],
        policy=policy,
        policy_scope=scope,
        policy_ref="policy-v1",
    )


def validate(data: Dict[str, Any]) -> Tuple[ValidationReport, Dict[str, Any]]:
    return validate_async_draft(**{k: v for k, v in data.items() if k != "snapshot"})


def seal(data: Dict[str, Any]) -> FrozenEvaluation:
    report, dependencies = validate(data)
    manifest_hash = canonical_hash(data["manifest"].model_dump(mode="json"))
    context = {"peers": [], "audience": "ticket-A"}
    snapshot = data["snapshot"].model_copy(
        update={
            "manifest": data["manifest"],
            "manifest_hash": manifest_hash,
            "source_draft_hash": manifest_hash,
            "tool_snapshot_hash": report.tool_snapshot_hash,
            "test_context_hash": canonical_hash(context),
        }
    )
    return freeze_evaluation(
        snapshot, report, dependencies, {"model_ref": "mock"}, context
    )


class ValidationTests(unittest.TestCase):
    def test_valid_pending(self) -> None:
        self.assertTrue(validate(fixture())[0].valid)

    def test_dependency_failure_paths(self) -> None:
        for change, blocker in (
            (lambda d: d.update(policy_ref="other"), "POLICY_UNRESOLVED"),
            (
                lambda d: d.update(
                    policy_scope=d["scope"].model_copy(
                        update={"manager_account_id": "B"}
                    )
                ),
                "POLICY_SCOPE_MISMATCH",
            ),
            (lambda d: d.update(protocols=[]), "MISSING_PROTOCOL"),
            (lambda d: d.update(tools=[]), "MISSING_TOOL_SNAPSHOT"),
            (
                lambda d: d.update(
                    tools=[d["tools"][0].model_copy(update={"available": False})]
                ),
                "TOOL_UNAVAILABLE",
            ),
            (
                lambda d: d.update(
                    tools=[d["tools"][0].model_copy(update={"schema_hash": "drift"})]
                ),
                "TOOL_SCHEMA_DRIFT",
            ),
            (
                lambda d: d.update(
                    tools=[d["tools"][0].model_copy(update={"capabilities": ()})]
                ),
                "MISSING_REQUIRED_CAPABILITY",
            ),
            (lambda d: d["policy"].update(ticket_id="ticket"), "INVALID_POLICY"),
            (lambda d: d["policy"].update(human_confirmation="yes"), "INVALID_POLICY"),
            (
                lambda d: d["policy"].update(required_facts=["other"]),
                "POLICY_FACT_COVERAGE",
            ),
            (
                lambda d: d["policy"].update(event_types=["other"]),
                "POLICY_EVENT_COVERAGE",
            ),
            (
                lambda d: d["policy"].update(human_confirmation=False),
                "MISSING_HUMAN_CONFIRMATION",
            ),
        ):
            with self.subTest(blocker=blocker):
                data = fixture()
                change(data)
                self.assertIn(blocker, validate(data)[0].blockers)

    def test_builder_query_only_dialect_explicit(self) -> None:
        data = fixture()
        protocol = data["protocols"][0].model_copy(update={"event_mappings": {}})
        data["protocols"] = [protocol]
        data["manifest"] = data["manifest"].model_copy(
            update={"protocol_snapshot_hashes": (protocol.snapshot_ref.schema_hash,)}
        )
        data["policy"].update(
            timeout_seconds=60,
            timeout_behavior="query_status",
            event_types=[],
            required_facts=[],
        )
        data["policy_schema"] = "bhn-phase-a-1"
        self.assertTrue(validate(data)[0].valid)
        data["policy_schema"] = "pta-phase-a-1"
        self.assertIn("INVALID_POLICY", validate(data)[0].blockers)

    def test_terminal_without_tracking(self) -> None:
        data = fixture()
        data.update(
            tools=[data["tools"][0].model_copy(update={"effect": ToolEffect.READ})],
            protocols=[],
            policy=None,
            policy_ref=None,
        )
        data["manifest"] = data["manifest"].model_copy(
            update={"async_policy_ref": None, "protocol_snapshot_hashes": ()}
        )
        self.assertTrue(validate(data)[0].valid)

    def test_missing_query_never_downgrades(self) -> None:
        data = fixture()
        protocol = data["protocols"][0].model_copy(
            update={"status_query_tool_version_id": None}
        )
        data["protocols"] = [protocol]
        data["manifest"] = data["manifest"].model_copy(
            update={"protocol_snapshot_hashes": (protocol.snapshot_ref.schema_hash,)}
        )
        self.assertIn("MISSING_STATUS_QUERY", validate(data)[0].blockers)


class EvaluationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.data = fixture()
        self.frozen = seal(self.data)
        self.clock = FakeClock()
        self.runner = FakeRunner(self.clock)
        self.service = AsyncEvaluationService(self.runner, self.clock)

    async def test_patterns_pass_only_mock_mode(self) -> None:
        record = await self.service.run(self.data["scope"], self.frozen, "eval-A")
        self.assertEqual(record.report.status, EvaluationStatus.PASSED)
        self.assertEqual(len(record.report.cases), 5)
        self.assertTrue(all(mode == "mock" for _, _, mode in self.runner.calls))
        self.assertGreater(record.report.metrics["cost"], 0)
        check_release_evidence(self.data["scope"], record, self.frozen)

    async def test_seal_survives_reload_and_input_mutation(self) -> None:
        self.data["manifest"].spec.model_config_ref["tampered"] = True
        self.data["policy"]["completion_condition"] = "changed"
        reloaded = FrozenEvaluation.model_validate_json(self.frozen.model_dump_json())
        record = await self.service.run(self.data["scope"], reloaded, "eval-A")
        self.assertEqual(record.report.status, EvaluationStatus.PASSED)
        self.assertNotIn("tampered", record.snapshot.manifest.spec.model_config_ref)

    async def test_scope_and_integrity_before_runner(self) -> None:
        for scope, frozen in (
            (
                self.data["scope"].model_copy(update={"manager_account_id": "B"}),
                self.frozen,
            ),
            (
                self.data["scope"],
                self.frozen.model_copy(update={"content_hash": "wrong"}),
            ),
        ):
            with self.assertRaises(ValueError):
                await self.service.run(scope, frozen, "eval-A")
        self.assertFalse(self.runner.calls)

    async def test_hard_gate_mutations_override_pass(self) -> None:
        mutations = (
            ("CROSS_AUDIENCE", {"notification_audiences": ["ticket-B"]}),
            ("UNBOUND_TOOL", {"unbound_tool_calls": 1}),
            ("SECRET_LEAK", {"secret_leaked": True}),
            ("APPROVED_BUDGET_EXCEEDED", {"budget_exceeded": True}),
            (
                "UNCONFIRMED_COMPLETION",
                {"claimed_completion": True, "provider_confirmed": False},
            ),
            ("WORKFLOW_CONTRACT", {"next_action": "watch_request"}),
            ("MISSING_RUNNER_EVIDENCE", {"llm_calls": True}),
            ("INVALID_ARGUMENT_METRICS", {"argument_checks": 0, "argument_passes": 1}),
        )
        for blocker, changes in mutations:
            with self.subTest(blocker=blocker):
                self.runner.mutation = lambda c, turns: turns[0].update(changes)
                record = await self.service.run(
                    self.data["scope"], self.frozen, "eval-A"
                )
                self.assertEqual(record.report.status, EvaluationStatus.FAILED)
                self.assertIn(blocker, record.report.hard_gate_failures)

    async def test_idle_and_repeated_side_effects(self) -> None:
        self.runner.mutation = lambda c, turns: [
            t.update(llm_calls=1) for t in turns if t["cause"] == "idle-before-timer"
        ]
        record = await self.service.run(self.data["scope"], self.frozen, "eval-A")
        self.assertIn(
            "UNTRIGGERED_OR_MISSING_LLM_TURN", record.report.hard_gate_failures
        )
        self.runner.mutation = lambda c, turns: [
            t.update(side_effect_calls=2, approval_granted=False)
            for t in turns
            if t["side_effect_calls"]
        ]
        record = await self.service.run(self.data["scope"], self.frozen, "eval-A")
        self.assertIn("SIDE_EFFECT_COUNT", record.report.hard_gate_failures)
        self.assertIn("BOOKING_WITHOUT_CONSENT", record.report.hard_gate_failures)

    async def test_sync_tracking_and_runner_exception(self) -> None:
        self.runner.mutation = lambda c, turns: turns[0].update(tracking_records=1)
        record = await self.service.run(self.data["scope"], self.frozen, "eval-A")
        self.assertIn("TRACKING_DEPENDENCY", record.report.hard_gate_failures)
        self.runner.mutation = None
        self.runner.error_case = "response-only"
        record = await self.service.run(self.data["scope"], self.frozen, "eval-A")
        self.assertEqual(len(record.report.cases), 5)
        self.assertNotIn("private credential", record.model_dump_json())
        self.assertIn("RUNNER_ERROR", record.report.hard_gate_failures)

    async def test_release_stale_fields_and_forged_report(self) -> None:
        record = await self.service.run(self.data["scope"], self.frozen, "eval-A")
        for field in (
            "runtime_profile",
            "test_context",
            "gate_config",
            "policy_snapshot",
        ):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "STALE"):
                check_release_evidence(
                    self.data["scope"],
                    record.model_copy(update={field: {"changed": True}}),
                    self.frozen,
                )
        with self.assertRaisesRegex(ValueError, "STALE"):
            check_release_evidence(
                self.data["scope"],
                record.model_copy(
                    update={
                        "report": record.report.model_copy(
                            update={"draft_revision": 999}
                        )
                    }
                ),
                self.frozen,
            )

    def test_missing_evidence_and_expectations_not_sent(self) -> None:
        suite = lifecycle_suite()
        case = suite.cases[0]
        result = EvaluationCaseResult(
            case_id=case.case_id,
            status=EvaluationStatus.PASSED,
            metrics={"quality": 100, "argument_rate": 1},
        )
        self.assertIn(
            "MISSING_RUNNER_EVIDENCE", grade_case(case, result).hard_gate_failures
        )
        self.assertNotIn("turns", suite.runner_input(case))


class ScopedAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_exact_owner_protocol_and_policy_resolution(self) -> None:
        from agentscope.app.workforce.lifecycle.async_evaluation import (
            AsyncDraftValidator,
        )

        data = fixture()
        calls = []

        class Registry:
            async def get_tool_snapshot(
                self, scope: Scope, version: str
            ) -> ToolDescriptor:
                calls.append((scope, version))
                return data["tools"][0]

        class ProtocolPort:
            async def get_snapshot(
                self, scope: Scope, version: str
            ) -> AsyncProtocolSnapshotRef:
                calls.append((scope, version))
                return data["protocols"][0].snapshot_ref

        async def detail(
            scope: Scope, ref: AsyncProtocolSnapshotRef
        ) -> AsyncToolProtocol:
            calls.append((scope, ref.tool_version_id))
            return data["protocols"][0]

        async def policy(
            scope: Scope, ref: str
        ) -> Tuple[Scope, str, str, Dict[str, Any]]:
            calls.append((scope, ref))
            return scope, ref, "pta-phase-a-1", data["policy"]

        adapter = AsyncDraftValidator(Registry(), ProtocolPort(), detail, policy)
        report, evidence = await adapter.validate(data["scope"], data["manifest"])
        self.assertTrue(report.valid)
        self.assertTrue(all(scope == data["scope"] for scope, _ in calls))
        self.assertEqual(
            evidence["protocol_refs"][0],
            data["protocols"][0].snapshot_ref.model_dump(mode="json"),
        )

        async def drift(
            scope: Scope, ref: AsyncProtocolSnapshotRef
        ) -> AsyncToolProtocol:
            return data["protocols"][0].model_copy(update={"protocol_version": "2"})

        with self.assertRaisesRegex(ValueError, "REFERENCE_DRIFT"):
            await AsyncDraftValidator(
                Registry(), ProtocolPort(), drift, policy
            ).validate(data["scope"], data["manifest"])


class ReviewRegressionTests(unittest.IsolatedAsyncioTestCase):
    def test_freeze_rechecks_manifest_against_validated_dependencies(self) -> None:
        data = fixture()
        report, dependencies = validate(data)
        manifest = data["manifest"].model_copy(
            update={
                "spec": data["manifest"].spec.model_copy(
                    update={
                        "tool_bindings": (
                            data["manifest"]
                            .spec.tool_bindings[0]
                            .model_copy(update={"schema_hash": "unvalidated-schema"}),
                        )
                    }
                )
            }
        )
        manifest_hash = canonical_hash(manifest.model_dump(mode="json"))
        context = {"peers": []}
        snapshot = data["snapshot"].model_copy(
            update={
                "manifest": manifest,
                "manifest_hash": manifest_hash,
                "source_draft_hash": manifest_hash,
                "tool_snapshot_hash": report.tool_snapshot_hash,
                "test_context_hash": canonical_hash(context),
            }
        )
        with self.assertRaisesRegex(ValueError, "SNAPSHOT_DEPENDENCY_MISMATCH"):
            freeze_evaluation(snapshot, report, dependencies, {}, context)

    async def test_failed_runner_with_error_code_cannot_pass(self) -> None:
        data = fixture()
        runner = FakeRunner(FakeClock())
        case = lifecycle_suite().cases[0]
        result = await runner.run_case(
            data["scope"],
            data["snapshot"],
            lifecycle_suite().runner_input(case),
            "mock",
        )
        result = result.model_copy(update={"error_code": "MODEL_ERROR"})
        self.assertNotEqual(grade_case(case, result).status, EvaluationStatus.PASSED)

    async def test_release_honors_ninety_percent_completion_gate(self) -> None:
        from agentscope.app.workforce.lifecycle.async_evaluation import LifecycleSuite

        data = fixture()
        clock = FakeClock()
        base_case = lifecycle_suite().cases[0]
        suite = LifecycleSuite(
            suite_version="review-quality-1",
            cases=tuple(
                base_case.model_copy(update={"case_id": "quality-" + str(index)})
                for index in range(10)
            ),
        )
        original = seal(data).read(data["scope"])
        frozen = freeze_evaluation(
            EvaluationSnapshot.model_validate(original["snapshot"]),
            ValidationReport.model_validate(original["validation"]),
            original["dependencies"],
            original["runtime_profile"],
            original["test_context"],
            suite,
        )

        class QualityRunner:
            async def run_case(
                self,
                scope: Scope,
                snapshot: EvaluationSnapshot,
                test_case: Mapping[str, object],
                execution_mode: str,
            ) -> EvaluationCaseResult:
                result = await FakeRunner(clock).run_case(
                    scope,
                    snapshot,
                    lifecycle_suite().runner_input(base_case),
                    execution_mode,
                )
                return result.model_copy(
                    update={
                        "case_id": test_case["case_id"],
                        "status": (
                            EvaluationStatus.FAILED
                            if test_case["case_id"] == "quality-0"
                            else EvaluationStatus.PASSED
                        ),
                    }
                )

        record = await AsyncEvaluationService(QualityRunner(), clock).run(
            data["scope"], frozen, "quality-eval"
        )
        self.assertEqual(record.report.status, EvaluationStatus.PASSED)
        self.assertEqual(record.report.metrics["completion_rate"], 0.9)
        check_release_evidence(data["scope"], record, frozen)
        with self.assertRaisesRegex(ValueError, "METRICS_MISMATCH"):
            check_release_evidence(
                data["scope"],
                record.model_copy(
                    update={
                        "report": record.report.model_copy(
                            update={
                                "metrics": dict(
                                    record.report.metrics, completion_rate=1.0
                                )
                            }
                        )
                    }
                ),
                frozen,
            )
