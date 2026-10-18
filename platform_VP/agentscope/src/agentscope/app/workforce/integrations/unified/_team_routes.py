"""Owner-scoped, evaluated business-team binding for partner routes."""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, update

from ....deps import get_current_principal, get_storage
from ...foundation._tables import partner_manager_routes
from ._readiness import bindable_members, route_readiness, team_hash
from ._tables import routes


class BindTeamRequest(BaseModel):
    agent_ids: list[str] = Field(min_length=1, max_length=12)
    coordinator_agent_id: str = Field(min_length=1)
    expected_team_hash: str = Field(min_length=64, max_length=64)


def team_routes_router(foundation: Any) -> APIRouter:
    router = APIRouter(prefix="/manager/partner-routes", tags=["workforce-team-readiness"])

    async def owned(route_id, principal):
        try:
            scope = await foundation.identity.resolve_manager(principal)
        except PermissionError as exc:
            raise HTTPException(403, "Verified area manager required") from exc
        async with foundation.uows() as uow:
            row = (await uow.execute(select(routes).where(
                routes.c.route_id == route_id, routes.c.tenant_id == scope.tenant_id,
                routes.c.manager_account_id == scope.manager_account_id,
            ))).mappings().first()
            grant = (await uow.execute(select(partner_manager_routes).where(
                partner_manager_routes.c.id == route_id,
                partner_manager_routes.c.tenant_id == scope.tenant_id,
                partner_manager_routes.c.domain_id == scope.domain_id,
                partner_manager_routes.c.area_id == scope.area_id,
                partner_manager_routes.c.manager_account_id == scope.manager_account_id,
            ))).mappings().first()
        if row is None or grant is None:
            raise HTTPException(404, "Route not found")
        return dict(row), dict(grant)

    @router.get("/{route_id}/readiness")
    async def readiness(route_id: str, principal=Depends(get_current_principal), storage=Depends(get_storage)):
        route, grant = await owned(route_id, principal)
        return await route_readiness(storage, route, status=grant["status"])

    @router.put("/{route_id}/team")
    async def bind_team(route_id: str, body: BindTeamRequest,
                        principal=Depends(get_current_principal), storage=Depends(get_storage)):
        route, grant = await owned(route_id, principal)
        if grant["status"] != "active":
            raise HTTPException(409, "ROUTE_NOT_ACTIVE")
        if team_hash(route) != body.expected_team_hash:
            raise HTTPException(409, "TEAM_REVISION_CONFLICT")
        try:
            members = await bindable_members(storage, route, body.agent_ids, body.coordinator_agent_id)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        config = {**(route.get("config") or {}), "member_agents": members}
        candidate = {**route, "config": config}
        result = await route_readiness(storage, candidate)
        if not result["ready"]:
            raise HTTPException(409, {"code": "TEAM_NOT_READY", "issues": result["issues"]})
        async with foundation.uows() as uow:
            changed = await uow.execute(update(routes).where(
                routes.c.route_id == route_id, routes.c.manager_account_id == route["manager_account_id"],
                routes.c.updated_at == route["updated_at"],
            ).values(config=config, updated_at=datetime.now(UTC)))
            if changed.rowcount != 1:
                raise HTTPException(409, "TEAM_REVISION_CONFLICT")
            await uow.commit()
        return result

    return router
