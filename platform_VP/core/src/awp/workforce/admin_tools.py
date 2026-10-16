"""Admin: the MCP servers and tools of a route (spec 7.4, 8), and the route's tool store (M1).

Two ways in. The whole-set PUTs are the old one: an admin types every server and tool, and they work at once. The
store is the new one: add a server (off), `enable` it, and its tools are discovered with safe defaults
(tool_store.py); a tool is then activated or changed one at a time with PATCH.

URLs are checked for SSRF when written; header values are sealed (A7) and never returned, only their names.
A tool may not take a name the platform's own tools or an agent's default grants answer to. The tenant's admin and
the manager of the route may use these; another manager's route answers 404.

Every write here locks the route first (adminkit.lock) and reads what it depends on afterwards: two people changing
one store, or a person and a discovery, never write over what the other just did.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import IntegrityError

from . import provider_match, ssrf, tables as t
from .adminkit import first, get_route, lock, scope_of
from .common import iso
from .crypto import SecretKeyMissing
from .schemas import McpServerIn, McpServersIn, ToolIn, ToolPatch, ToolsIn
from .tool_store import FRAMEWORK_TOOLS, DiscoveryFailed, StoreChanged, discover, reserved  # noqa: F401  (reserved: also used from here)

CONFIG = tuple(ToolIn.model_fields)  # what an admin sets on a tool; the rest of a row is the store's own
UNVOUCHED = ("the server does not call this tool read-only: to make it a look-up give the reason "
             "(consent_waiver), or leave it an action")


def unvouched(tool: ToolIn, known: Any) -> bool:
    """A look-up runs unasked and leaves no trace in the ledger. A tool the store discovered and whose server does not
    call it read-only is one only on a person's word, and that word is recorded (`consent_waiver`), like the waiver of
    an action's consent (M5): changing `kind` is not a way around either."""
    snap = known["schema"] if known is not None and known["source"] == "discovered" else None
    return tool.kind == "lookup" and isinstance(snap, dict) and not snap.get("read_only") and not tool.consent_waiver


def tool_out(r: Any) -> dict:
    snap = r["schema"] or {}
    return {"name": r["name"], "server": r["server"], "mcp_tool": r["mcp_tool"], "kind": r["kind"],
            "read_only": r["read_only"], "requires_consent": r["requires_consent"], "consent_waiver": r["consent_waiver"],
            "tracking": r["tracking"],
            "client_reference_arg": r["client_reference_arg"], "idempotency_arg": r["idempotency_arg"],
            "status_tool": r["status_tool"], "integration_id": r["integration_id"],
            "consent_summary": r["consent_summary"],
            "call_timeout": r["call_timeout"], "description_override": r["description_override"],
            "source": r["source"], "status": r["status"], "discovered_at": iso(r["discovered_at"]),
            "schema": {k: snap.get(k) for k in ("description", "input_schema", "read_only")} if snap else None,
            "schema_changed_at": iso(snap.get("changed_at"))}


