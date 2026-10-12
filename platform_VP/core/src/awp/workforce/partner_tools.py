"""PartnerTool: one `wf_tools` row of a route as a tool of an AgentScope agent (spec 8, P0 items 15-24).

Every agent of the route (leader and specialists) gets the route's tools through the same factory as the other
tools; the profile's allow-list then decides which of them each agent may use, and a tool that needs the
resident's consent is stopped by the approval gate before it is called.

  lookup   synchronous, read only. A successful answer becomes evidence like any tool result.
  action   written to the operation ledger first (ledger.py), then called once with the client_reference put
           into the partner's argument. The answer is stored by the tool itself, also when it timed out:
           an interrupted turn does not cancel a tool and nobody reads its return value (P0).

Getting the request out runs under one deadline (`call_timeout`, at most 9 s, plus a short grace): the
10-second clock of AgentScope's tool offload starts when the tool starts, so a slow ledger write would
otherwise push a call past it. `allow_offload = False` and the agent class of offload.py are the second line.
Writing the answer down is not under that deadline: an answer already in hand is never dropped for a slow
database (ledger.record). What the partner's text says is data: it reaches a model cleaned, and only the
platform's own `<platform-verified>` line (jobs.verified) tells the claims guard that work is done.
"""
from __future__ import annotations

import asyncio
import copy
import fnmatch
import json
import logging
from typing import Any

import jsonschema
from agentscope.message import TextBlock, ToolResultState
from agentscope.permission import PermissionBehavior, PermissionDecision
from agentscope.tool import ToolBase, ToolChunk
from jsonschema_specifications import REGISTRY as SPECIFICATIONS
from referencing import Registry
from referencing.exceptions import NoSuchResource
from sqlalchemy import select, update

from . import ledger, tables as t
from .common import opaque_id
from .jobs import clean, verified
from .ledger import NONCE
from .partner_hub import McpHub
from .partner_mcp import PartnerListError, ToolSpec
from .partner_result import DONE_WORDS, FAILED, JOB_ID, MAX_TEXT, OK, PENDING, UNKNOWN, PartnerResult

log = logging.getLogger("awp.workforce")

MAX_CALL_TIMEOUT = 9.0  # below the 10 s after which AgentScope would move a running tool to the background
BODY_GRACE = 0.7
RECORD_FLOOR = 0.25  # an answer in hand gets at least this long to be written down, whatever is left of the deadline
MAX_DESCRIPTION = 1000  # of a tool and of each property: the partner's words reach every model call
MAX_SCHEMA = 32 * 1024  # of one tool's input schema, as JSON: it too is sent with every model call of every agent
NONCE_SCHEMA = {"type": "string", "minLength": 1, "maxLength": 64,
                "description": "Leave this out. Only to deliberately repeat a request that was already carried out "
                               "with exactly the same arguments: give any value you have not used before."}


def _no_fetch(uri: str):
    raise NoSuchResource(ref=uri)


# The partner's schema never makes the platform fetch anything: a reference that is not in the schema fails.
NO_FETCH = SPECIFICATIONS.combine(Registry(retrieve=_no_fetch))
REFS = ("$ref", "$dynamicRef", "$recursiveRef")


def remote_ref(node: Any) -> bool:
    """The schema points outside itself."""
    if isinstance(node, dict):
        return any((k in REFS and isinstance(v, str) and not v.startswith("#")) or remote_ref(v) for k, v in node.items())
    return isinstance(node, list) and any(remote_ref(x) for x in node)


def oversized(spec: ToolSpec) -> bool:
    try:
        return len(json.dumps(spec.input_schema)) > MAX_SCHEMA
    except (TypeError, ValueError):
        return True


def defuse(node: Any) -> Any:
    """The partner's schema as a model may read it: platform tags defused, descriptions and titles capped."""
    if isinstance(node, dict):
        return {k: clean(v, MAX_DESCRIPTION) if k in ("description", "title") and isinstance(v, str) else defuse(v)
                for k, v in node.items()}
    if isinstance(node, list):
        return [defuse(x) for x in node]
    return clean(node, 2000) if isinstance(node, str) else node


def snapshot(spec: ToolSpec) -> dict:
    """A tool as its server described it, in the form the store keeps (`wf_tools.schema`): already cleaned."""
    return {"description": clean(spec.description or "", MAX_DESCRIPTION),
            "input_schema": defuse(spec.input_schema) if isinstance(spec.input_schema, dict) else {},
            "read_only": bool(spec.read_only)}


