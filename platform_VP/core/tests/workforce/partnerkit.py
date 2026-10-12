"""A fake partner for the tool tests (slice T1): a real FastMCP server over streamable HTTP in a thread.

Generic on purpose ('repair' and 'hotel' are only the names of fixtures). Every call is recorded, so a test
proves how many times the partner was really called and what it received. The partner is idempotent by
`client_reference` (the same reference never makes a second job) and answers a status query by reference.

Per-test knobs are plain attributes: `delay` (seconds a tool takes after its side effect), `pending_word`,
`status_of` (what the status tool says for a reference), `refuse` (answer 503 to tools/call).
"""
from __future__ import annotations

import asyncio
import json
import socket
import threading
import time

import uvicorn
from mcp.server.fastmcp import Context, FastMCP
from mcp.types import CallToolResult, ToolAnnotations

SECRET = "tok-SECRET-1234567890abcdef"  # the header value the platform sends; it must never come back out


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class Partner:
    def __init__(self, port: int | None = None, token: str = SECRET) -> None:
        self.port, self.token = port or free_port(), token
        self.calls: list[dict] = []  # every tools/call: tool, args, auth
        self.rpc: list[str] = []  # every JSON-RPC method the client sent
        self.jobs: dict[str, str] = {}  # client_reference -> job id (the partner's own idempotency)
        self.status_of: dict[str, str] = {}  # client_reference -> what the status tool answers
        self.effects: list[str] = []  # one entry per real side effect
        self.delay = 0.0
        self.pending_word = "pending"
        self.redirect_to: str | None = None
        self.refuse = 0  # answer this HTTP status to tools/call (0: off)
        self.server: uvicorn.Server | None = None
        self.thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/mcp"

    def of(self, tool: str) -> list[dict]:
        return [c for c in self.calls if c["tool"] == tool]

    @property
    def lists(self) -> int:
        return self.rpc.count("tools/list")

    # ---- the tools ------------------------------------------------------------------------------------------------
    def _job(self, ref: str, what: str) -> str:
        if ref not in self.jobs:
            self.jobs[ref] = f"JOB-{len(self.jobs) + 1}"
            self.effects.append(what)
        return self.jobs[ref]

    def build(self) -> FastMCP:
        mcp = FastMCP("partner", host="127.0.0.1", port=self.port, stateless_http=True, log_level="WARNING")

        def rec(ctx: Context, tool: str, args: dict) -> None:
            req = ctx.request_context.request
            self.calls.append({"tool": tool, "args": args, "auth": req.headers.get("authorization") if req else None,
                               "at": time.time()})

        @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
        def lookup_ticket(ticket_id: str, ctx: Context) -> str:
            """Look up a ticket. Read only."""
            rec(ctx, "lookup_ticket", {"ticket_id": ticket_id})
            return f"{ticket_id}: leaking pipe, status waiting for plumber"

        @mcp.tool()
        def lookup_no_hint(ticket_id: str, ctx: Context) -> str:
            """A look-up that does not say it is read only."""
            rec(ctx, "lookup_no_hint", {"ticket_id": ticket_id})
            return f"{ticket_id}: ok"

        @mcp.tool()
        async def book_repair(slot: str, client_reference: str, ctx: Context, note: str = "") -> str:
            """Ask for a repair visit. The partner confirms later."""
            rec(ctx, "book_repair", {"slot": slot, "client_reference": client_reference, "note": note})
            job = self._job(client_reference, "repair")
            if self.delay:
                await asyncio.sleep(self.delay)
            return json.dumps({"status": self.pending_word, "operation_id": job, "client_reference": client_reference})

        @mcp.tool()
        def book_hotel(hotel: str, nights: int, client_reference: str, ctx: Context) -> str:
            """Book a hotel. Confirmed at once."""
            rec(ctx, "book_hotel", {"hotel": hotel, "nights": nights, "client_reference": client_reference})
            job = self._job(client_reference, "hotel")
            return json.dumps({"status": "confirmed", "booking_id": job})

        @mcp.tool()
        def book_hotel_keyed(hotel: str, nights: int, request_key: str, ctx: Context) -> str:
            """Like book_hotel, but the partner wants the key under another name (idempotency_arg)."""
            rec(ctx, "book_hotel_keyed", {"hotel": hotel, "nights": nights, "request_key": request_key})
            job = self._job(request_key, "hotel")
            return json.dumps({"status": "confirmed", "booking_id": job})

        @mcp.tool()
        async def slow_action(seconds: float, client_reference: str, ctx: Context) -> str:
            """Does its side effect, then takes `seconds` to answer."""
            rec(ctx, "slow_action", {"seconds": seconds, "client_reference": client_reference})
            self._job(client_reference, "slow")
            await asyncio.sleep(seconds)
            return json.dumps({"status": "confirmed"})

        @mcp.tool()
        def rejecting_action(client_reference: str, ctx: Context) -> str:
            """Refuses with a status word."""
            rec(ctx, "rejecting_action", {"client_reference": client_reference})
            return json.dumps({"status": "rejected", "reason": "no technician available"})

        @mcp.tool()
        def broken_action(client_reference: str, ctx: Context) -> str:
            """Raises, with detail that must not reach the agent."""
            req = ctx.request_context.request
            rec(ctx, "broken_action", {"client_reference": client_reference})
            raise ValueError(f"ledger locked at /srv/partner/db.py line 9 host 10.1.2.3 auth {req.headers.get('authorization')}")

        @mcp.tool()
        def structured_only(ref: str, client_reference: str, ctx: Context) -> CallToolResult:
            """Answers in structuredContent only."""
            rec(ctx, "structured_only", {"ref": ref, "client_reference": client_reference})
            return CallToolResult(content=[], structuredContent={"status": "confirmed", "booking_id": "B-9", "ref": ref})

        @mcp.tool()
        def no_status_action(thing: str, client_reference: str, ctx: Context) -> str:
            """Answers with no status word at all."""
            rec(ctx, "no_status_action", {"thing": thing, "client_reference": client_reference})
            self._job(client_reference, "nostatus")
            return json.dumps({"note": "received"})

        @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
        def repair_status(client_reference: str, ctx: Context) -> str:
            """What became of a request, by its client_reference."""
            rec(ctx, "repair_status", {"client_reference": client_reference})
            if client_reference not in self.jobs:
                return json.dumps({"status": "unknown_reference"})
            word = self.status_of.get(client_reference, self.pending_word)
            return json.dumps({"status": word, "operation_id": self.jobs[client_reference]})

        @mcp.tool()
        def huge(n: int, ctx: Context) -> str:
            """A very large answer."""
            rec(ctx, "huge", {"n": n})
            return "x" * n

        return mcp

    # ---- the server -------------------------------------------------------------------------------------------------
    def _wrapped(self, app):
        async def wrapped(scope, receive, send):
            if scope["type"] != "http" or scope["method"] != "POST":
                return await app(scope, receive, send)
            body, more = b"", True
            while more:
                msg = await receive()
                body += msg.get("body", b"")
                more = msg.get("more_body", False)
            methods = []
            try:
                data = json.loads(body)
                methods = [m["method"] for m in (data if isinstance(data, list) else [data]) if isinstance(m, dict) and "method" in m]
            except ValueError:
                pass
            self.rpc.extend(methods)
            if self.redirect_to:
                await send({"type": "http.response.start", "status": 307,
                            "headers": [(b"location", self.redirect_to.encode()), (b"content-length", b"0")]})
                return await send({"type": "http.response.body", "body": b""})
            if self.refuse and "tools/call" in methods:
                await send({"type": "http.response.start", "status": self.refuse,
                            "headers": [(b"content-type", b"application/json")]})
                return await send({"type": "http.response.body", "body": b'{"error":"unavailable"}'})
            sent = False

            async def replay():
                nonlocal sent
                if not sent:
                    sent = True
                    return {"type": "http.request", "body": body, "more_body": False}
                return await receive()

            await app(scope, replay, send)
        return wrapped

    def start(self) -> "Partner":
        app = self._wrapped(self.build().streamable_http_app())
        self.server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=self.port, log_level="error",
                                                    timeout_graceful_shutdown=1))
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()
        for _ in range(200):
            if self.server.started:
                return self
            time.sleep(0.05)
        raise RuntimeError("the fake partner did not start")

    def stop(self) -> None:
        if self.server is None:
            return
        self.server.should_exit = True
        self.thread.join(timeout=8)
        if self.thread.is_alive():
            self.server.force_exit = True
            self.thread.join(timeout=5)
        self.server = None

    def __enter__(self) -> "Partner":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()
