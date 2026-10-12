"""A tiny partner MCP server for the `demo` profile of deploy/compose.yml (made from tests/workforce/partnerkit.py).

Generic on purpose: 'ticket' and 'repair' are only fixture names. Streamable HTTP at /mcp, three tools:
- lookup_ticket   read only (readOnlyHint): the tool store activates it at once
- book_repair     has a side effect, answers `pending`; idempotent by `client_reference` like a real partner must be
- repair_status   read only: what became of a request, by its reference

Every call is counted, so a check can prove how many times the partner was really called:
    python fake_mcp.py --stats      (run inside the container; prints JSON read from GET /stats)
    python fake_mcp.py --hold on    (tests and the failover smoke only; `off` lets the held calls go)

For tests only (the kill tests of core/tests/workforce/mpkit.py): POST /control {"hold": true} makes `book_repair` wait
after it took the request in (the side effect is done, the answer is not sent) until {"hold": false}; /stats says how
many calls are held and how many were answered. A test kills a platform process while its tool call hangs there.

Run: python fake_mcp.py   (listens on 0.0.0.0:8901; expects `Authorization: Bearer $DEMO_MCP_TOKEN` when that is set)
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import urllib.request

PORT = int(os.environ.get("DEMO_MCP_PORT", "8901"))
TOKEN = os.environ.get("DEMO_MCP_TOKEN", "")


def stats() -> int:
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/stats", timeout=5) as r:
        print(r.read().decode())
    return 0


def hold(word: str) -> int:
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/control", data=json.dumps({"hold": word == "on"}).encode(),
                                 method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as r:
        print(r.read().decode())
    return 0


def main() -> None:
    import uvicorn
    from mcp.server.fastmcp import FastMCP
    from mcp.types import ToolAnnotations
    from starlette.responses import JSONResponse

    calls: list[dict] = []  # every tools/call
    jobs: dict[str, str] = {}  # client_reference -> job id (the partner's own idempotency)
    effects: list[str] = []  # one entry per real side effect
    hold: dict = {"on": False, "open": None, "held": 0, "answered": 0}

    mcp = FastMCP("demo-partner", host="0.0.0.0", port=PORT, stateless_http=True, log_level="WARNING")
    # The server is reached by its compose service name: the SDK's DNS-rebinding guard only knows localhost.
    security = getattr(mcp.settings, "transport_security", None)
    if security is not None:
        security.enable_dns_rebinding_protection = False

    def rec(tool: str, args: dict) -> None:
        calls.append({"tool": tool, "args": args, "at": time.time()})

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def lookup_ticket(ticket_id: str) -> str:
        """Look up a ticket. Read only."""
        rec("lookup_ticket", {"ticket_id": ticket_id})
        return f"{ticket_id}: leaking pipe, status waiting for a technician"

    @mcp.tool()
    async def book_repair(slot: str, client_reference: str, note: str = "") -> str:
        """Ask for a repair visit. The partner confirms later, through its provider events."""
        rec("book_repair", {"slot": slot, "client_reference": client_reference, "note": note})
        if client_reference not in jobs:
            jobs[client_reference] = f"JOB-{len(jobs) + 1}"
            effects.append(client_reference)
        if hold["on"]:  # the request is in, the answer waits
            hold["held"] += 1
            try:
                await hold["open"].wait()
            finally:
                hold["held"] -= 1
        hold["answered"] += 1
        return json.dumps({"status": "pending", "operation_id": jobs[client_reference], "client_reference": client_reference})

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def repair_status(client_reference: str) -> str:
        """What became of a request, by its client_reference."""
        rec("repair_status", {"client_reference": client_reference})
        if client_reference not in jobs:
            return json.dumps({"status": "unknown_reference"})
        return json.dumps({"status": "pending", "operation_id": jobs[client_reference]})

    inner = mcp.streamable_http_app()

    async def app(scope, receive, send):
        if scope["type"] == "http" and scope["path"] in ("/health", "/stats"):
            by_tool: dict[str, int] = {}
            for c in calls:
                by_tool[c["tool"]] = by_tool.get(c["tool"], 0) + 1
            by_ref: dict[str, int] = {}  # how often book_repair was called with each reference
            for c in calls:
                if c["tool"] == "book_repair":
                    ref = c["args"]["client_reference"]
                    by_ref[ref] = by_ref.get(ref, 0) + 1
            body = {"status": "ok"} if scope["path"] == "/health" else {
                "calls": by_tool, "side_effects": len(effects), "jobs": jobs, "book_repair_calls_by_reference": by_ref,
                "side_effects_by_reference": {ref: effects.count(ref) for ref in jobs},
                "held": hold["held"], "answered": hold["answered"]}
            return await JSONResponse(body)(scope, receive, send)
        if scope["type"] == "http" and scope["path"] == "/control":  # tests only
            raw, more = b"", True
            while more:
                msg = await receive()
                raw, more = raw + msg.get("body", b""), msg.get("more_body", False)
            want = bool(json.loads(raw or b"{}").get("hold"))
            if hold["open"] is not None and not want:
                hold["open"].set()
            hold.update(on=want, open=asyncio.Event() if want else None)
            return await JSONResponse({"hold": want})(scope, receive, send)
        if scope["type"] == "http" and TOKEN:
            auth = dict(scope["headers"]).get(b"authorization", b"").decode()
            if auth != f"Bearer {TOKEN}":
                return await JSONResponse({"error": "unauthorized"}, status_code=401)(scope, receive, send)
        return await inner(scope, receive, send)

    uvicorn.run(app, host=os.environ.get("DEMO_HOST", "0.0.0.0"), port=PORT, log_level="warning")


if __name__ == "__main__":
    if "--stats" in sys.argv:
        sys.exit(stats())
    if "--hold" in sys.argv:
        sys.exit(hold(sys.argv[sys.argv.index("--hold") + 1]))
    main()