def stored_spec(row: Any) -> ToolSpec | None:
    """The tool from the snapshot on its row; None for a row that never had one (typed by hand, never discovered)."""
    snap = row["schema"]
    if not isinstance(snap, dict):
        return None
    return ToolSpec(name=row["mcp_tool"], description=str(snap.get("description") or ""),
                    input_schema=snap.get("input_schema") or {}, read_only=bool(snap.get("read_only")))


def hidden_args(cfg: Any) -> set[str]:
    return {a for a in (cfg["client_reference_arg"], cfg["idempotency_arg"]) if a}


def model_schema(spec: ToolSpec, cfg: Any) -> dict:
    """What the model sees: the partner's schema without the arguments the platform fills in, and for an
    action the optional nonce."""
    schema = defuse(copy.deepcopy(spec.input_schema)) if isinstance(spec.input_schema, dict) else {}
    schema.setdefault("type", "object")
    props = schema.setdefault("properties", {})
    hide = hidden_args(cfg)
    for name in hide:
        props.pop(name, None)
    schema["required"] = [r for r in schema.get("required") or [] if r not in hide]
    if cfg["kind"] == "action":
        props[NONCE] = NONCE_SCHEMA
    return schema


def chunk(text: str, ok: bool) -> ToolChunk:
    return ToolChunk(content=[TextBlock(text=text)], state=ToolResultState.SUCCESS if ok else ToolResultState.ERROR)


def kept_ref(op: Any, res: PartnerResult | None = None) -> str | None:
    """The partner's own job id as the platform keeps it: any id the partner chose (contract 6.2)."""
    ref = (op["external_job_id"] if op is not None else None) or (res.external_job_id if res is not None else None)
    return ref if opaque_id(ref) else None


def ref_of(op: Any, res: PartnerResult | None = None) -> str | None:
    """The reference a model may be shown: only an id made of plain characters (never the platform's internal code,
    never prose). An id with spaces or markup is kept and matched by the platform but not repeated to a model."""
    ref = kept_ref(op, res)
    return ref if ref and JOB_ID.fullmatch(ref) else None


def reference(op: Any, res: PartnerResult | None = None) -> str:
    ref = ref_of(op, res)
    if ref:
        return f"Reference: {ref}."
    return ("The partner has given a reference; the platform keeps it." if kept_ref(op, res)
            else "The partner has given no reference yet.")


def unfollowed(why: str | None) -> bool:
    """The partner accepted a request that nobody can follow (no events or status query, or nothing to match them by)."""
    return why in ("untracked", "uncorrelatable")


def render(res: PartnerResult, op: Any = None) -> tuple[str, bool]:
    """(the words the agent sees, whether the result may become evidence). They never claim more than was verified:
    only ok and pending are evidence; failed and unknown leave their trace in the ledger."""
    body = clean(res.text, MAX_TEXT)
    if res.outcome == OK:  # the partner's own word that it is done, in the one form the claims guard reads as proof
        return (verified(res.status) if res.status in DONE_WORDS else "") + body, True
    if res.outcome == PENDING:
        return (f"PENDING: the partner accepted the request but has not finished it. {reference(op, res)} "
                f"You will be told when it changes. Say only that it is pending; do not say it is done. "
                f"Partner said: {body}"), True
    if res.outcome == FAILED:
        return f"FAILED: {body}. Nothing was carried out. Tell the resident only that it failed.", False
    if unfollowed(res.error):
        return ("UNKNOWN: the partner accepted the request but says it is not finished, and nothing will tell us "
                "when it is. Do not retry it and do not tell the resident that it was done. Say only that it was "
                f"received and a person will follow it up. {reference(op, res)} ({body})"), False
    return ("UNKNOWN: the request may or may not have been carried out. Do not retry it and do not tell the "
            "resident that it was done or that it failed. A person or a later check will find out. "
            f"({body})"), False


def render_lookup(res: PartnerResult) -> tuple[str, bool]:
    body = clean(res.text, MAX_TEXT)
    if res.outcome == OK:  # a status field of the partner's own system (not a sentence someone typed) can be proof
        return (verified(res.status) if res.status in DONE_WORDS else "") + body, True
    if res.outcome == FAILED:
        return f"FAILED: the look-up did not work: {body}", False
    return (f"UNAVAILABLE: the partner did not answer in time ({body}). Nothing was changed; you may try once "
            "more, or tell the resident you could not check."), False


