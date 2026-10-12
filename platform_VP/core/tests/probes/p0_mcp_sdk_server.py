"""A real partner MCP server (FastMCP, streamable HTTP) in a background thread.

Every call is recorded, so a test can prove how many times a tool ran on the server
and whether a slow call kept running after the client gave up.
"""
from __future__ import annotations

import asyncio
import json
import socket
import threading
import time

import uvicorn
from mcp.server.fastmcp import Context, FastMCP
from mcp.types import CallToolRequest, CallToolResult, ToolAnnotations
from pydantic import BaseModel


class Booking(BaseModel):
    status: str
    operation_id: str


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class PartnerServer:
    """Start/stop a FastMCP server on a fixed port; `calls` survives a restart."""

    def __init__(self, port: int | None = None, stateless: bool = True, json_response: bool = False) -> None:
        self.port = port or free_port()
        self.stateless = stateless
        self.json_response = json_response
        self.calls: list[dict] = []     # every tool call: tool, args, headers, t_start, t_end
        self.require_token: str | None = None            # reject (401) every POST without "Bearer <token>"
        self.http_fail: dict[str, int] = {}              # JSON-RPC method -> HTTP status to answer with, app not run
        self.rpc: list[dict] = []       # every JSON-RPC request the CLIENT sent: {"method", "auth"} (HTTP level)
        self.server: uvicorn.Server | None = None
        self.thread: threading.Thread | None = None

    @property
    def list_calls(self) -> list[dict]:
        """tools/list requests sent by clients. (The low-level server also runs its own list handler inside
        every tools/call to find the output schema; that is not a request and is not counted.)"""
        return [r for r in self.rpc if r["method"] == "tools/list"]

    def _counting(self, app):
        rpc = self.rpc

        async def wrapped(scope, receive, send):
            if scope["type"] != "http" or scope["method"] != "POST":
                return await app(scope, receive, send)
            headers = {k.decode().lower(): v.decode() for k, v in scope["headers"]}

            async def reject(status: int):
                await send({"type": "http.response.start", "status": status,
                            "headers": [(b"content-type", b"application/json")]})
                await send({"type": "http.response.body", "body": b'{"error":"rejected by the test server"}'})

            if self.require_token is not None and headers.get("authorization") != f"Bearer {self.require_token}":
                return await reject(401)
            body, more = b"", True
            while more:
                msg = await receive()
                body += msg.get("body", b"")
                more = msg.get("more_body", False)
            try:
                data = json.loads(body)
                for m in (data if isinstance(data, list) else [data]):
                    if isinstance(m, dict) and "method" in m:
                        rpc.append({"method": m["method"], "auth": headers.get("authorization")})
                        if m["method"] in self.http_fail:
                            return await reject(self.http_fail[m["method"]])
            except ValueError:
                pass
            sent = False

            async def replay():
                nonlocal sent
                if not sent:
                    sent = True
                    return {"type": "http.request", "body": body, "more_body": False}
                return await receive()

            await app(scope, replay, send)

        return wrapped

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/mcp"

    # -- the tools ---------------------------------------------------------------------------
    def build(self) -> FastMCP:
        mcp = FastMCP("partner", host="127.0.0.1", port=self.port, stateless_http=self.stateless,
                      json_response=self.json_response, log_level="WARNING")
        calls = self.calls

        def rec(ctx: Context, tool: str, args: dict) -> dict:
            req = ctx.request_context.request
            headers = dict(req.headers) if req is not None else {}
            row = {"tool": tool, "args": args, "auth": headers.get("authorization"),
                   "x_tenant": headers.get("x-tenant"), "t_start": time.time(), "t_end": None}
            calls.append(row)
            return row

        @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, title="Look up a ticket"))
        def lookup_ticket(ticket_id: str, ctx: Context) -> str:
            """Look up a ticket by id. Read only."""
            row = rec(ctx, "lookup_ticket", {"ticket_id": ticket_id})
            row["t_end"] = time.time()
            return f"{ticket_id}: leaking pipe, status waiting for plumber"

        @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
        def book_plumber(slot: str, client_reference: str, ctx: Context) -> str:
            """Book a plumber. Asynchronous: the partner confirms later."""
            row = rec(ctx, "book_plumber", {"slot": slot, "client_reference": client_reference})
            row["t_end"] = time.time()
            return json.dumps({"status": "pending", "operation_id": "op-7781",
                               "client_reference": client_reference, "eta": "2026-10-12"})

        @mcp.tool()
        def structured_only(ref: str, ctx: Context) -> CallToolResult:
            """Return structuredContent and no text content at all."""
            row = rec(ctx, "structured_only", {"ref": ref})
            row["t_end"] = time.time()
            return CallToolResult(content=[], structuredContent={"status": "confirmed", "operation_id": "op-9",
                                                                 "ref": ref})

        @mcp.tool()
        def structured_dict(ref: str, ctx: Context) -> dict:
            """A plain dict return: FastMCP gives both text content and structuredContent."""
            row = rec(ctx, "structured_dict", {"ref": ref})
            row["t_end"] = time.time()
            return {"status": "accepted", "operation_id": "op-10", "ref": ref}

        @mcp.tool()
        def typed_model(ref: str, ctx: Context) -> Booking:
            """A pydantic return: FastMCP gives text content AND structuredContent plus an outputSchema."""
            row = rec(ctx, "typed_model", {"ref": ref})
            row["t_end"] = time.time()
            return Booking(status="queued", operation_id="op-11")

        @mcp.tool()
        def typed_lying(ref: str, ctx: Context) -> Booking:
            """Declares an outputSchema, but the wire answer below does not fit it (a partner bug)."""
            row = rec(ctx, "typed_lying", {"ref": ref})
            row["t_end"] = time.time()
            return Booking(status="confirmed", operation_id="op-12")

        call_inner = mcp._mcp_server.request_handlers[CallToolRequest]

        async def lying_handler(req):
            res = await call_inner(req)
            if req.params.name == "typed_lying":
                res.root.structuredContent = {"wrong": True}
            return res

        mcp._mcp_server.request_handlers[CallToolRequest] = lying_handler

        @mcp.tool()
        async def sleepy(seconds: float, ctx: Context) -> str:
            """Do a side effect, then take `seconds` to answer."""
            row = rec(ctx, "sleepy", {"seconds": seconds})
            row["side_effect"] = True      # the effect happens before the answer
            try:
                await asyncio.sleep(seconds)
            except asyncio.CancelledError:
                row["cancelled"] = True
                raise
            row["t_end"] = time.time()
            return json.dumps({"status": "completed", "slept": seconds})

        @mcp.tool()
        def boom(ctx: Context) -> str:
            """Always fails."""
            row = rec(ctx, "boom", {})
            row["t_end"] = time.time()
            raise ValueError("partner exploded: ledger locked")

        @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False))
        def record_action(note: str, ctx: Context) -> str:
            """An action that must run at most once."""
            row = rec(ctx, "record_action", {"note": note})
            row["t_end"] = time.time()
            return json.dumps({"status": "confirmed", "n": sum(1 for c in calls if c["tool"] == "record_action")})

        return mcp

    # -- lifecycle ---------------------------------------------------------------------------
    def start(self) -> "PartnerServer":
        app = self._counting(self.build().streamable_http_app())
        self.server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=self.port, log_level="error",
                                                    timeout_graceful_shutdown=1))
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()
        for _ in range(200):
            if self.server.started:
                return self
            time.sleep(0.05)
        raise RuntimeError("partner server did not start")

    def stop(self) -> None:
        if self.server is None:
            return
        self.server.should_exit = True
        self.thread.join(timeout=8)
        if self.thread.is_alive():          # open streams can stall a graceful stop
            self.server.force_exit = True
            self.thread.join(timeout=5)
        self.server = None

    def restart(self) -> "PartnerServer":
        self.stop()
        return self.start()

    def __enter__(self) -> "PartnerServer":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()

    def of(self, tool: str) -> list[dict]:
        return [c for c in self.calls if c["tool"] == tool]
