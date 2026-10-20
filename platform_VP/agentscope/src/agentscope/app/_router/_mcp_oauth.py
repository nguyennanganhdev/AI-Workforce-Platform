# -*- coding: utf-8 -*-
"""Sign a user in to a remote MCP with OAuth.

``POST /mcp/{mcp_id}/oauth/start`` (signed-in user) discovers the MCP's
authorization server if needed, registers this platform as a client, and
returns the URL to open. The provider then sends the browser to
``GET /mcp-oauth/callback``, which has no session of its own: the
one-time ``state`` from the start call says whose sign-in it is. The
callback stores the tokens, fetches the MCP's tools and sends the browser
back to the MCP page.
"""
import os
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse

from .._service import _mcp_oauth as oauth_flow
from ..deps import get_current_user_id, get_storage
from ..storage import StorageBase
from ...mcp import HttpMCPConfig
from ._mcp import refresh_catalog

oauth_start_router = APIRouter(prefix="/mcp", tags=["mcp"])
oauth_callback_router = APIRouter(prefix="/mcp-oauth", tags=["mcp"])


def _web_origin() -> str:
    """The browser origin of the web app."""
    explicit = os.getenv("PUBLIC_ORIGIN", "").strip()
    if explicit:
        return explicit.rstrip("/")
    origins = [o.strip() for o in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()]
    return (origins[0] if origins else "http://localhost:5173").rstrip("/")


def redirect_uri() -> str:
    """Where providers send the browser back: the API as the web sees it."""
    api = os.getenv("PUBLIC_API_URL", "").strip() or f"{_web_origin()}/api"
    return f"{api.rstrip('/')}/mcp-oauth/callback"


def _back(**params: str) -> RedirectResponse:
    return RedirectResponse(f"{_web_origin()}/mcp?{urlencode(params)}", status_code=302)


@oauth_start_router.post("/{mcp_id}/oauth/start")
async def start_oauth(
    mcp_id: str,
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
) -> dict:
    """Return the provider's sign-in URL for this MCP."""
    record = await storage.get_mcp(user_id, mcp_id)
    if record is None:
        raise HTTPException(status_code=404, detail="MCP not found")
    config = record.client.mcp_config
    if not isinstance(config, HttpMCPConfig) or record.openapi is not None:
        raise HTTPException(status_code=422, detail="Chỉ MCP kết nối từ xa mới đăng nhập OAuth được.")
    try:
        if record.oauth is None:
            record.oauth = await oauth_flow.discover(config.url)
        if record.oauth is None:
            raise oauth_flow.OAuthError(
                "MCP này không công bố đăng nhập OAuth. Hãy dùng API key nếu có.",
            )
        uri = redirect_uri()
        if not record.oauth.client_id or record.oauth.redirect_uri != uri:
            await oauth_flow.register(record.oauth, uri)
    except oauth_flow.OAuthError as exc:
        await storage.upsert_mcp(user_id, record)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await storage.upsert_mcp(user_id, record)
    return {"authorize_url": oauth_flow.begin(record.oauth, user_id, record.id)}


@oauth_callback_router.get("/callback")
async def oauth_callback(
    state: str = Query(default=""),
    code: str = Query(default=""),
    error: str = Query(default=""),
    error_description: str = Query(default=""),
    storage: StorageBase = Depends(get_storage),
) -> RedirectResponse:
    """Finish a sign-in started by :func:`start_oauth`."""
    pending = oauth_flow.take_pending(state) if state else None
    if pending is None:
        return _back(oauth="error", message="Phiên đăng nhập đã hết hạn. Hãy bấm Đăng nhập lại.")
    record = await storage.get_mcp(pending["user_id"], pending["mcp_id"])
    if record is None or record.oauth is None:
        return _back(oauth="error", message="Không tìm thấy MCP cần đăng nhập.")
    if error or not code:
        return _back(
            oauth="error",
            mcp=record.client.name,
            message=error_description or error or "Nhà cung cấp không trả về mã đăng nhập.",
        )
    try:
        await oauth_flow.complete(record.oauth, code, pending["verifier"])
    except oauth_flow.OAuthError as exc:
        return _back(oauth="error", mcp=record.client.name, message=str(exc))
    record.client = oauth_flow.with_token(record.client, record.oauth)
    await refresh_catalog(record, timeout=20)
    await storage.upsert_mcp(pending["user_id"], record)
    if record.last_sync_error:
        return _back(oauth="error", mcp=record.client.name, message=record.last_sync_error)
    return _back(oauth="ok", mcp=record.client.name, tools=str(len(record.discovered_tools)))
