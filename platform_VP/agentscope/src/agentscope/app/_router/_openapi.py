# -*- coding: utf-8 -*-
"""Import a REST API from its OpenAPI spec, and serve it as an MCP.

``/mcp/openapi`` previews and imports a spec for the signed-in user. The
import is an ordinary :class:`MCPRecord` whose HTTP client points at
``/mcp-bridge/openapi/{user}/{mcp}`` on the app itself, so sync, Agent
Builder and agent runs treat it like any remote MCP.

The bridge speaks the minimum of MCP over streamable HTTP with JSON
responses: ``initialize``, ``ping``, ``tools/list`` and ``tools/call``.
It is reached with a per-import token, not a user session, because the
caller is the app's own MCP client.
"""
import hashlib
import hmac
import os
import secrets
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field, SecretStr

from .._service._openapi import (
    MAX_OPERATIONS,
    OpenAPIError,
    call_operation,
    ensure_public_url,
    fetch_spec,
    load_spec_text,
    parse_spec,
    tool_snapshot,
)
from ..deps import get_current_user_id, get_storage
from ..storage import MCPRecord, StorageBase
from ..storage._model._mcp import OpenAPIBridge
from ...mcp import HttpMCPConfig, MCPClient
from ._mcp import refresh_catalog
from ._schema import MCPView

TOKEN_HEADER = "X-AWP-Bridge-Token"

openapi_router = APIRouter(prefix="/mcp/openapi", tags=["mcp"])
bridge_router = APIRouter(prefix="/mcp-bridge", tags=["mcp-bridge"])


def _bridge_base() -> str:
    """Where the app's own MCP client reaches this process."""
    return os.getenv("MCP_BRIDGE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class OpenAPISource(BaseModel):
    """A spec, by URL or pasted."""

    spec_url: str | None = Field(default=None, max_length=2000)
    spec_text: str | None = Field(default=None, max_length=5_000_000)


class OpenAPIImportRequest(OpenAPISource):
    """What to import and how to authenticate to the API."""

    name: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    display_name: str | None = Field(default=None, max_length=120)
    base_url: str = Field(min_length=1, max_length=2000)
    operations: list[str] = Field(min_length=1, max_length=MAX_OPERATIONS)
    auth_type: Literal["none", "bearer", "header", "query"] = "none"
    auth_name: str = Field(default="", max_length=120)
    auth_value: SecretStr | None = None


async def _load(source: OpenAPISource) -> dict:
    if source.spec_text and source.spec_text.strip():
        spec = load_spec_text(source.spec_text)
        url = source.spec_url
    elif source.spec_url:
        url = source.spec_url.strip()
        spec = await fetch_spec(url)
    else:
        raise OpenAPIError("Hãy nhập link OpenAPI hoặc dán nội dung spec.")
    return parse_spec(spec, url)


@openapi_router.post("/preview")
async def preview_openapi(
    body: OpenAPISource,
    _user_id: str = Depends(get_current_user_id),
) -> dict:
    """List what an import would offer, without saving anything."""
    try:
        parsed = await _load(body)
    except OpenAPIError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "title": parsed["title"],
        "description": parsed["description"],
        "base_urls": parsed["base_urls"],
        "operations": [
            {
                "name": op.name,
                "method": op.method,
                "path": op.path,
                "description": op.description,
            }
            for op in parsed["operations"]
        ],
        "skipped": parsed["skipped"],
        "max_operations": MAX_OPERATIONS,
    }


