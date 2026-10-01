"""Inspect database demo fixtures. Business routes use the regular V3 routers."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .v3_auth import resident_connection

router = APIRouter(tags=["V3 database demo"])
Scope = Annotated[tuple[AsyncConnection, str], Depends(resident_connection)]


@router.get("/demo/fixtures")
async def fixtures(request: Request, scope: Scope) -> dict[str, object]:
    if not request.app.state.settings.demo_mode:
        raise HTTPException(404, "Database demo is not enabled")
    db, actor = scope
    result: dict[str, object] = {"mode": "faker-database", "actorId": actor,
        "actors": ["resident", "management", "technical", "security", "admin"]}
    queries = {
        "domains": "select id,code,name from domains",
        "sites": "select id,code,name from sites",
        "buildings": "select id,code,name from buildings",
        "categories": "select id,code,name from service_categories",
        "managementUnits": "select id,code,name from management_units",
        "myUnits": "select u.id,u.code,u.building_id from units u join unit_residents ur on ur.unit_id=u.id and ur.tenant_id=u.tenant_id where ur.user_id=:actor",
        "staff": "select sp.id,sp.user_id,sp.employee_code,sp.management_unit_id,u.name from staff_profiles sp join users u on u.id=sp.user_id",
        "reviewers": "select distinct u.id,u.name from users u join tenant_memberships m on m.user_id=u.id join scoped_user_roles r on r.membership_id=m.id and r.tenant_id=m.tenant_id where m.status='active' and r.role_code='management' and r.valid_from<=now() and (r.valid_to is null or r.valid_to>now())",
        "roomAgents": "select ca.channel_id,a.id,a.name from channel_agents ca join agents a on a.id=ca.agent_id and a.tenant_id=ca.tenant_id join channel_memberships m on m.channel_id=ca.channel_id and m.tenant_id=ca.tenant_id where m.user_id=:actor",
        "scopes": "select id,kind,building_id from access_scopes",
    }
    for key, sql in queries.items():
        rows = await db.execute(text(sql), {"actor": actor})
        result[key] = [dict(row) for row in rows.mappings()]
    return result
