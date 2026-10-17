"""C02 consumer for MCP/skill records; authority stays with VinPlatformService."""
from typing import Literal

from fastapi import HTTPException

Kind = Literal["mcp", "skill"]


def catalog_authority(storage):
    from ..vin_platform import enabled

    if not enabled():
        return None
    authority = getattr(storage, "vin_platform_service", None)
    if authority is None:
        raise HTTPException(503, "RESOURCE_AUTHORITY_UNAVAILABLE")
    return authority


async def list_catalog_resources(storage, user_id: str, kind: Kind, *, permission="bind"):
    authority = catalog_authority(storage)
    if authority is None:
        return await getattr(storage, f"list_{kind}s")(user_id)
    from ..vin_platform._contracts import PlatformError
    from ..vin_platform._resources import catalog_records

    try:
        return [record for _, record in await catalog_records(authority, user_id, kind, permission)]
    except PlatformError as exc:
        raise HTTPException(exc.status, exc.code) from exc


async def resolve_catalog_resource(storage, user_id: str, kind: Kind, ident: str, *, permission="bind", environment="production"):
    authority = catalog_authority(storage)
    if authority is None:
        return await getattr(storage, f"get_{kind}")(user_id, ident)
    from ..vin_platform._contracts import PlatformError

    try:
        context = await authority.context(user_id, environment=environment)
        _, record = await authority.resolve_catalog(context, kind, ident, permission=permission)
        return record
    except PlatformError as exc:
        raise HTTPException(exc.status, exc.code) from exc


async def require_catalog_management(storage, user_id: str):
    authority = catalog_authority(storage)
    if authority is None:
        return
    from ..vin_platform._contracts import PlatformError

    try:
        view = await authority.capabilities(await authority.context(user_id))
    except PlatformError as exc:
        raise HTTPException(exc.status, exc.code) from exc
    if view["capabilities"].get("catalog.manage") is not True:
        raise HTTPException(403, "CATALOG_READ_ONLY")
