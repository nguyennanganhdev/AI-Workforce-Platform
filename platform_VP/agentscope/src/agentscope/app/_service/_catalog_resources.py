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
        records = [record for _, record in await catalog_records(authority, user_id, kind, permission)]
    except PlatformError as exc:
        raise HTTPException(exc.status, exc.code) from exc
    if kind in {"mcp", "skill"}:
        # Personal resources sit beside granted catalog records, scoped to their owner.
        granted = {record.id for record in records}
        records += [record for record in await getattr(storage, f"list_{kind}s")(user_id)
                    if record.id not in granted and record.user_id == user_id
                    and (kind != "skill" or (record.enabled and record.review_status == "approved"))]
    return records


async def resolve_catalog_resource(storage, user_id: str, kind: Kind, ident: str, *, permission="bind", environment="production"):
    authority = catalog_authority(storage)
    if authority is None:
        return await getattr(storage, f"get_{kind}")(user_id, ident)
    from ..vin_platform._contracts import PlatformError

    if kind in {"mcp", "skill"} and environment == "production":
        own = await getattr(storage, f"get_{kind}")(user_id, ident)
        if own is not None and own.user_id == user_id:
            if kind == "mcp" and permission != "view":
                await assert_customer_mcp(storage, user_id, own.client, check_host=False)
            if kind == "skill" and permission != "view" and (not own.enabled or own.review_status != "approved"):
                raise HTTPException(409, "RESOURCE_REVOKED")
            return own
    try:
        context = await authority.context(user_id, environment=environment)
        _, record = await authority.resolve_catalog(context, kind, ident, permission=permission)
        return record
    except PlatformError as exc:
        raise HTTPException(exc.status, exc.code) from exc


async def require_catalog_management(storage, user_id: str, *, private_kind: Kind | None = None):
    authority = catalog_authority(storage)
    if authority is None:
        return
    from ..vin_platform._contracts import PlatformError

    try:
        view = await authority.capabilities(await authority.context(user_id))
    except PlatformError as exc:
        raise HTTPException(exc.status, exc.code) from exc
    capabilities = view["capabilities"]
    if capabilities.get("catalog.manage") is not True and not (
        private_kind and capabilities.get(f"{private_kind}s.private.manage") is True
    ):
        raise HTTPException(403, "CATALOG_READ_ONLY")


async def is_operator(storage, user_id: str) -> bool:
    """Only platform operators (catalog managers) may run code on the server.

    Without the Vin authority there are no self-registered accounts, so the
    single-tenant deployment keeps its full local toolset.
    """
    authority = catalog_authority(storage)
    if authority is None:
        return True
    from ..vin_platform._contracts import PlatformError

    try:
        view = await authority.capabilities(await authority.context(user_id))
    except PlatformError:
        return False
    return view["capabilities"].get("catalog.manage") is True


def _remote_url(client) -> str | None:
    config = client.mcp_config
    return config.url if getattr(config, "type", None) == "http_mcp" else None


async def assert_customer_mcp(storage, user_id: str, client, *, check_host: bool = True) -> None:
    """A customer's MCP is a remote HTTP server on a public host.

    A stdio MCP spawns its command inside the platform, and a private URL
    is a request from inside the platform network. The host is checked when
    the MCP is written; runtime only re-checks the transport (no DNS).
    """
    if await is_operator(storage, user_id):
        return
    url = _remote_url(client)
    if url is None:
        raise HTTPException(403, "STDIO_MCP_NOT_ALLOWED")
    if not check_host:
        return
    from ..vin_platform._contracts import PlatformError
    from ..vin_platform._egress import assert_public_endpoint

    try:
        await assert_public_endpoint(url)
    except PlatformError as exc:
        raise HTTPException(exc.status, exc.code) from exc

