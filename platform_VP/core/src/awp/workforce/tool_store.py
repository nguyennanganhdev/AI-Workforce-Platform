"""The tool store of a route (M1): what a partner's MCP server offers, kept as rows of `wf_tools`.

`discover` reads the server's `tools/list` now and brings the rows in line with it. What it finds is never trusted
further than it can be checked:

  read-only hint   becomes a look-up, active at once: it changes nothing, so an agent may have it.
  everything else  becomes an action that asks the resident's consent and is only `proposed`: no agent gets it until a
                   person activates it and says how its result is followed (PATCH of the tool: `tracking`, the
                   reference argument).
  a look-up that   is an action from then on, proposed again: the hint was the only reason it ran unasked.
  lost its hint    (Not one a person called a look-up with a recorded reason: that never rested on the hint.)
  no longer there  `gone` (the row and its settings stay; if it comes back an action must be activated again).

Each row keeps the tool as the server described it (`schema`: input schema, description, hint, all cleaned), so an
agent still gets the tool when the server cannot be listed, for example after a restart with the partner down.

The partner's list is read outside any transaction (it can take seconds). The rows are then written under the
route's lock (adminkit.lock), and only when the server row is still the one that was read before the list: a server
switched off, changed or removed meanwhile is left as the person who did that left it (StoreChanged).
"""
from __future__ import annotations

import fnmatch
import logging
import re
from typing import Any

from sqlalchemy import insert, select, update

from ..profiles.compile import LEADER_TOOLS, WORKER_TOOLS, WRAP_UP_TOOLS
from . import tables as t
from .adminkit import lock
from .common import now
from .partner_mcp import PartnerListError, ToolSpec
from .partner_tools import oversized, remote_ref, snapshot

log = logging.getLogger("awp.workforce")

MAX_TOOLS = 200  # rows a route's store may hold: a server that lists thousands does not fill the table
NAME = re.compile(r"^[A-Za-z0-9_-]{1,64}$")  # what a model may be shown as a function name (schemas.Name)

# AgentScope's own tools (the framework, its channels and its memory and knowledge middleware add them to an agent):
# a partner tool must not shadow one. A tool the platform adds in process is not known here; the tool factory keeps
# it when a partner tool comes with the same name (middleware/__init__.py).
FRAMEWORK_TOOLS = {n.lower() for n in (
    "AskUser", "Bash", "Credential", "Edit", "GenerateStructuredOutput", "Glob", "Grep", "PowerShell", "Read",
    "ScheduleCreate", "ScheduleDelete", "ScheduleList", "ScheduleView", "SendFile", "SendImage", "SendMessage",
    "Skill", "SubmitHandover", "SubmitVerdict", "TaskCreate", "TaskGet", "TaskList", "TaskUpdate", "ToolStop",
    "Write", "reset_tools", "WebSearch", "WebFetch", "ToolSearch", "search_knowledge", "add_memory", "search_memory",
    "memory_search", "ListChatMembers", "ListChats", "ListConversations", "ListUsers", "ListWikiNodes",
    "ListWikiSpaces", "ReadWikiDocument")}


def reserved(name: str) -> bool:
    """Names an agent is granted by default (`Case*`, `Team*`, ...) or that belong to the platform or the framework."""
    patterns = {*LEADER_TOOLS, *WORKER_TOOLS, *WRAP_UP_TOOLS, "Agent*", "Team*", "Case*"}
    return name.lower() in FRAMEWORK_TOOLS or any(fnmatch.fnmatchcase(name, p) for p in patterns)


class DiscoveryFailed(Exception):
    """The server's tool list could not be read. The message is the platform's own, safe to store and show."""


class StoreChanged(Exception):
    """The server row changed, or went, while its list was being read: nothing was written."""


def refusal(spec: ToolSpec) -> str | None:
    """Why a tool the server offers gets no row."""
    if not NAME.fullmatch(spec.name):
        return "its name is not a plain function name of at most 64 characters"
    if reserved(spec.name):
        return "its name belongs to the platform's own tools"
    if remote_ref(spec.input_schema):
        return "its schema refers to something outside itself"
    if oversized(spec):
        return "its schema is too large"
    return None


def _same(old: Any, new: dict) -> bool:
    return isinstance(old, dict) and all(old.get(k) == new[k] for k in new)


