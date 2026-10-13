# -*- coding: utf-8 -*-
"""Partner-to-manager route grant lifecycle with revision guards."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Callable
from uuid import uuid4

from sqlalchemy import exists, insert, select, update

from ..contracts import (
    ActorContext,
    ActorKind,
    CredentialPurpose,
    PartnerManagerRoute,
    PartnerOperation,
    PartnerRouteStatus,
    Scope,
    UnitOfWork,
)
from ._database import SqlAlchemyUnitOfWork
from ._identity import _sql_uow
from ._tables import manager_memberships, partner_manager_routes


class PartnerRouteGrantService:
    """Create, partner-confirm and revoke one exact manager route."""

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

    async def create_pending(
        self,
        scope: Scope,
        partner_client_id: str,
        external_management_ref: str,
        operations: Sequence[PartnerOperation],
        granted_by: str,
        uow: UnitOfWork | None = None,
    ) -> PartnerManagerRoute:
        if (
            not partner_client_id
            or not external_management_ref
            or not granted_by
        ):
            raise ValueError("route identity fields are required")
        allowed = tuple(
            dict.fromkeys(PartnerOperation(item) for item in operations),
        )
        if not allowed:
            raise ValueError("route requires at least one operation")
        if uow is None:
            async with self._uows() as owned:
                route = await self.create_pending(
                    scope,
                    partner_client_id,
                    external_management_ref,
                    allowed,
                    granted_by,
                    owned,
                )
                await owned.commit()
                return route
        sql_uow = _sql_uow(uow)
        membership = (
            await sql_uow.execute(
                select(manager_memberships).where(
                    manager_memberships.c.tenant_id == scope.tenant_id,
                    manager_memberships.c.domain_id == scope.domain_id,
                    manager_memberships.c.area_id == scope.area_id,
                    manager_memberships.c.manager_account_id
                    == scope.manager_account_id,
                    manager_memberships.c.status == "verified",
                ),
            )
        ).mappings().one_or_none()
        if membership is None:
            raise PermissionError("verified manager membership required")
        now = self._now()
        route_id = self._id_factory()
        values = {
            "id": route_id,
            **scope.model_dump(mode="python"),
            "partner_client_id": partner_client_id,
            "external_management_ref": external_management_ref,
            "status": PartnerRouteStatus.PENDING_CONFIRMATION,
            "revision": 1,
            "membership_revision": membership["revision"],
            "allowed_operations": [item.value for item in allowed],
            "granted_by": granted_by,
            "confirmed_by_client_id": None,
            "created_at": now,
            "updated_at": now,
        }
        await sql_uow.execute(insert(partner_manager_routes).values(**values))
        return self._model(values)

    async def confirm(
        self,
        actor: ActorContext,
        route_id: str,
        expected_revision: int,
        uow: UnitOfWork | None = None,
    ) -> PartnerManagerRoute:
        if (
            actor.kind != ActorKind.PARTNER
            or actor.credential_purpose != CredentialPurpose.CUSTOMER_API
            or actor.partner_client_id is None
        ):
            raise PermissionError("customer API credential required")
        if uow is None:
            async with self._uows() as owned:
                route = await self.confirm(
                    actor,
                    route_id,
                    expected_revision,
                    owned,
                )
                await owned.commit()
                return route
        now = self._now()
        result = await _sql_uow(uow).execute(
            update(partner_manager_routes)
            .where(
                partner_manager_routes.c.id == route_id,
                partner_manager_routes.c.partner_client_id
                == actor.partner_client_id,
                partner_manager_routes.c.status
                == PartnerRouteStatus.PENDING_CONFIRMATION,
                partner_manager_routes.c.revision == expected_revision,
                exists(
                    select(manager_memberships.c.id).where(
                        manager_memberships.c.manager_account_id
                        == partner_manager_routes.c.manager_account_id,
                        manager_memberships.c.status == "verified",
                        manager_memberships.c.revision
                        == partner_manager_routes.c.membership_revision,
                    ),
                ),
            )
            .values(
                status=PartnerRouteStatus.ACTIVE,
                revision=expected_revision + 1,
                confirmed_by_client_id=actor.partner_client_id,
                updated_at=now,
            ),
        )
        if result.rowcount != 1:
            raise ValueError("route confirmation revision conflict")
        return await self._get(_sql_uow(uow), route_id)

    async def revoke(
        self,
        scope: Scope,
        route_id: str,
        expected_revision: int,
        uow: UnitOfWork | None = None,
    ) -> PartnerManagerRoute:
        if uow is None:
            async with self._uows() as owned:
                route = await self.revoke(
                    scope,
                    route_id,
                    expected_revision,
                    owned,
                )
                await owned.commit()
                return route
        now = self._now()
        result = await _sql_uow(uow).execute(
            update(partner_manager_routes)
            .where(
                partner_manager_routes.c.id == route_id,
                partner_manager_routes.c.tenant_id == scope.tenant_id,
                partner_manager_routes.c.domain_id == scope.domain_id,
                partner_manager_routes.c.area_id == scope.area_id,
                partner_manager_routes.c.manager_account_id
                == scope.manager_account_id,
                partner_manager_routes.c.revision == expected_revision,
                partner_manager_routes.c.status.in_(
                    (
                        PartnerRouteStatus.PENDING_CONFIRMATION,
                        PartnerRouteStatus.ACTIVE,
                    ),
                ),
            )
            .values(
                status=PartnerRouteStatus.REVOKED,
                revision=expected_revision + 1,
                updated_at=now,
            ),
        )
        if result.rowcount != 1:
            raise ValueError("route revoke revision conflict")
        return await self._get(_sql_uow(uow), route_id)

    @staticmethod
    async def _get(uow: object, route_id: str) -> PartnerManagerRoute:
        row = (
            await uow.execute(
                select(partner_manager_routes).where(
                    partner_manager_routes.c.id == route_id,
                ),
            )
        ).mappings().one()
        return PartnerRouteGrantService._model(row)

    @staticmethod
    def _model(row: object) -> PartnerManagerRoute:
        return PartnerManagerRoute(
            route_id=row["id"],
            scope=Scope(
                tenant_id=row["tenant_id"],
                domain_id=row["domain_id"],
                area_id=row["area_id"],
                manager_account_id=row["manager_account_id"],
            ),
            partner_client_id=row["partner_client_id"],
            external_management_ref=row["external_management_ref"],
            status=row["status"],
            revision=row["revision"],
            allowed_operations=tuple(
                PartnerOperation(item) for item in row["allowed_operations"]
            ),
            granted_by=row["granted_by"],
            confirmed_by_client_id=row["confirmed_by_client_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("clock must return timezone-aware datetime")
        return now


__all__ = ["PartnerRouteGrantService"]
