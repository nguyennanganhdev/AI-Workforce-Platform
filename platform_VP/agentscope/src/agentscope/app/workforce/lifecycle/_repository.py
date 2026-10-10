"""Scoped SQL repository with catalog fencing, CAS and immutable inserts."""

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Type

from sqlalchemy import and_, delete, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..contracts import Scope
from ._models import LifecycleError
from ._tables import TABLES, catalogs


def scope_filter(table: Any, scope: Scope) -> Any:
    return and_(
        *(table.c[key] == value for key, value in scope.model_dump().items())
    )


class LifecycleTransaction:
    """Local UoW adapter; shared JobPort must join this SQL session."""

    def __init__(self, session: AsyncSession, scope: Scope) -> None:
        self.session = session
        self.scope = scope
        self.callbacks: List[Callable[..., Any]] = []

    def add_after_commit(self, callback: Callable[..., Any]) -> None:
        self.callbacks.append(callback)

    async def __aenter__(self) -> "LifecycleTransaction":
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Any,
    ) -> Optional[bool]:
        return None

    async def commit(self) -> None:
        raise RuntimeError("LifecycleRepository owns the transaction")

    async def rollback(self) -> None:
        raise RuntimeError("LifecycleRepository owns the transaction")

    async def get(self, kind: str, record_id: str) -> Dict[str, Any]:
        table = TABLES[kind]
        row = (
            await self.session.execute(
                select(table.c.payload).where(
                    table.c.id == record_id,
                    scope_filter(table, self.scope),
                )
            )
        ).first()
        if row is None:
            raise LifecycleError("RESOURCE_NOT_FOUND", 404)
        return row[0]

    async def maybe_get(
        self, kind: str, record_id: str
    ) -> Optional[Dict[str, Any]]:
        try:
            return await self.get(kind, record_id)
        except LifecycleError as error:
            if error.status != 404:
                raise
            return None

    async def list(self, kind: str) -> List[Dict[str, Any]]:
        table = TABLES[kind]
        rows = await self.session.execute(
            select(table.c.payload)
            .where(
                scope_filter(table, self.scope),
            )
            .order_by(table.c.id)
        )
        return [row[0] for row in rows]

    async def insert(
        self,
        kind: str,
        record_id: str,
        payload: Dict[str, Any],
        revision: int = 1,
    ) -> None:
        values = dict(
            id=record_id,
            revision=revision,
            payload=payload,
            **self.scope.model_dump(),
        )
        if kind == "agents":
            values["business_key"] = payload["business_key"]
            values["legacy_agent_id"] = payload.get("legacy_agent_id")
        if "agent_id" in TABLES[kind].c:
            values["agent_id"] = (
                payload.get("agent_id") or payload["snapshot"]["agent_id"]
            )
        await self.session.execute(insert(TABLES[kind]).values(**values))

    async def save(
        self,
        kind: str,
        record_id: str,
        payload: Dict[str, Any],
        expected_revision: int,
    ) -> None:
        if kind in (
            "versions",
            "reuse_checks",
            "receipts",
            "snapshots",
            "suites",
            "cases",
            "release_events",
        ):
            raise LifecycleError("IMMUTABLE_RECORD")
        table = TABLES[kind]
        values = dict(
            payload=dict(payload, revision=expected_revision + 1),
            revision=expected_revision + 1,
        )
        if kind == "agents":
            values["business_key"] = payload["business_key"]
            values["legacy_agent_id"] = payload.get("legacy_agent_id")
        result = await self.session.execute(
            update(table)
            .where(
                table.c.id == record_id,
                scope_filter(table, self.scope),
                table.c.revision == expected_revision,
            )
            .values(**values)
        )
        if result.rowcount != 1:
            raise LifecycleError("REVISION_CONFLICT")

    async def delete_batch_record(self, kind: str, record_id: str) -> None:
        if kind not in ("batches", "batch_items"):
            raise LifecycleError("RETENTION_REQUIRED")
        table = TABLES[kind]
        await self.session.execute(
            delete(table).where(
                table.c.id == record_id, scope_filter(table, self.scope)
            )
        )

    async def catalog_revision(self) -> int:
        row = (
            await self.session.execute(
                select(catalogs.c.revision).where(
                    scope_filter(catalogs, self.scope),
                )
            )
        ).first()
        return row[0] if row else 0

    async def fence_catalog(self, expected_revision: int) -> int:
        """Serialize identity/release mutations, including different build
        IDs."""
        if expected_revision == 0:
            await self.session.execute(
                insert(catalogs).values(
                    **self.scope.model_dump(),
                    revision=1,
                )
            )
        else:
            result = await self.session.execute(
                update(catalogs)
                .where(
                    scope_filter(catalogs, self.scope),
                    catalogs.c.revision == expected_revision,
                )
                .values(revision=expected_revision + 1)
            )
            if result.rowcount != 1:
                raise LifecycleError("REUSE_DECISION_STALE")
        return expected_revision + 1


class LifecycleRepository:
    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self.session_factory = session_factory

    @asynccontextmanager
    async def transaction(
        self, scope: Scope
    ) -> AsyncIterator[LifecycleTransaction]:
        callbacks: List[Callable[..., Any]] = []
        try:
            async with self.session_factory() as session:
                async with session.begin():
                    tx = LifecycleTransaction(session, scope)
                    yield tx
                    callbacks = tx.callbacks
        except IntegrityError as error:
            raise LifecycleError("CONCURRENT_MUTATION") from error
        for callback in callbacks:
            await callback()

    async def get(
        self, scope: Scope, kind: str, record_id: str
    ) -> Dict[str, Any]:
        async with self.transaction(scope) as tx:
            return await tx.get(kind, record_id)