def _safe(read_only: bool) -> dict:
    """The defaults a tool gets from its hint alone."""
    if read_only:
        return dict(kind="lookup", read_only=True, requires_consent=False, consent_waiver=None, status="active")
    return dict(kind="action", read_only=False, requires_consent=True, consent_waiver=None, status="proposed")


async def discover(ctx: Any, route_id: str, server: Any, enable: bool = False) -> dict:
    """Read the server's tool list and update the route's rows; with `enable` the server is switched on too.
    A list that cannot be read changes no tool: the reason is kept on the server row and DiscoveryFailed raised."""
    name = server["name"]
    try:  # strict: the list as it is now or the failure, never the cached one; agents keep the cached one meanwhile
        specs = await ctx.mcp.client(route_id, server).list_tools(refresh=True, strict=True)
    except PartnerListError as e:
        async with ctx.db.engine.begin() as conn:
            await conn.execute(update(t.mcp_servers).where(
                t.mcp_servers.c.route_id == route_id, t.mcp_servers.c.name == name).values(last_error=str(e)[:300]))
        raise DiscoveryFailed(str(e)) from e
    offered = {s.name: s for s in specs if not oversized(s)}  # a schema too large to hand a model is not an offer
    stamp = now()
    report: dict[str, list] = {"added": [], "changed": [], "gone": [], "rejected": []}
    mine = (t.tools.c.route_id == route_id)
    this = (t.mcp_servers.c.route_id == route_id, t.mcp_servers.c.name == name)
    async with ctx.db.engine.begin() as conn:
        await lock(conn, t.routes, route_id)
        status = (await conn.execute(select(t.routes.c.status).where(t.routes.c.id == route_id))).scalar()
        current = (await conn.execute(select(t.mcp_servers).where(*this))).mappings().first()
        if status in (None, "replaced") or current is None or dict(current) != dict(server):
            raise StoreChanged()
        rows = (await conn.execute(select(t.tools).where(mine).order_by(t.tools.c.name))).mappings().all()
        for r in (r for r in rows if r["server"] == name):
            spec = offered.get(r["mcp_tool"])
            if spec is None:
                if r["status"] != "gone":
                    await conn.execute(update(t.tools).where(mine, t.tools.c.name == r["name"]).values(status="gone"))
                    report["gone"].append(r["name"])
                continue
            snap, values = snapshot(spec), {"discovered_at": stamp}
            if not _same(r["schema"], snap):
                values["schema"] = {**snap, "changed_at": stamp if r["schema"] else None}
                if r["schema"]:
                    report["changed"].append(r["name"])
            if r["source"] == "discovered" and r["kind"] == "lookup" and not spec.read_only and not r["consent_waiver"]:
                values.update(_safe(False), tracking="none")  # it ran unasked on the server's word, and the word is gone
                if r["name"] not in report["changed"]:
                    report["changed"].append(r["name"])
            elif r["status"] == "gone":  # back: a look-up as it was, an action only after a person looked again
                values["status"] = "active" if r["kind"] == "lookup" else "proposed"
            await conn.execute(update(t.tools).where(mine, t.tools.c.name == r["name"]).values(**values))
        taken, count = {r["name"] for r in rows}, len(rows)
        for spec in specs:
            if spec.name in taken and not oversized(spec):
                if not any(r["name"] == spec.name and r["server"] == name and r["mcp_tool"] == spec.name for r in rows):
                    report["rejected"].append({"mcp_tool": spec.name[:120], "reason": "a tool of this route already has that name"})
                continue
            why = refusal(spec) or ("the route's tool store is full" if count >= MAX_TOOLS else None)
            if why:
                report["rejected"].append({"mcp_tool": spec.name[:120], "reason": why})
                continue
            await conn.execute(insert(t.tools).values(
                route_id=route_id, name=spec.name, server=name, mcp_tool=spec.name, tracking="none", call_timeout=8.0,
                source="discovered", schema={**snapshot(spec), "changed_at": None}, discovered_at=stamp,
                **_safe(spec.read_only)))
            taken.add(spec.name)
            count += 1
            report["added"].append(spec.name)
        done = dict(last_discovered_at=stamp, last_error=None, revision=t.mcp_servers.c.revision + 1,
                    **({"enabled": True} if enable else {}))
        await conn.execute(update(t.mcp_servers).where(*this).values(**done))
    if report["rejected"]:
        log.warning("route %s, server %s: %s tool(s) of the server were not taken", route_id, name, len(report["rejected"]))
    return report