def build_admin_tools(r: APIRouter, ctx: Any) -> None:
    db, sealer, settings = ctx.db, ctx.sealer, ctx.settings

    def server_out(row: Any) -> dict:
        names: list[str] = []
        if row["headers_enc"]:
            try:
                names = sorted(json.loads(sealer.open(row["headers_enc"])))
            except (SecretKeyMissing, ValueError):
                pass
        return {"name": row["name"], "url": row["url"], "transport": row["transport"], "timeout": row["timeout"],
                "header_names": names,  # the values are never shown
                "enabled": bool(row["enabled"]), "last_discovered_at": iso(row["last_discovered_at"]),
                "last_error": row["last_error"]}

    async def editable(conn, who: Any, route_id: str, write: bool = False) -> Any:
        route = await get_route(conn, who, route_id)
        if write:  # the caller's own route, locked, and read again now that nobody else can change it
            await lock(conn, t.routes, route_id)
            route = await get_route(conn, who, route_id)
        if route["status"] == "replaced":
            raise HTTPException(409, "route was replaced")
        return route

    async def sealed_headers(who: Any, route_id: str, servers: list[McpServerIn]) -> dict[str, str | None]:
        """Check every URL and seal every header set, before anything is written."""
        async with db.engine.connect() as conn:
            await editable(conn, who, route_id)  # first: a route that is not the caller's learns nothing about our network
        checks = await asyncio.gather(*(ssrf.check_url(s.url, settings.mcp_allow_private) for s in servers),
                                      return_exceptions=True)
        sealed: dict[str, str | None] = {}
        for srv, checked in zip(servers, checks):
            if isinstance(checked, ssrf.Blocked):
                raise HTTPException(422, f"server {srv.name}: {checked}")
            if isinstance(checked, BaseException):
                raise checked
            try:
                sealed[srv.name] = sealer.seal(json.dumps(srv.headers, sort_keys=True)) if srv.headers else None
            except SecretKeyMissing:
                raise HTTPException(503, "AWP_SECRET_KEY is not set; server headers cannot be stored")
        return sealed

    async def server_of(conn, route_id: str, name: str) -> Any:
        return await first(conn, select(t.mcp_servers).where(
            t.mcp_servers.c.route_id == route_id, t.mcp_servers.c.name == name), "server")

    async def tools_of(conn, route_id: str, server: str | None = None) -> list:
        q = select(t.tools).where(t.tools.c.route_id == route_id)
        if server:
            q = q.where(t.tools.c.server == server)
        return (await conn.execute(q.order_by(t.tools.c.name))).mappings().all()

    # ---- servers -----------------------------------------------------------------------------------------------------
    @r.put("/routes/{route_id}/mcp")
    async def put_servers(route_id: str, body: McpServersIn, request: Request):
        """The whole set. A server declared here is on (its typed tools work at once, as before the store); one that
        was already there keeps what the store knows of it: whether it is on, and its last discovery."""
        who = scope_of(request)
        sealed = await sealed_headers(who, route_id, body.servers)
        async with db.engine.begin() as conn:
            await editable(conn, who, route_id, write=True)
            used = set((await conn.execute(select(t.tools.c.server).where(t.tools.c.route_id == route_id))).scalars())
            gone = sorted(used - {s.name for s in body.servers})
            if gone:
                raise HTTPException(409, f"tools of this route use servers that would be removed: {gone}")
            was = {x["name"]: x for x in (await conn.execute(select(t.mcp_servers).where(
                t.mcp_servers.c.route_id == route_id))).mappings()}
            await conn.execute(delete(t.mcp_servers).where(t.mcp_servers.c.route_id == route_id))
            kept = lambda s, k, d: was[s.name][k] if s.name in was else d  # noqa: E731
            rows = [dict(route_id=route_id, name=s.name, url=s.url, transport=s.transport,
                         headers_enc=sealed[s.name], timeout=s.timeout, enabled=kept(s, "enabled", True),
                         last_discovered_at=kept(s, "last_discovered_at", None), last_error=kept(s, "last_error", None),
                         revision=kept(s, "revision", -1) + 1)
                    for s in body.servers]
            if rows:
                await conn.execute(insert(t.mcp_servers), rows)
        ctx.mcp.forget(route_id)
        return {"servers": [server_out(x) for x in rows]}

    @r.post("/routes/{route_id}/mcp", status_code=201)
    async def add_server(route_id: str, body: McpServerIn, request: Request):
        """One more server for the tool store. It starts off: `enable` reads its tools and switches it on."""
        who = scope_of(request)
        sealed = await sealed_headers(who, route_id, [body])
        row = dict(route_id=route_id, name=body.name, url=body.url, transport=body.transport,
                   headers_enc=sealed[body.name], timeout=body.timeout, enabled=False, last_discovered_at=None, last_error=None)
        try:
            async with db.engine.begin() as conn:
                await editable(conn, who, route_id, write=True)
                await conn.execute(insert(t.mcp_servers).values(**row))
        except IntegrityError:
            raise HTTPException(409, f"the route already has a server named {body.name}")
        return server_out(row)

    @r.get("/routes/{route_id}/mcp")
    async def get_servers(route_id: str, request: Request):
        async with db.engine.connect() as conn:
            await get_route(conn, scope_of(request), route_id)
            rows = (await conn.execute(select(t.mcp_servers).where(t.mcp_servers.c.route_id == route_id)
                                       .order_by(t.mcp_servers.c.name))).mappings().all()
        return {"servers": [server_out(x) for x in rows]}

    async def discovered(request: Request, route_id: str, name: str, enable: bool) -> dict:
        who = scope_of(request)
        async with db.engine.connect() as conn:
            await editable(conn, who, route_id)
            server = await server_of(conn, route_id, name)
        try:
            report = await discover(ctx, route_id, server, enable=enable)
        except DiscoveryFailed as e:  # nothing changed but the reason, kept on the server row
            raise HTTPException(502, f"the server's tool list could not be read: {e}")
        except (IntegrityError, StoreChanged):  # switched off, changed or removed while the partner was answering
            raise HTTPException(409, "the server or the tool store changed meanwhile; nothing was written, try again")
        async with db.engine.connect() as conn:
            return {"server": server_out(await server_of(conn, route_id, name)),
                    "tools": [tool_out(x) for x in await tools_of(conn, route_id, name)], **report}

    @r.post("/routes/{route_id}/mcp/{name}/enable")
    async def enable_server(route_id: str, name: str, request: Request):
        """Read the server's tool list, keep a row per tool (tool_store.py), and switch the server on. A list that
        cannot be read leaves the server as it was (502)."""
        return await discovered(request, route_id, name, enable=True)

    @r.post("/routes/{route_id}/mcp/{name}/refresh")
    async def refresh_server(route_id: str, name: str, request: Request):
        """Compare the store with the server again: new tools, tools that went, schemas that changed."""
        return await discovered(request, route_id, name, enable=False)

    @r.post("/routes/{route_id}/mcp/{name}/disable")
    async def disable_server(route_id: str, name: str, request: Request):
        """Its tools are gone for every agent from the next run on; the rows and their settings stay."""
        who = scope_of(request)
        async with db.engine.begin() as conn:
            await editable(conn, who, route_id, write=True)
            await server_of(conn, route_id, name)
            await conn.execute(update(t.mcp_servers).where(
                t.mcp_servers.c.route_id == route_id, t.mcp_servers.c.name == name).values(
                enabled=False, revision=t.mcp_servers.c.revision + 1))
            return {"server": server_out(await server_of(conn, route_id, name))}

    # ---- tools -------------------------------------------------------------------------------------------------------
    async def check_bindings(conn, route: Any, tools: list[ToolIn]) -> None:
        have = set((await conn.execute(select(t.mcp_servers.c.name).where(t.mcp_servers.c.route_id == route["id"]))).scalars())
        unknown = sorted({x.server for x in tools} - have)
        if unknown:
            raise HTTPException(422, f"unknown servers (put them under /mcp first): {unknown}")
        wanted = {x.integration_id for x in tools if x.integration_id}
        ours = set((await conn.execute(select(t.integrations.c.id).where(
            t.integrations.c.id.in_(wanted), t.integrations.c.client_id == route["client_id"]))).scalars()) if wanted else set()
        if wanted - ours:  # another client's integration answers like a missing one
            raise HTTPException(422, f"unknown integrations of this client: {sorted(wanted - ours)}")
        loose = sorted(x.name for x in tools if x.tracking == "events" and not x.integration_id)
        if loose and not await provider_match.sole(conn, route["client_id"]):
            # with two providers, a tool that names none could be followed by either of them
            raise HTTPException(422, f"this client has more than one integration: bind these tools to one "
                                     f"(integration_id): {loose}")

    @r.put("/routes/{route_id}/tools")
    async def put_tools(route_id: str, body: ToolsIn, request: Request):
        """The whole set, each tool active. A tool that stays (same name, server and partner tool) keeps what the
        store knows of it: where it came from and its stored schema."""
        who = scope_of(request)
        clash = sorted(x.name for x in body.tools if reserved(x.name))
        if clash:
            raise HTTPException(422, f"these names belong to the platform's own tools: {clash}")
        async with db.engine.begin() as conn:
            route = await editable(conn, who, route_id, write=True)
            await check_bindings(conn, route, body.tools)
            was = {x["name"]: x for x in await tools_of(conn, route_id)}
            found = {(x["server"], x["mcp_tool"]): x for x in was.values() if x["source"] == "discovered"}
            loose = sorted(x.name for x in body.tools if unvouched(x, found.get((x.server, x.mcp_tool))))
            if loose:  # also under another name: retyping a discovered tool does not change what its server says of it
                raise HTTPException(422, f"{UNVOUCHED}: {loose}")
            await conn.execute(delete(t.tools).where(t.tools.c.route_id == route_id))
            rows = []
            for x in body.tools:
                old = was.get(x.name)
                same = old is not None and (old["server"], old["mcp_tool"]) == (x.server, x.mcp_tool)
                rows.append({**x.model_dump(), "route_id": route_id, "source": old["source"] if same else "manual",
                             "status": "gone" if same and old["status"] == "gone" else "active",
                             "schema": old["schema"] if same else None, "discovered_at": old["discovered_at"] if same else None})
            if rows:
                await conn.execute(insert(t.tools), rows)
        return {"tools": [tool_out(x) for x in rows]}

    @r.patch("/routes/{route_id}/tools/{name}")
    async def patch_tool(route_id: str, name: str, body: ToolPatch, request: Request):
        """Change one tool, or activate it. What is sent is laid over the row and the result must be a valid tool;
        only what was sent is written, on the row as it is now (read under the route's lock).
        Activating a proposed action needs `tracking` said out loud: nobody has yet told the platform how the result
        of that action is followed, and guessing `none` would call a pending request finished business."""
        who = scope_of(request)
        sent = body.model_dump(exclude_unset=True)
        status = sent.pop("status", None)
        async with db.engine.begin() as conn:
            route = await editable(conn, who, route_id, write=True)
            row = await first(conn, select(t.tools).where(t.tools.c.route_id == route_id, t.tools.c.name == name), "tool")
            if "consent_waiver" not in sent and (sent.get("requires_consent") or sent.get("kind", row["kind"]) != row["kind"]):
                sent["consent_waiver"] = None  # asking again ends the waiver; a reason given for one kind is none for the other
            merged = {**{k: row[k] for k in CONFIG}, **sent}
            try:
                tool = ToolIn.model_validate(merged)
            except ValidationError as e:
                raise HTTPException(422, "; ".join(str(x["msg"]) for x in e.errors()[:3]))
            if status and row["status"] == "gone":
                raise HTTPException(409, "the server no longer offers this tool; refresh the server first")
            if status == "active" and row["status"] == "proposed" and tool.kind == "action" and "tracking" not in sent:
                raise HTTPException(422, "to activate an action say how its result is followed: tracking "
                                         "(none, events or status_query)")
            if unvouched(tool, row):
                raise HTTPException(422, UNVOUCHED)
            await check_bindings(conn, route, [tool])
            values = {**{k: getattr(tool, k) for k in sent}, **({"status": status} if status else {})}
            if values:
                await conn.execute(update(t.tools).where(t.tools.c.route_id == route_id, t.tools.c.name == name).values(**values))
        return tool_out({**dict(row), **values})

    @r.get("/routes/{route_id}/tools")
    async def get_tools(route_id: str, request: Request, server: str | None = None, status: str | None = None):
        async with db.engine.connect() as conn:
            await get_route(conn, scope_of(request), route_id)
            rows = await tools_of(conn, route_id, server)
        return {"tools": [tool_out(x) for x in rows if not status or x["status"] == status]}
