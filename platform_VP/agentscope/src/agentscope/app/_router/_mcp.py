# -*- coding: utf-8 -*-
"""MCP router — the user's own library of installed MCPs.

This is the user-level collection an install lands in, distinct from
``/workspace/mcp``, which manages the MCPs of one session's workspace.
Installing from a hub only writes here; putting an MCP into a workspace
stays a separate, explicit act.
"""
import asyncio
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError

from ..._utils._common import _describe_exception
from ...mcp import HttpMCPConfig, MCPClient
from .._service import MCPRenderError, render_mcp
from ..deps import get_current_user_id, get_mcp_hubs, get_storage
from ..hub import MCPHubBase
from ..storage import MCPRecord, StorageBase
from ._schema import DirectInstallMCPRequest, MCPView, UpdateMCPRequest

mcp_router = APIRouter(prefix="/mcp", tags=["mcp"])


async def _discover_tools(client: MCPClient, timeout: float) -> list[dict]:
    """Return a bounded, JSON-safe MCP catalog snapshot."""
    try:
        async with asyncio.timeout(timeout):
            raw_tools = await client.list_raw_tools()
    finally:
        if client.is_stateful and client.is_connected:
            await client.close()
    return [
        {
            "name": tool.name,
            "description": tool.description or "",
            "input_schema": tool.inputSchema or {},
            # The server's own read-only hint; tools without it are treated
            # as writes (never executed by Agent Studio tests).
            "read_only": bool(
                getattr(getattr(tool, "annotations", None), "readOnlyHint", False),
            ),
        }
        for tool in raw_tools
    ]


@mcp_router.post("", status_code=status.HTTP_201_CREATED)
async def install_direct_mcp(
    body: DirectInstallMCPRequest,
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
) -> MCPView:
    """Connect, discover and register a partner HTTP MCP."""
    headers = dict(body.headers)
    if body.api_key:
        value = body.api_key.get_secret_value()
        if body.auth_scheme.strip():
            value = f"{body.auth_scheme.strip()} {value}"
        headers[body.auth_header] = value
    client = MCPClient(
        name=body.name,
        is_stateful=False,
        mcp_config=HttpMCPConfig(
            url=str(body.url),
            headers=headers or None,
            timeout=body.timeout,
        ),
    )
    from .._service._catalog_resources import assert_customer_mcp
    await assert_customer_mcp(storage, user_id, client)
    try:
        tools = await _discover_tools(client, body.timeout)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Không thể kết nối hoặc đọc danh sách tool từ MCP: "
                f"{_describe_exception(exc)}"
            ),
        ) from exc
    if not tools:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="MCP kết nối được nhưng không công bố tool nào.",
        )
    record = MCPRecord(
        user_id=user_id,
        client=client,
        values={"auth_header": body.auth_header},
        display_name=body.display_name or body.name,
        description=body.description,
        url=str(body.url),
        tags=["partner", "direct"],
        discovered_tools=tools,
        catalog_revision=1,
        last_synced_at=datetime.now(UTC),
    )
    try:
        await storage.upsert_mcp(user_id, record)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return MCPView.from_record(record)


@mcp_router.get("")
async def list_mcps(
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
) -> list[MCPView]:
    """Return every MCP the user has installed, ordered by name."""
    authority = getattr(storage, "vin_platform_service", None)
    if authority is not None and (await authority.context(user_id)).role == "VIN_USER":
        from ..vin_platform._resources import catalog_records
        granted = [MCPView.from_record(record).model_copy(update={"editable": False,
            "url": None, "last_sync_error": None}) for _, record in await catalog_records(authority, user_id, "mcp")]
        # The user's own MCPs are editable; granted pack/domain MCPs are view/use only.
        ids = {view.id for view in granted}
        own = [MCPView.from_record(record) for record in await storage.list_mcps(user_id) if record.id not in ids]
        return granted + sorted(own, key=lambda view: view.name)
    records = await storage.list_mcps(user_id)
    return sorted(
        (MCPView.from_record(r) for r in records),
        key=lambda view: view.name,
    )


