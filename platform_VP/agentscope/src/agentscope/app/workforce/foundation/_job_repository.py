# -*- coding: utf-8 -*-
"""PostgreSQL/SQLite durable-job repository with lease fencing."""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
from typing import Any, Callable

from sqlalchemy import and_, insert, or_, select, update

from ..contracts import Scope, UnitOfWork
from ._database import SqlAlchemyUnitOfWork
from ._identity import _sql_uow
from ._tables import durable_jobs
from .event_delivery import (
    DurableJob,
    JobLeaseLostError,
    JobOwnerKind,
    JobStatus,
)


def _json_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _namespace(job: DurableJob) -> str:
    if job.scope is not None:
        values = (
            "scope",
            job.scope.tenant_id,
            job.scope.domain_id,
            job.scope.area_id,
            job.scope.manager_account_id,
        )
    else:
        values = (
            "provider",
            job.tenant_id,
            job.provider_integration_id or "",
        )
    canonical = "".join(f"{len(value)}:{value}" for value in values)
    return sha256(canonical.encode("utf-8")).hexdigest()


class SqlDurableJobRepository:
    """Atomic job persistence used by :class:`DurableJobService`."""

    def __init__(self, uows: Callable[[], SqlAlchemyUnitOfWork]) -> None:
        self._uows = uows

    async def enqueue_once(
        self,
        job: DurableJob,
        uow: UnitOfWork | None = None,
    ) -> DurableJob:
        if uow is None:
            async with self._uows() as owned:
                stored = await self.enqueue_once(job, owned)
                await owned.commit()
                return stored
        sql_uow = _sql_uow(uow)
        values = self._values(job)
        statement = self._insert_ignore(sql_uow, values)
        await sql_uow.execute(statement)
        row = (
            await sql_uow.execute(
                select(durable_jobs).where(
                    durable_jobs.c.owner_namespace
                    == values["owner_namespace"],
                    durable_jobs.c.idempotency_key == job.idempotency_key,
                ),
            )
        ).mappings().one()
        if row["payload_hash"] != values["payload_hash"]:
            raise ValueError("idempotency key reused with different payload")
        if row["job_type"] != job.job_type:
            raise ValueError("idempotency key reused with different job type")
        return self._model(row)

    async def claim_next(
        self,
        worker_id: str,
        now: datetime,
        lease_expires_at: datetime,
    ) -> DurableJob | None:
        async with self._uows() as uow:
            statement = (
                select(durable_jobs)
                .where(
                    durable_jobs.c.not_before <= now,
                    or_(
                        durable_jobs.c.status == JobStatus.PENDING,
                        and_(
                            durable_jobs.c.status == JobStatus.LEASED,
                            durable_jobs.c.lease_expires_at.is_not(None),
                            durable_jobs.c.lease_expires_at <= now,
                        ),
                    ),
                )
                .order_by(durable_jobs.c.not_before, durable_jobs.c.created_at)
                .limit(1)
            )
            if uow.bind.dialect.name == "postgresql":
                statement = statement.with_for_update(skip_locked=True)
            row = (await uow.execute(statement)).mappings().first()
            if row is None:
                return None
            result = await uow.execute(
                update(durable_jobs)
                .where(
                    durable_jobs.c.id == row["id"],
                    durable_jobs.c.fencing_token == row["fencing_token"],
                )
                .values(
                    status=JobStatus.LEASED,
                    attempt=row["attempt"] + 1,
                    lease_owner=worker_id,
                    lease_expires_at=lease_expires_at,
                    fencing_token=row["fencing_token"] + 1,
                    updated_at=now,
                ),
            )
            if result.rowcount != 1:
                await uow.rollback()
                return None
            await uow.commit()
            return self._model(
                {
                    **dict(row),
                    "status": JobStatus.LEASED,
                    "attempt": row["attempt"] + 1,
                    "lease_owner": worker_id,
                    "lease_expires_at": lease_expires_at,
                    "fencing_token": row["fencing_token"] + 1,
                    "updated_at": now,
                },
            )

    async def renew_lease(
        self,
        job_id: str,
        worker_id: str,
        fencing_token: int,
        now: datetime,
        lease_expires_at: datetime,
    ) -> DurableJob:
        return await self._fenced_update(
            job_id,
            worker_id,
            fencing_token,
            now,
            {"lease_expires_at": lease_expires_at, "updated_at": now},
        )

    async def complete(
        self,
        job_id: str,
        worker_id: str,
        fencing_token: int,
        result: dict[str, Any],
        now: datetime,
    ) -> DurableJob:
        return await self._fenced_update(
            job_id,
            worker_id,
            fencing_token,
            now,
            {
                "status": JobStatus.SUCCEEDED,
                "result": result,
                "lease_owner": None,
                "lease_expires_at": None,
                "updated_at": now,
            },
        )

    async def fail(
        self,
        job_id: str,
        worker_id: str,
        fencing_token: int,
        error: dict[str, Any],
        now: datetime,
        retry_at: datetime,
    ) -> DurableJob:
        async with self._uows() as uow:
            row = await self._locked_claim(
                uow,
                job_id,
                worker_id,
                fencing_token,
                now,
            )
            terminal = row["attempt"] >= row["max_attempts"]
            values = {
                "status": JobStatus.FAILED if terminal else JobStatus.PENDING,
                "error": error,
                "not_before": retry_at,
                "lease_owner": None,
                "lease_expires_at": None,
                "updated_at": now,
            }
            await self._update_claim(uow, row, values)
            await uow.commit()
            return self._model({**dict(row), **values})

    async def _fenced_update(
        self,
        job_id: str,
        worker_id: str,
        fencing_token: int,
        now: datetime,
        values: dict[str, Any],
    ) -> DurableJob:
        async with self._uows() as uow:
            row = await self._locked_claim(
                uow,
                job_id,
                worker_id,
                fencing_token,
                now,
            )
            await self._update_claim(uow, row, values)
            await uow.commit()
            return self._model({**dict(row), **values})

    @staticmethod
    async def _locked_claim(
        uow: SqlAlchemyUnitOfWork,
        job_id: str,
        worker_id: str,
        fencing_token: int,
        now: datetime,
    ) -> Any:
        statement = select(durable_jobs).where(
            durable_jobs.c.id == job_id,
            durable_jobs.c.status == JobStatus.LEASED,
            durable_jobs.c.lease_owner == worker_id,
            durable_jobs.c.fencing_token == fencing_token,
            durable_jobs.c.lease_expires_at.is_not(None),
            durable_jobs.c.lease_expires_at > now,
        )
        if uow.bind.dialect.name == "postgresql":
            statement = statement.with_for_update()
        row = (await uow.execute(statement)).mappings().first()
        if row is None:
            raise JobLeaseLostError(f"stale or expired lease for job {job_id}")
        return row

    @staticmethod
    async def _update_claim(
        uow: SqlAlchemyUnitOfWork,
        row: Any,
        values: dict[str, Any],
    ) -> None:
        result = await uow.execute(
            update(durable_jobs)
            .where(
                durable_jobs.c.id == row["id"],
                durable_jobs.c.status == JobStatus.LEASED,
                durable_jobs.c.lease_owner == row["lease_owner"],
                durable_jobs.c.fencing_token == row["fencing_token"],
            )
            .values(**values),
        )
        if result.rowcount != 1:
            raise JobLeaseLostError(f"stale fence for job {row['id']}")

    @staticmethod
    def _insert_ignore(
        uow: Any,
        values: dict[str, Any],
    ) -> Any:
        bind = uow.bind if uow.bind is not None else uow.get_bind()
        dialect = bind.dialect.name
        if dialect == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as dialect_insert

            return (
                dialect_insert(durable_jobs)
                .values(**values)
                .on_conflict_do_nothing(
                    constraint="uq_wf_job_owner_idempotency",
                )
            )
        if dialect == "sqlite":
            from sqlalchemy.dialects.sqlite import insert as dialect_insert

            return (
                dialect_insert(durable_jobs)
                .values(**values)
                .on_conflict_do_nothing(
                    index_elements=["owner_namespace", "idempotency_key"],
                )
            )
        return insert(durable_jobs).values(**values)

    @staticmethod
    def _values(job: DurableJob) -> dict[str, Any]:
        scope = job.scope
        return {
            "id": job.job_id,
            "owner_kind": job.owner_kind,
            "owner_namespace": _namespace(job),
            "tenant_id": job.tenant_id,
            "domain_id": scope.domain_id if scope else None,
            "area_id": scope.area_id if scope else None,
            "manager_account_id": scope.manager_account_id if scope else None,
            "provider_integration_id": job.provider_integration_id,
            "job_type": job.job_type,
            "payload": job.payload,
            "payload_hash": _json_hash(
                {"job_type": job.job_type, "payload": job.payload},
            ),
            "idempotency_key": job.idempotency_key,
            "status": job.status,
            "attempt": job.attempt,
            "max_attempts": job.max_attempts,
            "not_before": job.not_before,
            "lease_owner": job.lease_owner,
            "lease_expires_at": job.lease_expires_at,
            "fencing_token": job.fencing_token,
            "result": job.result,
            "error": job.error,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
        }

    @staticmethod
    def _model(row: Any) -> DurableJob:
        scope = None
        if row["owner_kind"] == JobOwnerKind.SCOPE:
            scope = Scope(
                tenant_id=row["tenant_id"],
                domain_id=row["domain_id"],
                area_id=row["area_id"],
                manager_account_id=row["manager_account_id"],
            )
        return DurableJob(
            job_id=row["id"],
            owner_kind=row["owner_kind"],
            scope=scope,
            tenant_id=row["tenant_id"],
            provider_integration_id=row["provider_integration_id"],
            job_type=row["job_type"],
            payload=row["payload"],
            idempotency_key=row["idempotency_key"],
            status=row["status"],
            attempt=row["attempt"],
            max_attempts=row["max_attempts"],
            not_before=row["not_before"],
            lease_owner=row["lease_owner"],
            lease_expires_at=row["lease_expires_at"],
            fencing_token=row["fencing_token"],
            result=row["result"],
            error=row["error"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


__all__ = ["SqlDurableJobRepository"]
