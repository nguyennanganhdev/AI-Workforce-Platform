"""Durable evaluation jobs; scope and frozen input are loaded from SQL."""

from typing import Any, Dict

from sqlalchemy import update

from ...contracts import EvaluationSnapshot, JobPort, Scope
from .._models import EvaluationRecord
from ._evaluation import (
    AsyncEvaluationService,
    FrozenEvaluation,
    check_release_evidence,
    grade_case,
)
from ._repository import SqlEvaluationRepository
from ._repository import scoped
from ._tables import case_runs
from ._runtime import RuntimeEvaluationRunner
from ._suites import LifecycleSuite


class EvaluationJobService:
    job_type = "workforce.lifecycle.evaluate"

    def __init__(self, repository: SqlEvaluationRepository, jobs: JobPort) -> None:
        self.repository = repository
        self.jobs = jobs

    async def enqueue(
        self, scope: Scope, evaluation_id: str, frozen: FrozenEvaluation
    ) -> str:
        async with self.repository.uows() as tx:
            await self.repository.register(scope, evaluation_id, frozen, tx)
            job_id = await self.jobs.enqueue(
                scope,
                self.job_type,
                {"evaluation_id": evaluation_id},
                "evaluation:" + evaluation_id,
                tx,
            )
            await tx.commit()
            return job_id


class EvaluationJobHandler:
    job_type = EvaluationJobService.job_type

    def __init__(
        self, repository: SqlEvaluationRepository, service: AsyncEvaluationService
    ) -> None:
        self.repository = repository
        self.service = service

    async def __call__(self, job: Any) -> Dict[str, str]:
        if job.job_type != self.job_type or job.scope is None:
            raise ValueError("SCOPED_EVALUATION_JOB_REQUIRED")
        evaluation_id = job.payload["evaluation_id"]
        frozen = await self.repository.load(job.scope, evaluation_id)
        record = await self.repository.load_record(job.scope, evaluation_id)
        if record is None:
            record = await self.service.run(job.scope, frozen, evaluation_id)
            await self.repository.save_record(record)
        return {"evaluation_id": evaluation_id, "status": record.report.status.value}


async def check_persisted_release(
    repository: SqlEvaluationRepository,
    scope: Scope,
    evaluation_id: str,
    current: FrozenEvaluation,
    uow: Any = None,
) -> EvaluationRecord:
    """Authoritative scoped prewrite hook; publishing remains a caller action."""
    if uow is not None:
        repository = repository.in_transaction(uow)
        # Cancellation is mutable. Lock the cases through the publish commit
        # so it cannot invalidate evidence between verification and activation.
        payload = current.read(scope)
        for case in payload["suite"]["cases"]:
            await uow.execute(
                update(case_runs)
                .where(
                    *scoped(
                        case_runs,
                        scope,
                        {
                            "snapshot_id": payload["snapshot"]["snapshot_id"],
                            "case_id": case["case_id"],
                        },
                    )
                )
                .values(cancelled=case_runs.c.cancelled)
            )
    record = await repository.load_record(scope, evaluation_id)
    if record is None:
        raise ValueError("INCOMPLETE_EVALUATION")
    check_release_evidence(scope, record, current)
    # C5 release requires retained production-runtime evidence. A Phase-B fake
    # report or cancelled/deleted/tampered case cannot satisfy this SQL hook.
    payload = current.read(scope)
    suite = LifecycleSuite.model_validate(payload["suite"])
    verifier = RuntimeEvaluationRunner(repository)
    for case, saved in zip(suite.cases, record.report.cases):
        result = await verifier.run_case(
            scope,
            EvaluationSnapshot.model_validate(payload["snapshot"]),
            {
                **suite.runner_input(case),
                "runtime_profile": payload["runtime_profile"],
                "test_context": payload["test_context"],
                "protocol_refs": payload["dependencies"]["protocol_refs"],
            },
            "mock",
        )
        if grade_case(case, result) != saved:
            raise ValueError("RUNTIME_REPORT_EVIDENCE_MISMATCH")
    return record