@openapi_router.post("", status_code=status.HTTP_201_CREATED)
async def import_openapi(
    body: OpenAPIImportRequest,
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
) -> MCPView:
    """Save an import as an MCP and fetch its tools through the bridge.

    The spec is re-read here rather than trusting the preview, so the
    stored operations are the ones the spec actually declares.
    """
    try:
        parsed = await _load(body)
        await ensure_public_url(body.base_url)
    except OpenAPIError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    wanted = set(body.operations)
    operations = [op for op in parsed["operations"] if op.name in wanted]
    if not operations:
        raise HTTPException(status_code=422, detail="Chưa chọn endpoint nào có trong spec.")
    if body.auth_type in ("header", "query") and not body.auth_name.strip():
        raise HTTPException(status_code=422, detail="Hãy nhập tên header hoặc tham số chứa API key.")

    token = secrets.token_urlsafe(32)
    record = MCPRecord(
        user_id=user_id,
        # Replaced below once the id is known; the URL embeds it.
        client=MCPClient(
            name=body.name,
            is_stateful=False,
            mcp_config=HttpMCPConfig(url=_bridge_base()),
        ),
        display_name=body.display_name or parsed["title"] or body.name,
        description=parsed["description"] or parsed["title"],
        tags=["openapi"],
        url=body.spec_url,
        openapi=OpenAPIBridge(
            title=parsed["title"],
            spec_url=body.spec_url,
            base_url=body.base_url.rstrip("/"),
            operations=operations,
            auth_type=body.auth_type,
            auth_name=body.auth_name.strip(),
            auth_value=body.auth_value.get_secret_value() if body.auth_value else "",
            token_sha256=_hash(token),
        ),
        discovered_tools=[tool_snapshot(op) for op in operations],
    )
    record.client = MCPClient(
        name=body.name,
        is_stateful=False,
        mcp_config=HttpMCPConfig(
            url=f"{_bridge_base()}/mcp-bridge/openapi/{user_id}/{record.id}",
            headers={TOKEN_HEADER: token},
            timeout=60,
        ),
    )
    try:
        await storage.upsert_mcp(user_id, record)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    # Proves the round trip agents will use; the catalog above stays if
    # the bridge cannot be reached, and the reason is shown.
    await refresh_catalog(record, timeout=20)
    await storage.upsert_mcp(user_id, record)
    return MCPView.from_record(record)


# ── the bridge ───────────────────────────────────────────────────────


def _rpc_result(msg_id: Any, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _rpc_error(msg_id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


async def _answer(record: MCPRecord, message: dict) -> dict | None:
    """Answer one JSON-RPC message; ``None`` for a notification."""
    if "id" not in message:
        return None
    msg_id, method = message.get("id"), message.get("method")
    params = message.get("params") or {}
    bridge = record.openapi
    assert bridge is not None
    if method == "initialize":
        return _rpc_result(
            msg_id,
            {
                "protocolVersion": params.get("protocolVersion") or "2025-06-18",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": record.client.name, "version": "1.0"},
            },
        )
    if method == "ping":
        return _rpc_result(msg_id, {})
    if method == "tools/list":
        return _rpc_result(
            msg_id,
            {
                "tools": [
                    {
                        "name": op.name,
                        "description": op.description,
                        "inputSchema": op.input_schema,
                    }
                    for op in bridge.operations
                ],
            },
        )
    if method == "tools/call":
        operation = next(
            (op for op in bridge.operations if op.name == params.get("name")),
            None,
        )
        if operation is None:
            return _rpc_error(msg_id, -32602, f"Unknown tool {params.get('name')!r}")
        text, is_error = await call_operation(
            bridge,
            operation,
            params.get("arguments") or {},
        )
        return _rpc_result(
            msg_id,
            {"content": [{"type": "text", "text": text}], "isError": is_error},
        )
    return _rpc_error(msg_id, -32601, f"Method not found: {method}")


async def _bridge_record(
    request: Request,
    user_id: str,
    mcp_id: str,
    storage: StorageBase,
) -> MCPRecord:
    """The import this request may use; 404 for anything else, so the
    route does not tell which user or MCP ids exist."""
    token = request.headers.get(TOKEN_HEADER, "")
    record = await storage.get_mcp(user_id, mcp_id) if token else None
    if (
        record is None
        or record.openapi is None
        or not record.enabled
        or not hmac.compare_digest(_hash(token), record.openapi.token_sha256)
    ):
        raise HTTPException(status_code=404, detail="Not found")
    return record


@bridge_router.post("/openapi/{user_id}/{mcp_id}")
async def bridge_rpc(
    user_id: str,
    mcp_id: str,
    request: Request,
    storage: StorageBase = Depends(get_storage),
) -> Response:
    """Handle MCP JSON-RPC from the app's own client."""
    record = await _bridge_record(request, user_id, mcp_id, storage)
    try:
        payload = await request.json()
    except ValueError:
        return JSONResponse(_rpc_error(None, -32700, "Parse error"), status_code=400)
    messages = payload if isinstance(payload, list) else [payload]
    answers = [
        answer
        for message in messages
        if isinstance(message, dict)
        and (answer := await _answer(record, message)) is not None
    ]
    if not answers:
        return Response(status_code=202)
    return JSONResponse(answers if isinstance(payload, list) else answers[0])


@bridge_router.get("/openapi/{user_id}/{mcp_id}")
async def bridge_stream(
    user_id: str,
    mcp_id: str,
    request: Request,
    storage: StorageBase = Depends(get_storage),
) -> Response:
    """No server-initiated stream: every answer comes back on its POST."""
    await _bridge_record(request, user_id, mcp_id, storage)
    return Response(status_code=405, headers={"Allow": "POST"})
