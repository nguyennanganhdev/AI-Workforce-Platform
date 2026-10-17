# -*- coding: utf-8 -*-
"""Database-backed partner route resolution and immutable revalidation."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Callable

from sqlalchemy import column, select, table, text

from ..contracts import (
    ActorContext,
    ActorKind,
    CredentialPurpose,
    PartnerAudience,
    PartnerOperation,
    ResolvedPartnerRoute,
    Scope,
    UnitOfWork,
)
from ._database import SqlAlchemyUnitOfWork
from ._identity import _sql_uow
from ._tables import manager_memberships, partner_manager_routes


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


class SqlPartnerRoutingPort:
    """Resolve one external management reference to exactly one manager."""

    def __init__(
        self,
        uows: Callable[[], SqlAlchemyUnitOfWork],
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._uows = uows
        self._clock = clock

    async def resolve(
        self,
        partner_actor: ActorContext,
        routing_input: Mapping[str, object],
    ) -> ResolvedPartnerRoute:
        self._require_customer_actor(partner_actor)
        external_ref = routing_input.get("external_management_ref")
        if not isinstance(external_ref, str) or not external_ref:
            raise PermissionError("external management reference required")
        external_user_id = routing_input.get("external_user_id")
        if not isinstance(external_user_id, str) or not external_user_id:
            raise PermissionError("external user is required for routing")
        if (
            partner_actor.external_user_id is not None
            and partner_actor.external_user_id != external_user_id
        ):
            raise PermissionError("partner routing user mismatch")
        async with self._uows() as uow:
            rows = await self._active_rows(
                uow,
                partner_actor.partner_client_id,
                external_ref,
            )
            if len(rows) == 1:
                await self._verify_residence(
                    uow,
                    rows[0],
                    external_user_id,
                    routing_input.get("residence_id"),
                )
        if len(rows) != 1:
            raise PermissionError("partner route is missing or ambiguous")
        return self._projection(rows[0])

    async def revalidate(
        self,
        scope: Scope,
        route_id: str,
        expected_revision: int,
        actor: ActorContext,
        audience: PartnerAudience,
        operation: PartnerOperation,
        uow: UnitOfWork | None = None,
    ) -> ResolvedPartnerRoute:
        self._require_customer_actor(actor)
        if actor.partner_client_id != audience.partner_client_id:
            raise PermissionError("partner audience client mismatch")
        if (
            actor.external_user_id is not None
            and actor.external_user_id != audience.external_user_id
        ):
            raise PermissionError("partner audience user mismatch")
        if uow is None:
            async with self._uows() as owned:
                return await self.revalidate(
                    scope,
                    route_id,
                    expected_revision,
                    actor,
                    audience,
                    operation,
                    owned,
                )
        statement = (
            select(
                partner_manager_routes,
                manager_memberships.c.revision.label(
                    "active_membership_revision",
                ),
            )
            .join(
                manager_memberships,
                manager_memberships.c.manager_account_id
                == partner_manager_routes.c.manager_account_id,
            )
            .join(
                _auth_users,
                _auth_users.c.id
                == manager_memberships.c.manager_account_id,
            )
            .join(
                _business_domains,
                _business_domains.c.id
                == manager_memberships.c.domain_id,
            )
            .join(
                _areas,
                _areas.c.id == manager_memberships.c.area_id,
            )
            .where(
                partner_manager_routes.c.id == route_id,
                partner_manager_routes.c.revision == expected_revision,
                partner_manager_routes.c.partner_client_id
                == actor.partner_client_id,
                partner_manager_routes.c.status == "active",
                manager_memberships.c.status == "verified",
                _auth_users.c.tenant_id
                == partner_manager_routes.c.tenant_id,
                _auth_users.c.domain_id
                == partner_manager_routes.c.domain_id,
                _auth_users.c.area_id == partner_manager_routes.c.area_id,
                _auth_users.c.role == "AREA_MANAGER",
                _auth_users.c.status == "active",
                _business_domains.c.tenant_id
                == partner_manager_routes.c.tenant_id,
                _business_domains.c.status == "active",
                _areas.c.domain_id == partner_manager_routes.c.domain_id,
                _areas.c.status == "active",
            )
            .limit(2)
        )
        rows = (await _sql_uow(uow).execute(statement)).mappings().all()
        if len(rows) != 1:
            raise PermissionError("partner route is no longer active")
        row = rows[0]
        if any(row[key] != value for key, value in scope.model_dump().items()):
            raise PermissionError("partner route owner changed")
        if row["membership_revision"] != row["active_membership_revision"]:
            raise PermissionError("manager membership revision changed")
        allowed = {
            PartnerOperation(item) for item in row["allowed_operations"]
        }
        if operation not in allowed:
            raise PermissionError("partner operation is not granted")
        await self._verify_residence(
            _sql_uow(uow),
            row,
            audience.external_user_id,
            audience.residence_id,
        )
        return self._projection(row)

    @staticmethod
    def _require_customer_actor(actor: ActorContext) -> None:
        if (
            actor.kind != ActorKind.PARTNER
            or actor.credential_purpose != CredentialPurpose.CUSTOMER_API
            or actor.partner_client_id is None
        ):
            raise PermissionError("customer API credential required")

    @staticmethod
    async def _active_rows(
        uow: SqlAlchemyUnitOfWork,
        client_id: str,
        external_ref: str,
    ) -> list[Any]:
        statement = (
            select(
                partner_manager_routes,
                manager_memberships.c.revision.label(
                    "active_membership_revision",
                ),
            )
            .join(
                manager_memberships,
                manager_memberships.c.manager_account_id
                == partner_manager_routes.c.manager_account_id,
            )
            .join(
                _auth_users,
                _auth_users.c.id
                == manager_memberships.c.manager_account_id,
            )
            .join(
                _business_domains,
                _business_domains.c.id
                == manager_memberships.c.domain_id,
            )
            .join(
                _areas,
                _areas.c.id == manager_memberships.c.area_id,
            )
            .where(
                partner_manager_routes.c.partner_client_id == client_id,
                partner_manager_routes.c.external_management_ref
                == external_ref,
                partner_manager_routes.c.status == "active",
                manager_memberships.c.status == "verified",
                _auth_users.c.tenant_id
                == partner_manager_routes.c.tenant_id,
                _auth_users.c.domain_id
                == partner_manager_routes.c.domain_id,
                _auth_users.c.area_id == partner_manager_routes.c.area_id,
                _auth_users.c.role == "AREA_MANAGER",
                _auth_users.c.status == "active",
                _business_domains.c.tenant_id
                == partner_manager_routes.c.tenant_id,
                _business_domains.c.status == "active",
                _areas.c.domain_id == partner_manager_routes.c.domain_id,
                _areas.c.status == "active",
            )
            .limit(2)
        )
        return list((await uow.execute(statement)).mappings().all())

    @staticmethod
    async def _verify_residence(
        uow: Any,
        route: Mapping[str, Any],
        external_user_id: str,
        residence_id: object,
    ) -> None:
        if residence_id is None:
            return
        if not isinstance(residence_id, str) or not residence_id:
            raise PermissionError("invalid residence routing value")
        found = await uow.scalar(
            text(
                """
                SELECT COUNT(*)
                FROM partner_residences
                WHERE partner_client_id = :partner_client_id
                  AND external_user_id = :external_user_id
                  AND residence_id = :residence_id
                  AND domain_id = :domain_id
                  AND area_id = :area_id
                  AND status = 'active'
                """,
            ),
            {
                "partner_client_id": route["partner_client_id"],
                "external_user_id": external_user_id,
                "residence_id": residence_id,
                "domain_id": route["domain_id"],
                "area_id": route["area_id"],
            },
        )
        if found != 1:
            raise PermissionError("residence is not bound to partner route")

    def _projection(self, row: Mapping[str, Any]) -> ResolvedPartnerRoute:
        if row["membership_revision"] != row["active_membership_revision"]:
            raise PermissionError("manager membership revision changed")
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("clock must return timezone-aware datetime")
        return ResolvedPartnerRoute(
            scope=Scope(
                tenant_id=row["tenant_id"],
                domain_id=row["domain_id"],
                area_id=row["area_id"],
                manager_account_id=row["manager_account_id"],
            ),
            route_id=row["id"],
            route_revision=row["revision"],
            grant_operations=tuple(
                PartnerOperation(item) for item in row["allowed_operations"]
            ),
            membership_revision=row["membership_revision"],
            resolved_at=now,
        )


__all__ = ["SqlPartnerRoutingPort"]
