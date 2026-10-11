# -*- coding: utf-8 -*-
"""SQL implementation of the immutable async protocol repository."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import insert, select, update

from ...contracts import (
    AsyncProtocolSnapshotRef,
    Scope,
    UnitOfWork,
    WorkforceContractError,
    WorkforceErrorCode,
)
from ._models import AsyncToolProtocol
from ._tables import async_protocol_heads, async_protocol_versions


def _sql_uow(uow: UnitOfWork | Any) -> Any:
    if not hasattr(uow, "execute"):
        raise TypeError("Registry SQL repository requires a SQL unit of work")
    if not hasattr(uow, "bind") and not hasattr(uow, "get_bind"):
        raise TypeError("Registry SQL unit of work has no database bind")
    return uow


def _dialect_name(uow: Any) -> str:
    bind = getattr(uow, "bind", None)
    if bind is None and hasattr(uow, "get_bind"):
        bind = uow.get_bind()
    if bind is None or not hasattr(bind, "dialect"):
        raise TypeError("Registry SQL unit of work has no SQLAlchemy dialect")
    return str(bind.dialect.name)


class SqlAsyncProtocolRepository:
    """Persist immutable protocol versions and one CAS current pointer."""

    def __init__(
        self,
        uows: Callable[[], Any],
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        id_factory: Callable[[], str] = lambda: str(uuid4()),
    ) -> None:
        self._uows = uows
        self._clock = clock
        self._id_factory = id_factory

    async def publish(
        self,
        scope: Scope,
        protocol: AsyncToolProtocol,
        expected_snapshot: AsyncProtocolSnapshotRef | None,
        uow: UnitOfWork | None = None,
    ) -> None:
        scope = Scope.model_validate(scope)
        protocol = AsyncToolProtocol.model_validate(protocol)
        reference = protocol.snapshot_ref
        if uow is None:
            async with self._uows() as owned:
                await self.publish(
                    scope,
                    protocol,
                    expected_snapshot,
                    owned,
                )
                await owned.commit()
                return

        sql_uow = _sql_uow(uow)
        head = await self._get_head(
            sql_uow,
            scope,
            protocol.tool_version_id,
            for_update=True,
        )
        if head is not None:
            current = self._head_reference(head)
            if current == reference:
                await self._load_version(sql_uow, scope, reference)
                return
            if expected_snapshot != current:
                self._revision_conflict()
            await self._ensure_version(sql_uow, scope, protocol)
            result = await sql_uow.execute(
                update(async_protocol_heads)
                .where(
                    async_protocol_heads.c.id == head["id"],
                    async_protocol_heads.c.revision == head["revision"],
                    async_protocol_heads.c.current_schema_hash
                    == current.schema_hash,
                )
                .values(
                    current_protocol_id=reference.protocol_id,
                    current_protocol_version=reference.protocol_version,
                    current_schema_hash=reference.schema_hash,
                    current_provider_integration_id=(
                        reference.provider_integration_id
                    ),
                    current_capabilities=list(reference.capabilities),
                    revision=head["revision"] + 1,
                    updated_at=self._now(),
                ),
            )
            if result.rowcount != 1:
                self._revision_conflict()
            return

        if expected_snapshot is not None:
            self._revision_conflict()
        await self._ensure_version(sql_uow, scope, protocol)
        now = self._now()
        values = {
            "id": self._id_factory(),
            **scope.model_dump(mode="python"),
            "tool_version_id": protocol.tool_version_id,
            "current_protocol_id": reference.protocol_id,
            "current_protocol_version": reference.protocol_version,
            "current_schema_hash": reference.schema_hash,
            "current_provider_integration_id": (
                reference.provider_integration_id
            ),
            "current_capabilities": list(reference.capabilities),
            "enabled": True,
            "revision": 1,
            "created_at": now,
            "updated_at": now,
        }
        result = await sql_uow.execute(
            self._insert_ignore(sql_uow, async_protocol_heads, values),
        )
        if result.rowcount == 1:
            return
        concurrent = await self._get_head(
            sql_uow,
            scope,
            protocol.tool_version_id,
            for_update=True,
        )
        if concurrent is None:
            self._revision_conflict()
        if self._head_reference(concurrent) != reference:
            self._revision_conflict()
        await self._load_version(sql_uow, scope, reference)

    async def get_current(
        self,
        scope: Scope,
        tool_version_id: str,
    ) -> tuple[AsyncToolProtocol, bool]:
        scope = Scope.model_validate(scope)
        async with self._uows() as uow:
            head = await self._get_head(uow, scope, tool_version_id)
            if head is None:
                raise KeyError("async protocol head not found")
            protocol = await self._load_version(
                uow,
                scope,
                self._head_reference(head),
            )
            return protocol, bool(head["enabled"])

    async def get_pinned(
        self,
        scope: Scope,
        snapshot: AsyncProtocolSnapshotRef,
    ) -> AsyncToolProtocol:
        scope = Scope.model_validate(scope)
        snapshot = AsyncProtocolSnapshotRef.model_validate(snapshot)
        async with self._uows() as uow:
            return await self._load_version(uow, scope, snapshot)

    async def set_enabled(
        self,
        scope: Scope,
        tool_version_id: str,
        enabled: bool,
        expected_snapshot: AsyncProtocolSnapshotRef,
        uow: UnitOfWork | None = None,
    ) -> None:
        scope = Scope.model_validate(scope)
        expected_snapshot = AsyncProtocolSnapshotRef.model_validate(
            expected_snapshot,
        )
        if expected_snapshot.tool_version_id != tool_version_id:
            self._revision_conflict()
        if uow is None:
            async with self._uows() as owned:
                await self.set_enabled(
                    scope,
                    tool_version_id,
                    enabled,
                    expected_snapshot,
                    owned,
                )
                await owned.commit()
                return

        sql_uow = _sql_uow(uow)
        head = await self._get_head(
            sql_uow,
            scope,
            tool_version_id,
            for_update=True,
        )
        if head is None:
            raise KeyError("async protocol head not found")
        if self._head_reference(head) != expected_snapshot:
            self._revision_conflict()
        await self._load_version(sql_uow, scope, expected_snapshot)
        if bool(head["enabled"]) is enabled:
            return
        result = await sql_uow.execute(
            update(async_protocol_heads)
            .where(
                async_protocol_heads.c.id == head["id"],
                async_protocol_heads.c.revision == head["revision"],
                async_protocol_heads.c.current_schema_hash
                == expected_snapshot.schema_hash,
            )
            .values(
                enabled=enabled,
                revision=head["revision"] + 1,
                updated_at=self._now(),
            ),
        )
        if result.rowcount != 1:
            self._revision_conflict()

    async def _ensure_version(
        self,
        uow: Any,
        scope: Scope,
        protocol: AsyncToolProtocol,
    ) -> None:
        reference = protocol.snapshot_ref
        values = {
            "id": self._id_factory(),
            **scope.model_dump(mode="python"),
            "tool_version_id": reference.tool_version_id,
            "protocol_id": reference.protocol_id,
            "protocol_version": reference.protocol_version,
            "schema_hash": reference.schema_hash,
            "configuration": protocol.model_dump(mode="json"),
            "created_at": self._now(),
        }
        await uow.execute(
            self._insert_ignore(uow, async_protocol_versions, values),
        )
        try:
            await self._load_version(uow, scope, reference)
        except ValueError as exc:
            raise WorkforceContractError(
                WorkforceErrorCode.IDEMPOTENCY_CONFLICT,
                "protocol version already has different content",
            ) from exc

    @staticmethod
    async def _get_head(
        uow: Any,
        scope: Scope,
        tool_version_id: str,
        *,
        for_update: bool = False,
    ) -> Any | None:
        statement = select(async_protocol_heads).where(
            *SqlAsyncProtocolRepository._scope_filter(
                async_protocol_heads,
                scope,
            ),
            async_protocol_heads.c.tool_version_id == tool_version_id,
        )
        if for_update and _dialect_name(uow) == "postgresql":
            statement = statement.with_for_update()
        rows = (await uow.execute(statement.limit(2))).mappings().all()
        if len(rows) > 1:
            raise RuntimeError("async protocol head is ambiguous")
        return rows[0] if rows else None

    @staticmethod
    async def _load_version(
        uow: Any,
        scope: Scope,
        reference: AsyncProtocolSnapshotRef,
    ) -> AsyncToolProtocol:
        statement = select(async_protocol_versions).where(
            *SqlAsyncProtocolRepository._scope_filter(
                async_protocol_versions,
                scope,
            ),
            async_protocol_versions.c.tool_version_id
            == reference.tool_version_id,
            async_protocol_versions.c.protocol_id == reference.protocol_id,
            async_protocol_versions.c.protocol_version
            == reference.protocol_version,
        )
        rows = (await uow.execute(statement.limit(2))).mappings().all()
        if len(rows) > 1:
            raise RuntimeError("async protocol version is ambiguous")
        if not rows:
            raise KeyError("async protocol version not found")
        row = rows[0]
        protocol = AsyncToolProtocol.model_validate(row["configuration"])
        if (
            row["schema_hash"] != reference.schema_hash
            or protocol.snapshot_ref != reference
        ):
            raise ValueError("async protocol snapshot mismatch")
        return protocol

    @staticmethod
    def _head_reference(row: Any) -> AsyncProtocolSnapshotRef:
        protocol = AsyncProtocolSnapshotRef(
            protocol_id=row["current_protocol_id"],
            protocol_version=row["current_protocol_version"],
            schema_hash=row["current_schema_hash"],
            tool_version_id=row["tool_version_id"],
            provider_integration_id=row[
                "current_provider_integration_id"
            ],
            capabilities=tuple(row["current_capabilities"]),
        )
        return protocol

    @staticmethod
    def _scope_filter(table: Any, scope: Scope) -> tuple[Any, ...]:
        return (
            table.c.tenant_id == scope.tenant_id,
            table.c.domain_id == scope.domain_id,
            table.c.area_id == scope.area_id,
            table.c.manager_account_id == scope.manager_account_id,
        )

    @staticmethod
    def _insert_ignore(uow: Any, table: Any, values: dict[str, Any]) -> Any:
        dialect = _dialect_name(uow)
        if dialect == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as pg_insert

            return pg_insert(table).values(**values).on_conflict_do_nothing()
        if dialect == "sqlite":
            from sqlalchemy.dialects.sqlite import insert as sqlite_insert

            return (
                sqlite_insert(table)
                .values(**values)
                .on_conflict_do_nothing()
            )
        raise RuntimeError(
            "async protocol SQL repository supports PostgreSQL and SQLite",
        )

    @staticmethod
    def _revision_conflict() -> None:
        raise WorkforceContractError(
            WorkforceErrorCode.REVISION_CONFLICT,
            "current async protocol changed",
        )

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("clock must return timezone-aware datetime")
        return now


__all__ = ["SqlAsyncProtocolRepository"]