def existing(op: Any) -> tuple[str, bool]:
    """The answer for a call whose operation row already exists: the partner is not called again."""
    stored = op["result"] or {}
    text = clean(str(stored.get("text", "")), MAX_TEXT)
    ref = ref_of(op)
    of = f" (reference {ref})" if ref else ""
    status = op["status"]
    if status in ("intent", "sent"):
        return (f"IN PROGRESS: this same request is already being sent{of}. It was not sent again. "
                "Do not repeat it; its result will be recorded."), False
    if status == "pending":
        return (f"PENDING: this same request is already with the partner{of} and has not finished. "
                "It was not sent again. Say only that it is pending; do not say it is done. "
                f"Partner said: {text}"), True
    if status == "completed":
        mark = verified(stored.get("status")) if stored.get("status") in DONE_WORDS else ""
        return (f"ALREADY DONE: this same request was carried out earlier{of} and was not sent again. "
                f"{mark}{text} To make a new, separate request change an argument or give a new {NONCE}."), True
    if status == "failed":
        return (f"FAILED earlier: {text}. It was not sent again. To try again on purpose change an argument or "
                f"give a new {NONCE}."), False
    if unfollowed(stored.get("error")):
        return ("UNKNOWN: this same request was accepted by the partner and nothing will tell us when it is done"
                f"{of}. Do not retry it and do not tell the resident that it was done; a person will follow it up."), False
    return (f"UNKNOWN: this same request was sent before and nobody knows whether it was carried out{of}. "
            "Do not retry it and do not tell the resident that it was done or that it failed."), False


class _Run:
    """What the body of an action has done so far, for the code that must clean up after a timeout."""

    def __init__(self) -> None:
        self.op: Any = None
        self.mine = False  # this run marked the row sent, so it owns the live call
        self.sent = False
        self.res: PartnerResult | None = None  # the partner's answer, once it is in hand


