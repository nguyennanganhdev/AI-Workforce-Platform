# -*- coding: utf-8 -*-
"""Async SQL repository sharing a Foundation session/UOW, without auto-DDL."""

from typing import Any

from contextlib import asynccontextmanager

from sqlalchemy import select, update

from ._tables import (
    metadata,
    tool_calls,
    approvals,
    booking_operations,
    execution_events,
)
from .external_operations._tables import external_operations
from .provider_events._tables import provider_event_inbox
from ._utils import ExecutionError, freeze, owner, require_scope

TABLES = {
    "calls": tool_calls,
    "approvals": approvals,
    "bookings": booking_operations,
    "events": execution_events,
    "operations": external_operations,
    "inbox": provider_event_inbox,
}


class ExecutionRepository:
    """Scoped JSON records plus relational keys, unique constraints and CAS."""

    def __init__(self, session_factory: Any) -> None:
        self.session_factory = session_factory

    @asynccontextmanager
    async def transaction(self) -> Any:
        """Do not use this context across model/provider network calls."""
        async with self.session_factory() as session:
            async with session.begin():
                yield session

    def _where(self, table: Any, filters: Any, scope: Any = None) -> Any:
        clauses = [table.c[k] == v for k, v in filters.items()]
        if scope is not None:
            clauses += [table.c[k] == v for k, v in owner(scope).items()]
        return clauses

    async def find(
        self,
        kind: Any,
        filters: Any,
        uow: Any,
        scope: Any = None,
        lock: Any = False,
    ) -> Any:
        """
        Unscoped lookups are restricted to internal inbox/correlation code.
        """
        table = TABLES[kind]
        stmt = select(table).where(*self._where(table, filters, scope))
        if lock:
            stmt = stmt.with_for_update()
        rows = (await uow.execute(stmt)).mappings().all()
        return [freeze(r["payload"]) for r in rows]

    async def get(
        self,
        kind: Any,
        record_id: Any,
        uow: Any,
        scope: Any = None,
        lock: Any = False,
    ) -> Any:
        """
        Load one persisted record, optionally locking until UOW completion.
        """
        rows = await self.find(kind, {"id": record_id}, uow, scope, lock)
        return rows[0] if rows else None

    def _columns(self, kind: Any, record: Any) -> Any:
        table = TABLES[kind]
        data = {
            "id": record["id"],
            "revision": record.get("revision", 1),
            "payload": freeze(record),
        }
        for col in table.c:
            if col.name in data:
                continue
            if col.name in record:
                data[col.name] = record[col.name]
            elif col.name in record.get("scope", {}):
                data[col.name] = record["scope"][col.name]
        return data

    async def insert_once(
        self, kind: Any, record: Any, filters: Any, uow: Any, scope: Any = None
    ) -> Any:
        """Let the DB serialize duplicates; compare hashes in the caller."""
        table = TABLES[kind]
        dialect = uow.bind.dialect.name
        if dialect == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
        elif dialect == "sqlite":
            from sqlalchemy.dialects.sqlite import insert
        else:
            raise ExecutionError("UNSUPPORTED_EXECUTION_DATABASE", 503)
        stmt = (
            insert(table)
            .values(**self._columns(kind, record))
            .on_conflict_do_nothing()
        )
        await uow.execute(stmt)
        rows = await self.find(kind, filters, uow, scope, lock=True)
        if len(rows) != 1:
            raise ExecutionError("RESOURCE_KEY_CONFLICT")
        return rows[0]

    async def save(
        self, kind: Any, record: Any, expected_revision: Any, uow: Any
    ) -> Any:
        """CAS prevents stale workers from replacing a newer fact."""
        record = freeze(record)
        record["revision"] = expected_revision + 1
        table = TABLES[kind]
        filters = {"id": record["id"], "revision": expected_revision}
        scope = record.get("scope")
        result = await uow.execute(
            update(table)
            .where(
                *self._where(table, filters, scope),
            )
            .values(**self._columns(kind, record))
        )
        if result.rowcount != 1:
            raise ExecutionError("REVISION_CONFLICT")
        return record

    async def read(self, kind: Any, scope: Any, record_id: Any) -> Any:
        """
        Public owner lookup. Provider receipts have their own identity check.
        """
        async with self.transaction() as uow:
            record = await self.get(kind, record_id, uow, scope)
            require_scope(scope, record)
            return record


__all__ = ["ExecutionRepository", "metadata"]
