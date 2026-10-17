"""C5 integration: production SQL checkpoint/guard/Execution → persisted grading."""

from typing import Any, Dict
import asyncio
import json
from pathlib import Path
import unittest

from sqlalchemy import select, update

from agentscope.app.workforce.contracts import EvaluationStatus
from agentscope.app.workforce.lifecycle.async_evaluation import (
    AsyncEvaluationService,
    EvaluationJobHandler,
    EvaluationJobService,
    RuntimeEvaluationRunner,
    SqlEvaluationRepository,
    check_persisted_release,
    get_metadata,
    lifecycle_suite,
    grade_case,
    phase_c_schema_bundle,
)
from agentscope.app.workforce.foundation import DurableJobWorker
from agentscope.app.workforce.lifecycle.async_evaluation._tables import (
    evaluations,
    steps,
    turn_evidence,
)
from tests.workforce.orchestration.phase_c import test_c4_sql_slice as c4
from tests.workforce.lifecycle.async_evaluation.runtime_fixture import SqlCaseDriver


class RuntimeIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.driver = SqlCaseDriver()
        await self.driver.setup()
        self.repo = self.driver.repo
        self.scope = c4.SCOPE
        self.frozen = self.driver.frozen
        self.runner = RuntimeEvaluationRunner(self.repo, self.driver)
        self.service = AsyncEvaluationService(self.runner, self.driver.env.clock)

    async def asyncTearDown(self) -> None:
        await self.driver.cleanup()

    def case_input(self, index: int = 0) -> Dict[str, Any]:
        payload = self.frozen.read(self.scope)
        suite = lifecycle_suite()
        return {
            **suite.runner_input(suite.cases[index]),
            "runtime_profile": payload["runtime_profile"],
            "test_context": payload["test_context"],
            "protocol_refs": payload["dependencies"]["protocol_refs"],
        }

    async def run_case(self, index: int = 0) -> Any:
        return await self.runner.run_case(
            self.scope, self.driver.snapshot, self.case_input(index), "mock"
        )

    async def test_all_patterns_use_committed_runtime_and_real_execution(self) -> None:
        record = await self.service.run(self.scope, self.frozen, "eval-C5")
        self.assertEqual(record.report.hard_gate_failures, ())
        self.assertEqual(record.report.status, EvaluationStatus.PASSED)
        self.assertEqual(self.driver.provider.calls, 4)
        await self.repo.register(self.scope, "eval-C5", self.frozen)
        await self.repo.save_record(record)
        loaded = await check_persisted_release(
            self.repo, self.scope, "eval-C5", self.frozen
        )
        self.assertEqual(loaded, record)
        evidence = []
        for _, receipt in self.driver.opened.values():
            evidence += await self.repo.evidence(self.scope, receipt.workflow_id)
        self.assertEqual(
            sum(item.model_turns for item in evidence), self.driver.model.calls
        )
        self.assertEqual(sum(item.tool_calls for item in evidence), 4)
        self.assertTrue(any(item.approval_cause for item in evidence))
        self.assertTrue(any(item.provider_cause for item in evidence))
        serialized = record.model_dump_json()
        self.assertNotIn("TEST-ONLY-ref", serialized)
        self.assertNotIn("Fixture response", serialized)

    async def test_repository_rejects_scope_override(self) -> None:
        with self.assertRaisesRegex(ValueError, "EVALUATION_SCOPE_OVERRIDE"):
            await self.repo.read(
                evaluations, self.scope, {"manager_account_id": "other"}
            )

    async def test_evidence_payload_must_match_sql_identity(self) -> None:
        await self.run_case()
        workflow_id = next(iter(self.driver.opened.values()))[1].workflow_id
        async with self.driver.env.uows() as tx:
            await tx.execute(update(turn_evidence).values(after_revision=999))
            await tx.commit()
        with self.assertRaisesRegex(ValueError, "RUNTIME_EVIDENCE_CONTEXT_MISMATCH"):
            await self.repo.evidence(self.scope, workflow_id)

    async def test_cancelled_case_rejects_new_committed_evidence(self) -> None:
        await self.run_case()
        workflow_id = next(iter(self.driver.opened.values()))[1].workflow_id
        evidence = (await self.repo.evidence(self.scope, workflow_id))[0]
        await self.runner.cancel_case(self.scope, workflow_id)
        async with self.driver.env.uows() as tx:
            with self.assertRaisesRegex(ValueError, "RUNTIME_CASE_CANCELLED"):
                await self.driver.writer.record(
                    evidence.model_copy(update={"trigger_id": "after-cancel"}), tx
                )
        self.assertEqual(len(await self.repo.evidence(self.scope, workflow_id)), 1)

    async def test_reloaded_repository_and_runner_reuse_completed_case(self) -> None:
        result = await self.run_case(1)
        counts = (
            self.driver.model.calls,
            self.driver.provider.calls,
            self.driver.apply_calls,
        )
        replacement = RuntimeEvaluationRunner(
            SqlEvaluationRepository(self.driver.env.uows), self.driver
        )
        replay = await replacement.run_case(
            self.scope, self.driver.snapshot, self.case_input(1), "mock"
        )
        self.assertEqual(replay, result)
        self.assertEqual(
            counts,
            (
                self.driver.model.calls,
                self.driver.provider.calls,
                self.driver.apply_calls,
            ),
        )
        changed = self.case_input(1)
        changed["runtime_profile"] = {"model": "changed"}
        with self.assertRaisesRegex(ValueError, "STALE_RUNTIME_CASE"):
            await replacement.run_case(
                self.scope, self.driver.snapshot, changed, "mock"
            )

    async def test_mode_scope_and_missing_audit_fail_before_success(self) -> None:
        with self.assertRaisesRegex(ValueError, "ISOLATED_MOCK"):
            await self.runner.run_case(
                self.scope, self.driver.snapshot, self.case_input(), "production"
            )
        with self.assertRaisesRegex(ValueError, "SCOPE_MISMATCH"):
            await self.runner.run_case(
                self.scope.model_copy(update={"manager_account_id": "other"}),
                self.driver.snapshot,
                self.case_input(),
                "mock",
            )
        self.assertEqual(self.driver.model.calls, 0)
        original = self.driver.apply

        async def missing(*args: Any) -> Any:
            observation = await original(*args)
            data = observation.model_dump()
            del data["audit"]["approval_granted"]
            return data

        self.driver.apply = missing
        with self.assertRaises(ValueError):
            await self.run_case()

    async def test_evidence_rollback_and_immutable_conflict(self) -> None:
        await self.run_case()
        workflow_id = next(iter(self.driver.opened.values()))[1].workflow_id
        evidence = (await self.repo.evidence(self.scope, workflow_id))[0]
        pending = evidence.model_copy(update={"trigger_id": "rolled-back-turn"})
        async with self.driver.env.uows() as tx:
            await self.driver.writer.record(pending, tx)
        self.assertEqual(len(await self.repo.evidence(self.scope, workflow_id)), 1)
        async with self.driver.env.uows() as tx:
            with self.assertRaisesRegex(ValueError, "IMMUTABLE"):
                await self.driver.writer.record(
                    evidence.model_copy(update={"model_turns": 99}), tx
                )
        self.assertEqual(
            (await self.repo.evidence(self.scope, workflow_id))[0], evidence
        )
        self.assertFalse(
            await self.repo.evidence(
                self.scope.model_copy(update={"manager_account_id": "B"}), workflow_id
            )
        )

    async def test_idle_usage_without_committed_evidence_fails(self) -> None:
        original = self.driver.apply

        async def forged(*args: Any) -> Any:
            observation = await original(*args)
            if args[2]["cause"] == "idle-before-timer":
                data = observation.model_dump()
                data["after"]["checkpoint"]["used_budget"]["model_turns"] += 1
                return data
            return observation

        self.driver.apply = forged
        with self.assertRaisesRegex(ValueError, "USAGE_EVIDENCE"):
            await self.run_case(2)

    async def test_pin_drift_is_rejected(self) -> None:
        original = self.driver.apply

        async def drift(*args: Any) -> Any:
            data = (await original(*args)).model_dump()
            data["after"]["workflow"]["version_pins"] = ("new-version",)
            data["after"]["checkpoint"]["agent_version_pins"][0][
                "version_id"
            ] = "new-version"
            return data

        self.driver.apply = drift
        with self.assertRaisesRegex(ValueError, "PIN_MISMATCH"):
            await self.run_case()

    async def test_durable_job_report_reload_and_publish_guard(self) -> None:
        jobs = EvaluationJobService(self.repo, self.driver.env.jobs)
        job_id = await jobs.enqueue(self.scope, "eval-job", self.frozen)
        self.assertEqual(
            await jobs.enqueue(self.scope, "eval-job", self.frozen), job_id
        )
        handler = EvaluationJobHandler(self.repo, self.service)

        async def observed_job(job: Any) -> Any:
            self.captured_job = job
            return await handler(job)

        worker = DurableJobWorker(
            self.driver.env.jobs,
            {handler.job_type: observed_job},
            worker_id="eval-worker",
        )
        job = await worker.run_once()
        self.assertEqual(job.status, "succeeded")
        record = await check_persisted_release(
            self.repo, self.scope, "eval-job", self.frozen
        )
        counts = (self.driver.model.calls, self.driver.provider.calls)
        replacement = EvaluationJobHandler(
            SqlEvaluationRepository(self.driver.env.uows), self.service
        )
        await replacement(self.captured_job)
        self.assertEqual(counts, (self.driver.model.calls, self.driver.provider.calls))
        self.assertEqual(record.report.status, EvaluationStatus.PASSED)
        with self.assertRaises(KeyError):
            await self.repo.load_record(
                self.scope.model_copy(update={"area_id": "other"}), "eval-job"
            )
        stale = self.frozen.model_copy(update={"content_hash": "changed"})
        with self.assertRaises(ValueError):
            await check_persisted_release(self.repo, self.scope, "eval-job", stale)

    async def test_cancelled_case_cannot_reuse_success(self) -> None:
        await self.run_case(1)
        workflow_id = self.driver.opened["interactive-booking"][1].workflow_id
        with self.assertRaises(KeyError):
            await self.runner.cancel_case(
                self.scope.model_copy(update={"manager_account_id": "B"}), workflow_id
            )
        await self.runner.cancel_case(self.scope, workflow_id)
        with self.assertRaisesRegex(ValueError, "CANCELLED"):
            await self.run_case(1)

    async def test_cached_result_requires_retained_runtime_evidence(self) -> None:
        await self.run_case()
        async with self.driver.env.uows() as tx:
            await tx.execute(update(turn_evidence).values(content_hash="tampered"))
            await tx.commit()
        with self.assertRaisesRegex(ValueError, "EVIDENCE_DRIFT"):
            await self.run_case()

    async def test_interrupted_after_observation_write_resumes_without_model_replay(
        self,
    ) -> None:
        original = self.repo.put
        interrupted = False

        async def interrupt(table: Any, *args: Any, **kwargs: Any) -> None:
            nonlocal interrupted
            await original(table, *args, **kwargs)
            if table is steps and not interrupted:
                interrupted = True
                raise asyncio.CancelledError()

        self.repo.put = interrupt
        with self.assertRaises(asyncio.CancelledError):
            await self.run_case()
        self.repo.put = original
        replacement = RuntimeEvaluationRunner(
            SqlEvaluationRepository(self.driver.env.uows), self.driver
        )
        result = await replacement.run_case(
            self.scope, self.driver.snapshot, self.case_input(), "mock"
        )
        self.assertEqual(result.status, EvaluationStatus.PASSED)
        self.assertEqual(self.driver.model.calls, 1)

    async def test_missing_model_guard_is_a_hard_failure(self) -> None:
        self.driver.model.use_guard = False
        with self.assertRaisesRegex(ValueError, "EXECUTION_GUARD"):
            await self.run_case()

    async def test_writer_failure_rolls_back_runtime_checkpoint_and_public_output(
        self,
    ) -> None:
        original = self.driver.writer.record

        async def fail(evidence: Any, tx: Any) -> None:
            await original(evidence, tx)
            raise RuntimeError("TEST-rollback")

        self.driver.writer.record = fail
        with self.assertRaisesRegex(RuntimeError, "TEST-rollback"):
            await self.run_case()
        workflow_id = self.driver.opened["response-only"][1].workflow_id
        aggregate = await self.driver.env.workflows_repo.load(self.scope, workflow_id)
        self.assertEqual(aggregate.workflow.revision, 1)
        self.assertEqual(aggregate.checkpoint.used_budget.model_turns, 0)
        self.assertFalse(await self.repo.evidence(self.scope, workflow_id))
        history = await self.driver.env.event_service.list_after(
            self.driver.actor, aggregate.workflow.conversation_id, None, 100
        )
        self.assertEqual(
            [event.event_type for event in history.items], ["request.accepted"]
        )

    async def test_job_enqueue_failure_rolls_back_frozen_input(self) -> None:
        class FailingJobs:
            async def enqueue(self, *args: Any) -> str:
                raise RuntimeError("TEST-enqueue")

        with self.assertRaisesRegex(RuntimeError, "TEST-enqueue"):
            await EvaluationJobService(self.repo, FailingJobs()).enqueue(
                self.scope, "rolled-back", self.frozen
            )
        with self.assertRaises(KeyError):
            await self.repo.load(self.scope, "rolled-back")
        async with self.driver.env.uows() as tx:
            self.assertFalse((await tx.execute(select(evaluations))).all())

    async def test_protocol_reference_drift_with_same_hash_is_rejected(self) -> None:
        original = self.driver.apply

        async def drift(*args: Any) -> Any:
            data = (await original(*args)).model_dump()
            data["after"]["checkpoint"]["protocol_pins"][0][
                "protocol_version"
            ] = "other-version"
            return data

        self.driver.apply = drift
        with self.assertRaisesRegex(ValueError, "PIN_MISMATCH"):
            await self.run_case()

    async def test_disabled_tool_before_approval_blocks_resume_without_changing_pins(
        self,
    ) -> None:
        from agentscope.app.workforce.execution._utils import ExecutionError

        original = self.driver.apply

        async def disable(*args: Any) -> Any:
            if args[2]["cause"] == "approval":
                self.driver.descriptor["available"] = False
            return await original(*args)

        self.driver.apply = disable
        with self.assertRaises(ExecutionError) as caught:
            await self.run_case(1)
        self.assertEqual(caught.exception.code, "TOOL_UNAVAILABLE")
        self.assertEqual(self.driver.provider.calls, 0)
        workflow_id = self.driver.opened["interactive-booking"][1].workflow_id
        aggregate = await self.driver.env.workflows_repo.load(self.scope, workflow_id)
        self.assertEqual(
            aggregate.workflow.version_pins,
            (self.driver.snapshot.candidate_version_id,),
        )
        self.assertTrue(aggregate.checkpoint.pending_approval_ids)

    async def test_authorization_revoke_prevents_model_turn_and_cannot_pass_grader(
        self,
    ) -> None:
        async def revoke(*args: Any) -> None:
            raise PermissionError("TEST-revoked")

        original = self.driver.apply

        async def revoked_step(*args: Any) -> Any:
            self.driver.env.authorization.authorize_trigger = revoke
            return await original(*args)

        self.driver.apply = revoked_step
        result = await self.run_case()
        graded = grade_case(lifecycle_suite().cases[0], result)
        self.assertEqual(graded.status, EvaluationStatus.FAILED)
        self.assertEqual(self.driver.model.calls, 0)
        self.assertEqual(self.driver.provider.calls, 0)

    async def test_persisted_publish_guard_rejects_cancelled_runtime_case(self) -> None:
        record = await self.service.run(self.scope, self.frozen, "eval-cancel")
        await self.repo.register(self.scope, "eval-cancel", self.frozen)
        await self.repo.save_record(record)
        workflow_id = self.driver.opened["interactive-booking"][1].workflow_id
        await self.runner.cancel_case(self.scope, workflow_id)
        with self.assertRaisesRegex(ValueError, "CANCELLED"):
            await check_persisted_release(
                self.repo, self.scope, "eval-cancel", self.frozen
            )

    def test_exported_evidence_schema_artifact_matches_code(self) -> None:
        from jsonschema import Draft202012Validator

        artifact = (
            Path(__file__).resolve().parents[4]
            / "docs/workforce/handoffs/pho-tien-anh/phase_c/schemas.json"
        )
        bundle = phase_c_schema_bundle()
        self.assertEqual(json.loads(artifact.read_text()), bundle)
        for schema in bundle["schemas"].values():
            Draft202012Validator.check_schema(schema)

    def test_metadata_is_additive_and_compiles_for_both_databases(self) -> None:
        from sqlalchemy.schema import CreateTable
        from sqlalchemy.dialects import postgresql, sqlite

        self.assertEqual(len(get_metadata().tables), 4)
        for table in get_metadata().sorted_tables:
            for dialect in (postgresql.dialect(), sqlite.dialect()):
                self.assertIn(
                    "CREATE TABLE", str(CreateTable(table).compile(dialect=dialect))
                )