class PartnerTool(ToolBase):
    is_concurrency_safe = False  # an agent's calls run one after another, as for AgentScope's own MCP tools
    allow_offload = False

    def __init__(self, rt: Any, wf: Any, cfg: Any, spec: ToolSpec, client: Any) -> None:
        super().__init__()
        self.rt, self.wf, self.cfg, self.spec, self.client = rt, wf, dict(cfg), spec, client
        self.name = cfg["name"]
        self.description = clean(cfg["description_override"] or spec.description or cfg["name"], MAX_DESCRIPTION)
        self.input_schema = model_schema(spec, cfg)
        self.is_read_only = cfg["kind"] == "lookup"
        self.total = min(float(cfg["call_timeout"] or 8.0), MAX_CALL_TIMEOUT)
        props = self.input_schema.get("properties") or {}
        self.declared = set(props) if props else None
        self.hide = hidden_args(cfg)
        self.validator = None
        try:
            jsonschema.Draft202012Validator.check_schema(self.input_schema)
            self.validator = jsonschema.Draft202012Validator(self.input_schema, registry=NO_FETCH)
        except Exception as e:  # a schema nobody can read is the partner's to judge
            log.warning("tool %s: its schema cannot be checked here (%s)", self.name, type(e).__name__)

    async def check_permissions(self, *args: Any, **kwargs: Any) -> PermissionDecision:
        """The profile's allow-list and the approval gate decide before this is asked; there is nobody to ask here."""
        return PermissionDecision(behavior=PermissionBehavior.ALLOW, message="partner tool of the route")

    def _arguments(self, given: dict) -> tuple[dict, str | None]:
        """The arguments the model may send (nothing it did not declare, nothing the platform fills in), and
        the first thing wrong with them against the partner's schema."""
        args = {k: v for k, v in given.items() if k not in self.hide and (self.declared is None or k in self.declared)}
        if self.validator is None:
            return args, None
        try:
            first = next(iter(self.validator.iter_errors(args)), None)
        except Exception as e:  # a reference that leads nowhere, a pattern that is not one: nothing is sent on a guess
            log.warning("tool %s: its schema failed on a call (%s)", self.name, type(e).__name__)
            return args, "the tool's schema could not be checked"
        if first is None:
            return args, None
        where = ".".join(str(p) for p in first.path)
        return args, f"{where + ': ' if where else ''}{first.message}"[:300]

    async def call(self, **given: Any) -> ToolChunk:
        args, wrong = self._arguments(given)
        if wrong:
            return chunk(f"Not sent, nothing was done: the arguments are wrong ({wrong}). Correct them and call again.", False)
        if self.cfg["kind"] == "lookup":
            return await self._lookup(args)
        return await self._action(args)

    async def _lookup(self, args: dict) -> ToolChunk:
        try:
            async with asyncio.timeout(self.total + BODY_GRACE):
                res = await self.client.call(self.cfg["mcp_tool"], args, kind="lookup", timeout=self.total, tracking="none")
        except TimeoutError:
            res = PartnerResult(UNKNOWN, "no answer in time", error="timeout")
        text, ok = render_lookup(res)
        return chunk(text, ok)

    async def _action(self, args: dict) -> ToolChunk:
        loop, run = asyncio.get_running_loop(), _Run()
        started = loop.time()
        why = ""
        try:
            try:
                async with asyncio.timeout(self.total + BODY_GRACE):
                    early = await self._send(args, run, started)
                if early is not None:
                    return early
            except TimeoutError:
                why = "no answer in time"
            except asyncio.CancelledError:
                if run.sent:  # the partner may have the request or even have answered: say so, in the background if need be
                    await ledger.record(self.rt.db, run.op["id"], run.res or PartnerResult(
                        UNKNOWN, "the call was interrupted", error="cancelled", sent=True), 1.0,
                        expect=None if run.res else ("intent", "sent"))
                raise
            except Exception:
                log.exception("partner tool %s failed", self.name)
                why = "the call failed unexpectedly"
            return await self._finish(run, started, why)
        finally:
            if run.mine:
                ledger.INFLIGHT.discard(run.op["id"])

    async def _send(self, args: dict, run: _Run, started: float) -> ToolChunk | None:
        """Write the intent, send the request, keep the answer. A chunk is returned when nothing was sent."""
        loop, db = asyncio.get_running_loop(), self.rt.db
        model_args = dict(args)
        begun = await ledger.begin(db, self.wf["id"], self.wf["route_id"], self.name, model_args)
        if begun.refused:
            return chunk(begun.refused, False)
        op = begun.op
        if not begun.fresh:
            return chunk(*existing(op))
        run.op = op
        if not await ledger.mark_sent(db, op["id"], getattr(self.rt, "node", None) or None):
            return chunk("IN PROGRESS: this request is being handled elsewhere. It was not sent again.", False)
        run.mine = run.sent = True
        ledger.INFLIGHT.add(op["id"])
        model_args.pop(NONCE, None)  # ours: the partner never sees it
        sent = {**model_args, **{a: op["client_reference"] for a in self.hide}}
        res = await self.client.call(self.cfg["mcp_tool"], sent, kind="action",
                                     timeout=max(self.total - (loop.time() - started), 0.5), tracking=self.cfg["tracking"])
        if res.outcome == PENDING and not res.external_job_id and not self.hide:
            # nothing in the answer and nothing we sent can match a later event to this request
            res = PartnerResult(UNKNOWN, res.text, status=res.status, error="uncorrelatable", sent=True)
        run.res = res
        return None

    async def _finish(self, run: _Run, started: float, why: str) -> ToolChunk:
        """Write down what became of the call and say it. The answer is the partner's if one is in hand; without one,
        a call that may have left is `unknown` (never `failed`), one that had not left is `failed` and may be repeated."""
        if run.op is None:
            return chunk("Not sent, nothing was done: the platform could not record the request. You may try once more.", False)
        res = run.res
        if res is None and not run.sent:
            await ledger.record(self.rt.db, run.op["id"], PartnerResult(FAILED, why, error="not_sent", sent=False),
                                RECORD_FLOOR, expect=("intent", "sent"))
            return chunk("Not sent, nothing was done: the platform could not get the request out in time. "
                         "You may try once more.", False)
        answered = res is not None
        res = res or PartnerResult(UNKNOWN, why, error="timeout", sent=True)
        left = started + self.total + BODY_GRACE - asyncio.get_running_loop().time()
        row = await ledger.record(self.rt.db, run.op["id"], res, max(left, RECORD_FLOOR),
                                  expect=None if answered else ("intent", "sent"))
        return chunk(*render(res, row if row is not None else {**dict(run.op), "external_job_id": res.external_job_id}))