@mcp_router.post("/{mcp_id}/sync")
async def sync_mcp_tools(
    mcp_id: str,
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
) -> MCPView:
    """Refresh the registered tool catalog for one installed MCP."""
    record = await storage.get_mcp(user_id, mcp_id)
    if record is None:
        raise HTTPException(status_code=404, detail="MCP not found")
    if not record.enabled:
        raise HTTPException(status_code=409, detail="MCP is disabled")
    try:
        record.discovered_tools = await _discover_tools(
            MCPClient.model_validate(record.client.model_dump(mode="json")),
            float(record.client.mcp_config.timeout or 30.0),
        )
        record.catalog_revision += 1
        record.last_synced_at = datetime.now(UTC)
        record.last_sync_error = None
    except Exception as exc:
        record.last_sync_error = _describe_exception(exc)
        await storage.upsert_mcp(user_id, record)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Không thể đồng bộ MCP: {record.last_sync_error}",
        ) from exc
    await storage.upsert_mcp(user_id, record)
    return MCPView.from_record(record)


@mcp_router.patch("/{mcp_id}")
async def update_mcp(
    mcp_id: str,
    body: UpdateMCPRequest,
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
    hubs: dict[str, MCPHubBase] = Depends(get_mcp_hubs),
) -> MCPView:
    """Rename, enable/disable, or re-key an installed MCP.

    Changing a secret is a re-render, not a field edit: an API key can
    sit anywhere in the config — inside a URL, a header, an env var — so
    the card's template plus the merged answers is the only thing that
    knows where to put it.

    Raises:
        `HTTPException`: 404 if the MCP is not in the caller's library,
            400 if the MCP has no card to re-render from, 409 if the new
            name is taken, or 422 if the name is not made of
            ``[a-zA-Z0-9_-]``.
    """
    record = await storage.get_mcp(user_id, mcp_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No installed MCP with id {mcp_id!r}.",
        )

    if body.values is not None:
        hub = hubs.get(record.hub_id or "")
        if hub is None or record.card_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "This MCP has no card to re-render from — its hub is "
                    "not registered, or it was added by hand."
                ),
            )
        try:
            card = await hub.get_mcp(user_id, record.card_id)
        except KeyError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    f"Hub {record.hub_id!r} no longer has the card this "
                    f"MCP was installed from."
                ),
            ) from e

        # Merged, not replaced: the client sends only what changed, and
        # a write-only field the form did not echo back must survive.
        merged = {**record.values, **body.values}
        try:
            record.client = render_mcp(
                card,
                merged,
                body.name or record.client.name,
            )
        except MCPRenderError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            ) from e
        from .._service._catalog_resources import assert_customer_mcp
        await assert_customer_mcp(storage, user_id, record.client)
        record.values = merged
        record.version = card.version
    elif body.name is not None:
        # ``MCPClient`` checks its name in ``model_post_init``, which a
        # plain attribute assignment skips; rebuild the client through
        # ``model_validate`` so an illegal name is refused here. Stored
        # as-is it would fail the same check on the next read, turning
        # every route that loads the library into a 500.
        try:
            record.client = MCPClient.model_validate(
                {**record.client.model_dump(), "name": body.name},
            )
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(exc),
            ) from exc

    if body.enabled is not None:
        record.enabled = body.enabled

    try:
        await storage.upsert_mcp(user_id, record)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e

    return MCPView.from_record(record)


@mcp_router.delete("/{mcp_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mcp(
    mcp_id: str,
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
) -> None:
    """Remove an MCP from the user's library.

    Workspaces that already hold this MCP keep it — the workspace
    relation is derived by name, not a foreign key, and tearing down a
    live stateful MCP session as a side effect of a library edit would
    surprise the user.
    """
    if not await storage.delete_mcp(user_id, mcp_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No installed MCP with id {mcp_id!r}.",
        )
