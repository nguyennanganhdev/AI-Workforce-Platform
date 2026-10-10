"""Durable evaluation orchestration over shared
JobPort/EvaluationRunnerPort."""

import asyncio
from copy import deepcopy
from decimal import Decimal
from statistics import pvariance
from ..contracts import (
    EvaluationReport,
    EvaluationSnapshot,
    EvaluationStatus,
    Scope,
)
from ._graders import GATE_V1, grade_case, grade_suite
from ._models import (
    AgentDraft,
    EvaluationRecord,
    LifecycleError,
    canonical_hash,
    new_id,
    now,
)
from ._suites import grading_cases


class EvaluationMixin:
    async def start_evaluation(
        self,
        scope: Scope,
        draft_id: str,
        expected_revision: int,
        suite_version: str,
        idempotency_key: str,
    ) -> EvaluationRecord:
        await self.identity.check_scope_active(scope)
        if not idempotency_key:
            raise LifecycleError("IDEMPOTENCY_KEY_REQUIRED", 422)
        suite = self.suites.get(suite_version)
        if any(case.get("quality_required") for case in suite.cases):
            if self.judge is None or not self.runtime_profile.get(
                "judge_profile_hash"
            ):
                raise LifecycleError("QUALITY_JUDGE_REQUIRED", 503)
        request_hash = canonical_hash(
            [draft_id, expected_revision, suite_version]
        )
        receipt_id = canonical_hash(
            ["evaluation", scope.model_dump(), idempotency_key]
        )
        async with self.repository.transaction(scope) as tx:
            receipt = await tx.maybe_get("receipts", receipt_id)
            if receipt:
                if receipt["request_hash"] != request_hash:
                    raise LifecycleError("IDEMPOTENCY_CONFLICT")
                return EvaluationRecord.model_validate(
                    await tx.get("evaluations", receipt["evaluation_id"])
                )
        draft = await self.get_draft(scope, draft_id)
        if draft.revision != expected_revision:
            raise LifecycleError("REVISION_CONFLICT")
        validation, refs, policy = await self.validator.freeze(
            scope, draft.manifest
        )
        if not validation.valid:
            raise LifecycleError(
                "DRAFT_INVALID", 422, {"blockers": list(validation.blockers)}
            )
        context = {
            "suite_hash": suite.content_hash,
            "execution_mode": "mock",
            "session_namespace": new_id(),
            "clock": "fixture",
            "protocol_refs": list(refs),
            "policy": policy,
            "peer_fixtures": self.peer_fixtures,
        }
        snapshot = EvaluationSnapshot(
            snapshot_id=new_id(),
            scope=scope,
            agent_id=draft.agent_id,
            draft_id=draft_id,
            draft_revision=draft.revision,
            source_draft_hash=draft.manifest_hash,
            candidate_version_id=new_id(),
            manifest=draft.manifest,
            manifest_hash=draft.manifest_hash,
            tool_snapshot_hash=validation.tool_snapshot_hash,
            test_context_hash=canonical_hash(context),
            created_at=now(),
        )
        evaluation_id = new_id()
        report = EvaluationReport(
            evaluation_id=evaluation_id,
            agent_id=draft.agent_id,
            draft_id=draft_id,
            draft_revision=draft.revision,
            manifest_hash=draft.manifest_hash,
            snapshot_id=snapshot.snapshot_id,
            suite_version=suite_version,
            runtime_profile_hash=canonical_hash(self.runtime_profile),
            tool_snapshot_hash=validation.tool_snapshot_hash,
            test_context_hash=snapshot.test_context_hash,
            status=EvaluationStatus.QUEUED,
        )
        async with self.repository.transaction(scope) as tx:
            await self.identity.check_scope_active(scope, uow=tx)
            current = AgentDraft.model_validate(
                await tx.get("drafts", draft_id)
            )
            if (
                current.revision != expected_revision
                or current.manifest_hash != draft.manifest_hash
            ):
                raise LifecycleError("REVISION_CONFLICT")
            # Job persistence MUST join tx.session; no enqueue/commit gap.
            job_id = await self.jobs.enqueue(
                scope,
                "workforce.lifecycle.evaluate",
                {"evaluation_id": evaluation_id},
                f"evaluation:{evaluation_id}",
                uow=tx,
            )
            record = EvaluationRecord(
                scope=scope,
                revision=1,
                snapshot=snapshot,
                report=report,
                suite_hash=suite.content_hash,
                runtime_profile=self.runtime_profile,
                test_context=context,
                validation=validation,
                protocol_refs=refs,
                policy_snapshot=policy,
                gate_config=dict(GATE_V1),
                job_id=job_id,
            )
            await tx.insert(
                "evaluations", evaluation_id, record.model_dump(mode="json")
            )
            await tx.insert(
                "snapshots",
                snapshot.snapshot_id,
                snapshot.model_dump(mode="json"),
            )
            existing_suite = await tx.maybe_get("suites", suite.content_hash)
            if existing_suite is None:
                await tx.insert(
                    "suites",
                    suite.content_hash,
                    {"version": suite.version, "cases": list(suite.cases)},
                )
            await tx.insert(
                "receipts",
                receipt_id,
                {"request_hash": request_hash, "evaluation_id": evaluation_id},
            )
            return record

    async def get_evaluation(
        self, scope: Scope, evaluation_id: str
    ) -> EvaluationRecord:
        return EvaluationRecord.model_validate(
            await self.repository.get(scope, "evaluations", evaluation_id)
        )

    async def _save_evaluation(
        self, scope: Scope, old: EvaluationRecord, changed: EvaluationRecord
    ) -> EvaluationRecord:
        changed = changed.model_copy(update={"revision": old.revision + 1})
        async with self.repository.transaction(scope) as tx:
            await tx.save(
                "evaluations",
                old.report.evaluation_id,
                changed.model_dump(mode="json"),
                old.revision,
            )
            existing_ids = {case.case_id for case in old.report.cases}
            for case in changed.report.cases:
                if case.case_id not in existing_ids:
                    await tx.insert(
                        "cases",
                        canonical_hash(
                            [old.report.evaluation_id, case.case_id]
                        ),
                        {
                            "agent_id": old.snapshot.agent_id,
                            "evaluation_id": old.report.evaluation_id,
                            "result": case.model_dump(mode="json"),
                        },
                    )
        return changed

    async def run_evaluation(
        self, scope: Scope, evaluation_id: str
    ) -> EvaluationRecord:
        """Job worker owns lease; retries use stable, isolated per-case run
        IDs."""
        await self.identity.check_scope_active(scope)
        record = await self.get_evaluation(scope, evaluation_id)
        if record.report.status not in (
            EvaluationStatus.QUEUED,
            EvaluationStatus.RUNNING,
        ):
            return record
        suite = self.suites.get(record.report.suite_version)
        if (
            suite.content_hash != record.suite_hash
            or canonical_hash(self.runtime_profile)
            != record.report.runtime_profile_hash
        ):
            raise LifecycleError("EVALUATION_PROFILE_DRIFT")
        report = record.report.model_copy(
            update={
                "status": EvaluationStatus.RUNNING,
                "started_at": record.report.started_at or now(),
            }
        )
        record = await self._save_evaluation(
            scope, record, record.model_copy(update={"report": report})
        )
        results = list(record.report.cases)
        try:
            for case in suite.cases:
                if any(
                    result.case_id == case["case_id"] for result in results
                ):
                    continue
                current = await self.get_evaluation(scope, evaluation_id)
                if current.revision != record.revision:
                    return current
                await self.identity.check_scope_active(scope)
                await self.require_compatible(scope, record.snapshot.manifest)
                run_case = dict(
                    case,
                    case_run_id=canonical_hash(
                        [evaluation_id, case["case_id"]]
                    ),
                    test_context=record.test_context,
                    runtime_profile=record.runtime_profile,
                    candidate_version_id=record.snapshot.candidate_version_id,
                    sandbox_namespace=record.test_context["session_namespace"],
                )
                result = await self.runner.run_case(
                    scope,
                    record.snapshot.model_copy(deep=True),
                    deepcopy(run_case),
                    "mock",
                )
                if result.case_id != case["case_id"]:
                    raise LifecycleError("CASE_ID_MISMATCH")
                # Secrets resolved by the runtime are redacted by its adapter
                # as
                # well as this injected Foundation redactor before persistence.
                clean = self.redact(result.model_dump(mode="json"))
                result = type(result).model_validate(clean)
                golden = next(
                    item
                    for item in grading_cases(
                        suite,
                        record.validation.tool_snapshots,
                    )
                    if item["case_id"] == case["case_id"]
                )
                case_failures = grade_case(golden, result)
                if case_failures:
                    result = result.model_copy(
                        update={
                            "status": EvaluationStatus.FAILED,
                            "hard_gate_failures": case_failures,
                        }
                    )
                elif case.get("quality_required"):
                    if self.judge is None:
                        raise LifecycleError("QUALITY_JUDGE_REQUIRED", 503)
                    verdict = self.redact(
                        await self.judge.judge(
                            scope, record.snapshot, case, result
                        )
                    )
                    score = verdict.get("score")
                    if (
                        type(score) not in (int, float)
                        or not 0 <= score <= 1
                        or not verdict.get("judge_profile_hash")
                        == record.runtime_profile.get("judge_profile_hash")
                    ):
                        raise LifecycleError("QUALITY_JUDGE_INVALID")
                    metrics = dict(result.metrics, quality_judge=verdict)
                    judge_cost = Decimal(str(verdict["cost"]))
                    judge_latency = float(verdict["latency_ms"])
                    if (
                        not judge_cost.is_finite()
                        or judge_cost < 0
                        or not 0 <= judge_latency < float("inf")
                    ):
                        raise LifecycleError("QUALITY_JUDGE_INVALID")
                    metrics["cost"] = str(
                        Decimal(str(metrics["cost"])) + judge_cost
                    )
                    metrics["latency_ms"] = (
                        float(metrics["latency_ms"]) + judge_latency
                    )
                    result = result.model_copy(
                        update={
                            "metrics": metrics,
                            "status": (
                                EvaluationStatus.PASSED
                                if score >= case.get("quality_threshold", 0.8)
                                else EvaluationStatus.FAILED
                            ),
                        }
                    )
                results.append(result)
                report = record.report.model_copy(
                    update={"cases": tuple(results)}
                )
                record = await self._save_evaluation(
                    scope, record, record.model_copy(update={"report": report})
                )
            passed, metrics, failures = grade_suite(
                grading_cases(suite, record.validation.tool_snapshots),
                results,
                record.gate_config,
            )
            async with self.repository.transaction(scope) as tx:
                prior = [
                    item["report"]["metrics"]
                    for item in await tx.list("evaluations")
                    if item["report"]["evaluation_id"] != evaluation_id
                    and item["report"]["manifest_hash"]
                    == record.report.manifest_hash
                    and item["suite_hash"] == record.suite_hash
                    and item["report"]["runtime_profile_hash"]
                    == record.report.runtime_profile_hash
                    and item["report"]["status"] in ("passed", "failed")
                ]
            samples = [*prior, metrics]
            metrics.update(
                {
                    "repeat_count": len(samples),
                    "completion_variance": pvariance(
                        [x["completion_rate"] for x in samples]
                    ),
                    "tool_argument_variance": pvariance(
                        [x["tool_argument_rate"] for x in samples]
                    ),
                }
            )
            report = record.report.model_copy(
                update={
                    "status": (
                        EvaluationStatus.PASSED
                        if passed
                        else EvaluationStatus.FAILED
                    ),
                    "metrics": metrics,
                    "hard_gate_failures": failures,
                    "finished_at": now(),
                }
            )
            return await self._save_evaluation(
                scope, record, record.model_copy(update={"report": report})
            )
        except asyncio.CancelledError:
            # The last committed case and snapshot survive worker shutdown.
            raise
        except LifecycleError as error:
            if error.code == "REVISION_CONFLICT":
                return await self.get_evaluation(scope, evaluation_id)
            report = record.report.model_copy(
                update={
                    "status": EvaluationStatus.ERROR,
                    "hard_gate_failures": (error.code,),
                    "finished_at": now(),
                }
            )
            return await self._save_evaluation(
                scope, record, record.model_copy(update={"report": report})
            )
        except Exception:
            report = record.report.model_copy(
                update={
                    "status": EvaluationStatus.ERROR,
                    "hard_gate_failures": ("RUNNER_ERROR",),
                    "finished_at": now(),
                }
            )
            return await self._save_evaluation(
                scope, record, record.model_copy(update={"report": report})
            )

    async def cancel_evaluation(
        self, scope: Scope, evaluation_id: str
    ) -> EvaluationRecord:
        record = await self.get_evaluation(scope, evaluation_id)
        if record.report.status not in (
            EvaluationStatus.QUEUED,
            EvaluationStatus.RUNNING,
        ):
            return record
        report = record.report.model_copy(
            update={"status": EvaluationStatus.CANCELLED, "finished_at": now()}
        )
        changed = await self._save_evaluation(
            scope, record, record.model_copy(update={"report": report})
        )
        for case in self.suites.get(record.report.suite_version).cases:
            await self.runner.cancel_case(
                scope, canonical_hash([evaluation_id, case["case_id"]])
            )
        return changed