async def keep_snapshots(rt: Any, found: list[tuple[Any, ToolSpec]]) -> None:
    """A tool typed by hand has no stored schema until its server was listed once. The first agent that gets it from
    the live list leaves the schema on the row, so the tool is still there when the partner is down later."""
    try:
        for r, spec in found:  # a row a transaction: nothing here can wait in a circle with a writer of the store
            async with rt.db.engine.begin() as conn:
                await conn.execute(update(t.tools).where(
                    t.tools.c.route_id == r["route_id"], t.tools.c.name == r["name"], t.tools.c.server == r["server"],
                    t.tools.c.mcp_tool == r["mcp_tool"]).values(schema={**snapshot(spec), "changed_at": None}))
    except Exception:  # the agent has its tools either way
        log.exception("could not store the schemas of the tools of route %s", found[0][0]["route_id"])


async def partner_tools(rt: Any, wf: Any, patterns: list[str]) -> list[PartnerTool]:
    """The route's tools this agent may have: the `active` rows of `wf_tools` whose server is enabled, each with its
    schema from the cached MCP list. When the server cannot be listed (the partner is down, perhaps since before this
    process started) the schema stored at the last discovery is used instead: the agent keeps the tool and a call
    fails in plain words, where dropping it would leave the agent not knowing the tool exists.
    A tool the partner no longer offers, a schema that points outside itself or is too large, a look-up that is not
    read only, or an unlistable server's tool with no stored schema is left out (and logged), never an error for the
    agent. Read only is the server's word; a person's word counts on a tool typed by hand, and on a discovered one
    only with the recorded reason."""
    hub: McpHub | None = getattr(rt, "mcp", None)
    if hub is None:
        return []
    async with rt.db.engine.connect() as conn:
        rows = (await conn.execute(select(t.tools).where(
            t.tools.c.route_id == wf["route_id"], t.tools.c.status == "active").order_by(t.tools.c.name))).mappings().all()
    rows = [r for r in rows if any(fnmatch.fnmatchcase(r["name"], p) for p in patterns)]
    if not rows:
        return []
    servers, specs, out, unkept = await hub.servers(wf["route_id"]), {}, [], []
    for r in rows:
        server = servers.get(r["server"])
        if server is None:
            log.warning("tool %s of route %s: no server %s", r["name"], wf["route_id"], r["server"])
            continue
        if not server["enabled"]:  # switched off: its tools are not there for any agent
            continue
        try:
            client = hub.client(wf["route_id"], server)
        except PartnerListError as e:  # its headers cannot be opened: it could not be called either
            log.warning("tool %s of route %s: %s", r["name"], wf["route_id"], e)
            continue
        if r["server"] not in specs:
            try:
                specs[r["server"]] = {s.name: s for s in await client.list_tools()}
            except PartnerListError as e:
                log.warning("server %s of route %s cannot be listed (%s): using the stored schemas", r["server"], wf["route_id"], e)
                specs[r["server"]] = None
        listed = specs[r["server"]]
        spec = stored_spec(r) if listed is None else listed.get(r["mcp_tool"])
        if spec is None:
            log.warning("tool %s of route %s: %s", r["name"], wf["route_id"], "the server cannot be listed and no schema is stored"
                        if listed is None else f"the partner does not offer {r['mcp_tool']}")
            continue
        if remote_ref(spec.input_schema):
            log.warning("tool %s of route %s: its schema refers to something outside itself", r["name"], wf["route_id"])
            continue
        if oversized(spec):
            log.warning("tool %s of route %s: its schema is too large", r["name"], wf["route_id"])
            continue
        vouched = r["read_only"] and (r["source"] == "manual" or r["consent_waiver"])
        if r["kind"] == "lookup" and not (spec.read_only or vouched):
            log.warning("tool %s of route %s: a look-up must be read only", r["name"], wf["route_id"])
            continue
        if listed is not None and not r["schema"]:
            unkept.append((r, spec))
        out.append(PartnerTool(rt, wf, r, spec, client))
    if unkept:
        await keep_snapshots(rt, unkept)
    return out
