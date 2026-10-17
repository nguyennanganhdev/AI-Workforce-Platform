# -*- coding: utf-8 -*-
"""Verified AREA_MANAGER membership and identity adapters."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Callable
from uuid import uuid4

from sqlalchemy import column, exists, insert, select, table, update

from ..contracts import ManagerRole, Scope, UnitOfWork
from ._database import SqlAlchemyUnitOfWork
from ._tables import manager_memberships


_VERIFIED = "verified"

_auth_users = table(
    "auth_users",
    column("id"),
    column("tenant_id"),
    column("domain_id"),
    column("area_id"),
    column("role"),
    column("status"),
)
_business_domains = table(
    "business_domains",
    column("id"),
    column("tenant_id"),
    column("status"),
)
_areas = table(
    "areas",
    column("id"),
    column("domain_id"),
    column("status"),
)


def _principal_field(principal: object, name: str) -> object:
    value = getattr(principal, name, None)
    if value is None and isinstance(principal, dict):
        value = principal.get(name)
    return value


def _sql_uow(uow: UnitOfWork | Any) -> Any:
    """Accept the canonical UOW or an owner adapter's AsyncSession.

    Phase-B Execution already exposes its transaction as an AsyncSession.  It
    is safe to join because both surfaces provide ``execute`` and ``bind``;
    repositories still never commit an injected transaction.
    """
    if isinstance(uow, SqlAlchemyUnitOfWork):
        return uow
    if hasattr(uow, "execute") and (
        hasattr(uow, "bind") or hasattr(uow, "get_bind")
    ):
        return uow
    raise TypeError("Workforce SQL adapter requires a SQL unit of work")


class SqlIdentityPort:
    """Resolve scope from verified database state, never token body alone."""

    def __init__(self, uows: Callable[[], SqlAlchemyUnitOfWork]) -> None:
        self._uows = uows

    async def resolve_manager(self, authenticated_principal: object) -> Scope:
        if (
            _principal_field(authenticated_principal, "role")
            != ManagerRole.AREA_MANAGER
        ):
            raise PermissionError("AREA_MANAGER role required")
        account_id = _principal_field(authenticated_principal, "user_id")
        tenant_id = _principal_field(authenticated_principal, "tenant_id")
        if not isinstance(account_id, str) or not isinstance(tenant_id, str):
            raise PermissionError("verified manager principal required")
        async with self._uows() as uow:
            row = await self._load_active(uow, account_id, tenant_id)
        if row is None:
            raise PermissionError("manager membership is not verified")
        scope = Scope(
            tenant_id=row["tenant_id"],
            domain_id=row["domain_id"],
            area_id=row["area_id"],
            manager_account_id=row["manager_account_id"],
        )
        token_domain = _principal_field(authenticated_principal, "domain_id")
        token_area = _principal_field(authenticated_principal, "area_id")
        if token_domain != scope.domain_id or token_area != scope.area_id:
            raise PermissionError("manager token scope is stale")
        return scope

    async def check_scope_active(
        self,
        scope: Scope,
        uow: UnitOfWork | None = None,
    ) -> None:
        if uow is None:
            async with self._uows() as owned:
                await self.check_scope_active(scope, owned)
            return
        row = await self._load_active(
            _sql_uow(uow),
            scope.manager_account_id,
            scope.tenant_id,
        )
        if row is None or any(
            row[key] != value
            for key, value in (
                ("domain_id", scope.domain_id),
                ("area_id", scope.area_id),
            )
        ):
            raise PermissionError("manager scope is inactive")

    @staticmethod
    async def _load_active(
        uow: SqlAlchemyUnitOfWork,
        account_id: str,
        tenant_id: str,
    ) -> Any:
        statement = (
            select(manager_memberships)
            .join(
                _auth_users,
                _auth_users.c.id
                == manager_memberships.c.manager_account_id,
            )
            .join(
                _business_domains,
                _business_domains.c.id == manager_memberships.c.domain_id,
            )
            .join(
                _areas,
                _areas.c.id == manager_memberships.c.area_id,
            )
            .where(
                manager_memberships.c.manager_account_id == account_id,
                manager_memberships.c.tenant_id == tenant_id,
                manager_memberships.c.status == _VERIFIED,
                _auth_users.c.tenant_id == tenant_id,
                _auth_users.c.domain_id == manager_memberships.c.domain_id,
                _auth_users.c.area_id == manager_memberships.c.area_id,
                _auth_users.c.role == ManagerRole.AREA_MANAGER,
                _auth_users.c.status == "active",
                _business_domains.c.tenant_id == tenant_id,
                _business_domains.c.status == "active",
                _areas.c.domain_id == manager_memberships.c.domain_id,
                _areas.c.status == "active",
            )
            .limit(2)
        )
        rows = (await uow.execute(statement)).mappings().all()
        if len(rows) > 1:
            raise RuntimeError("manager has multiple active memberships")
        return rows[0] if rows else None


class ManagementVerificationService:
    """Provision pending membership and apply an audited verification CAS."""

    def __init__(
        self,
        uows: Callable[[], SqlAlchemyUnitOfWork],
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        id_factory: Callable[[], str] = lambda: str(uuid4()),
    ) -> None:
        self._uows = uows
        self._clock = clock
        self._id_factory = id_factory

    async def ensure_pending(
        self,
        scope: Scope,
        uow: UnitOfWork | None = None,
    ) -> int:
        if uow is None:
            async with self._uows() as owned:
                revision = await self.ensure_pending(scope, owned)
                await owned.commit()
                return revision
        sql_uow = _sql_uow(uow)
        existing = (
            await sql_uow.execute(
                select(manager_memberships).where(
                    manager_memberships.c.manager_account_id
                    == scope.manager_account_id,
                ),
            )
        ).mappings().first()
        if existing is not None:
            if any(
                existing[key] != value
                for key, value in scope.model_dump().items()
            ):
                raise ValueError("manager membership scope cannot be replaced")
            return int(existing["revision"])
        now = self._aware_now()
        await sql_uow.execute(
            insert(manager_memberships).values(
                id=self._id_factory(),
                **scope.model_dump(mode="python"),
                status="pending_verification",
                revision=1,
                verified_by=None,
                verified_at=None,
                created_at=now,
                updated_at=now,
            ),
        )
        return 1

    async def verify(
        self,
        scope: Scope,
        expected_revision: int,
        verified_by: str,
        uow: UnitOfWork | None = None,
    ) -> int:
        if not verified_by:
            raise ValueError("verified_by is required")
        if uow is None:
            async with self._uows() as owned:
                revision = await self.verify(
                    scope,
                    expected_revision,
                    verified_by,
                    owned,
                )
                await owned.commit()
                return revision
        now = self._aware_now()
        result = await _sql_uow(uow).execute(
            update(manager_memberships)
            .where(
                manager_memberships.c.manager_account_id
                == scope.manager_account_id,
                manager_memberships.c.tenant_id == scope.tenant_id,
                manager_memberships.c.domain_id == scope.domain_id,
                manager_memberships.c.area_id == scope.area_id,
                manager_memberships.c.revision == expected_revision,
                manager_memberships.c.status == "pending_verification",
                exists(
                    select(_auth_users.c.id)
                    .join(
                        _business_domains,
                        _business_domains.c.id == _auth_users.c.domain_id,
                    )
                    .join(
                        _areas,
                        _areas.c.id == _auth_users.c.area_id,
                    )
                    .where(
                        _auth_users.c.id == scope.manager_account_id,
                        _auth_users.c.tenant_id == scope.tenant_id,
                        _auth_users.c.domain_id == scope.domain_id,
                        _auth_users.c.area_id == scope.area_id,
                        _auth_users.c.role == ManagerRole.AREA_MANAGER,
                        _auth_users.c.status == "active",
                        _business_domains.c.tenant_id == scope.tenant_id,
                        _business_domains.c.status == "active",
                        _areas.c.domain_id == scope.domain_id,
                        _areas.c.status == "active",
                    ),
                ),
            )
            .values(
                status=_VERIFIED,
                revision=expected_revision + 1,
                verified_by=verified_by,
                verified_at=now,
                updated_at=now,
            ),
        )
        if result.rowcount != 1:
            raise ValueError("membership revision or state conflict")
        return expected_revision + 1

    def _aware_now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("clock must return timezone-aware datetime")
        return now


__all__ = ["ManagementVerificationService", "SqlIdentityPort"]
