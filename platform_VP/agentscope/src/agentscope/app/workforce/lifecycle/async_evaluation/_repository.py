"""Scoped immutable evaluation storage using the canonical injected SQL UOW."""

from typing import Any, Dict, List, Mapping, Optional

from sqlalchemy import select

from ...contracts import Scope, UnitOfWorkFactory
from ...orchestration.workflows import CommittedTurnEvidence
from .._models import EvaluationRecord
from ._evaluation import FrozenEvaluation
from ._tables import case_runs, evaluations, turn_evidence
from ._validation import canonical_hash


def scoped(table: Any, scope: Scope, keys: Mapping[str, Any]) -> List[Any]:
    if set(keys).intersection(scope.model_dump()):
        raise ValueError("EVALUATION_SCOPE_OVERRIDE")
    return [
        table.c[key] == value for key, value in {**scope.model_dump(), **keys}.items()
    ]


class SqlEvaluationRepository:
    """No schema creation; injected transactions are never committed here."""

    def __init__(self, uows: UnitOfWorkFactory) -> None:
        self.uows = uows

    async def read(
        self, table: Any, scope: Scope, keys: Mapping[str, Any], uow: Any = None
    ) -> Optional[Dict[str, Any]]:
        if uow is None:
            async with self.uows() as tx:
                return await self.read(table, scope, keys, tx)
        row = await uow.execute(select(table).where(*scoped(table, scope, keys)))
        value = row.mappings().one_or_none()
        return dict(value) if value is not None else None

    async def put(
        self,
        table: Any,
        scope: Scope,
        keys: Mapping[str, Any],
        values: Mapping[str, Any],
        uow: Any = None,
    ) -> None:
        if uow is None:
            async with self.uows() as tx:
                await self.put(table, scope, keys, values, tx)
                await tx.commit()
                return
        if uow.bind.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
        elif uow.bind.dialect.name == "sqlite":
            from sqlalchemy.dialects.sqlite import insert
        else:
            raise ValueError("UNSUPPORTED_EVALUATION_DATABASE")
        await uow.execute(
            insert(table)
            .values(**scope.model_dump(), **keys, **values)
            .on_conflict_do_nothing()
        )
        stored = await self.read(table, scope, keys, uow)
        if stored is None or any(stored[key] != value for key, value in values.items()):
            raise ValueError("IMMUTABLE_EVALUATION_CONFLICT")

    async def register(
        self,
        scope: Scope,
        evaluation_id: str,
        frozen: FrozenEvaluation,
        uow: Any = None,
    ) -> None:
        payload = frozen.read(scope)
        await self.put(
            evaluations,
            scope,
            {"evaluation_id": evaluation_id},
            {
                "snapshot_id": payload["snapshot"]["snapshot_id"],
                "content_hash": frozen.content_hash,
                "frozen": frozen.model_dump(mode="json"),
            },
            uow,
        )

    async def load(self, scope: Scope, evaluation_id: str) -> FrozenEvaluation:
        row = await self.read(evaluations, scope, {"evaluation_id": evaluation_id})
        if row is None:
            raise KeyError("evaluation not found in owner scope")
        frozen = FrozenEvaluation.model_validate(row["frozen"])
        frozen.read(scope)
        if frozen.content_hash != row["content_hash"]:
            raise ValueError("EVALUATION_CONTENT_DRIFT")
        return frozen

    async def save_record(self, record: EvaluationRecord) -> None:
        from sqlalchemy import update

        key = {"evaluation_id": record.report.evaluation_id}
        async with self.uows() as tx:
            row = await self.read(evaluations, record.scope, key, tx)
            if row is None or record.snapshot.snapshot_id != row["snapshot_id"]:
                raise ValueError("EVALUATION_SNAPSHOT_MISMATCH")
            if record.artifacts.get("frozen_content_hash") != row["content_hash"]:
                raise ValueError("EVALUATION_CONTENT_DRIFT")
            data = record.model_dump(mode="json")
            digest = canonical_hash(data)
            await tx.execute(
                update(evaluations)
                .where(
                    *scoped(evaluations, record.scope, key),
                    evaluations.c.record.is_(None),
                )
                .values(record=data, record_hash=digest)
            )
            stored = await self.read(evaluations, record.scope, key, tx)
            if (
                stored is None
                or stored["record"] != data
                or stored["record_hash"] != digest
            ):
                raise ValueError("IMMUTABLE_EVALUATION_CONFLICT")
            await tx.commit()

    async def load_record(
        self, scope: Scope, evaluation_id: str
    ) -> Optional[EvaluationRecord]:
        row = await self.read(evaluations, scope, {"evaluation_id": evaluation_id})
        if row is None:
            raise KeyError("evaluation not found in owner scope")
        if row["record"] is None:
            return None
        if canonical_hash(row["record"]) != row["record_hash"]:
            raise ValueError("EVALUATION_CONTENT_DRIFT")
        record = EvaluationRecord.model_validate(row["record"])
        if record.scope != scope or record.report.evaluation_id != evaluation_id:
            raise ValueError("EVALUATION_SCOPE_MISMATCH")
        return record

    async def evidence(
        self, scope: Scope, workflow_id: str
    ) -> List[CommittedTurnEvidence]:
        async with self.uows() as tx:
            rows = (
                (
                    await tx.execute(
                        select(turn_evidence)
                        .where(
                            *scoped(turn_evidence, scope, {"workflow_id": workflow_id})
                        )
                        .order_by(turn_evidence.c.after_revision)
                    )
                )
                .mappings()
                .all()
            )
        result = []
        for row in rows:
            if canonical_hash(row["payload"]) != row["content_hash"]:
                raise ValueError("RUNTIME_EVIDENCE_DRIFT")
            evidence = CommittedTurnEvidence.model_validate(row["payload"])
            if (
                evidence.workflow_id != row["workflow_id"]
                or evidence.trigger_id != row["trigger_id"]
                or evidence.after_revision != row["after_revision"]
            ):
                raise ValueError("RUNTIME_EVIDENCE_CONTEXT_MISMATCH")
            result.append(evidence)
        return result


class SqlRuntimeEvidenceWriter:
    """Bind one Scope to C4's RuntimeEvidenceWriter; join the turn transaction."""

    def __init__(self, repository: SqlEvaluationRepository, scope: Scope) -> None:
        self.repository = repository
        self.scope = scope

    async def record(self, evidence: CommittedTurnEvidence, uow: Any) -> None:
        evidence = CommittedTurnEvidence.model_validate(evidence.model_dump())
        # Lifecycle owns this association. Never read/write workflow tables.
        row = await self.repository.read(
            case_runs, self.scope, {"workflow_id": evidence.workflow_id}, uow
        )
        if row is None:
            raise ValueError("UNREGISTERED_EVALUATION_WORKFLOW")
        if row["cancelled"]:
            raise ValueError("RUNTIME_CASE_CANCELLED")
        if evidence.after_revision != evidence.before_revision + 1:
            raise ValueError("INVALID_EVIDENCE_REVISION")
        payload = evidence.model_dump(mode="json")
        await self.repository.put(
            turn_evidence,
            self.scope,
            {"workflow_id": evidence.workflow_id, "trigger_id": evidence.trigger_id},
            {
                "after_revision": evidence.after_revision,
                "payload": payload,
                "content_hash": canonical_hash(payload),
            },
            uow,
        )
