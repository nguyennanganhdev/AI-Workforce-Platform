"""The sandbox an evaluation runs in: a real workflow on the real engine, cut off from everything real.

Each tenant has one internal client and route (environment `eval`). No API key can exist for that client (the admin
API does not see it), so nothing of a sandbox is reachable through /workforce/v1; its route has no MCP server and no
tool, so no partner is ever called; the events it writes belong to its own throw-away conversation. The agents get
their tools from the case's fixtures (a `Runtime.tool_factories` entry), their calls are traced into the case
file, and the leader is the exact version under test (a leader), or a minimal leader of the platform's own that
brings in the exact specialist version and nothing else.

What marks a case as a sandbox is `awp_cases.meta["eval"]` (the pin), written by `start` and by nothing else.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from types import SimpleNamespace
from typing import Any

from agentscope.message import TextBlock, ToolResultState
from agentscope.middleware import MiddlewareBase
from agentscope.permission import PermissionBehavior, PermissionDecision
from agentscope.tool import ToolBase, ToolChunk, ToolResponse
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError

from ..profiles import AgentProfile
from ..workforce import tables as t
from ..workforce.common import now

log = logging.getLogger("awp")

EVAL_ENV = t.EVAL_ENV  # wf_clients.environment of a sandbox client: the admin API's ClientIn cannot make one
EVAL_DOMAIN = "awp:eval"  # the domain of its cases (not a domain a partner can have: Slug has no colon)
EVAL_LEADER = "awp_eval_leader"  # profile key of the platform's own leader (ProfileStore refuses the awp_ prefix)
REF = "awp-eval"


def pin_of(case: dict | None) -> dict | None:
    """The sandbox pin of a case, None for every real one."""
    return ((case or {}).get("meta") or {}).get("eval")


def template_type(key: str, version: int) -> str:
    """The sub-agent type a draft specialist is created under. `@` cannot be in a profile key, so it never takes
    the place of a published specialist's template."""
    return f"{key}@{version}"


def eval_leader(pin: dict) -> AgentProfile:
    """The leader of a specialist's evaluation: it may create that one specialist version, and is told to do only that."""
    kind = pin["type"]
    return AgentProfile(
        key=EVAL_LEADER, name="eval-leader", role="leader", team=[kind], model_tier="cheap", max_iters=8,
        mission="the platform's harness for evaluating one specialist.",
        instructions=(
            "This is an evaluation, not a real resident. Do exactly this and nothing else: TeamCreate, then AgentCreate "
            f"ONE specialist with subagent_type {kind!r} and give it the resident's message, word for word, as its task. "
            "Do not answer the task yourself and call no other tool. When its report wakes you, end with "
            "CaseFinalize(answer='Evaluation finished.', outcome='needs_human', unknowns=['evaluation only'])."))


async def leader_for(rt, tenant: str, pin: dict) -> tuple[AgentProfile, int] | None:
    """The leader of a sandbox workflow: the pinned version of a leader profile whatever its status, or the platform's
    eval leader when a specialist is under test."""
    if pin["role"] == "specialist":
        return eval_leader(pin), 0
    rec = await rt.profiles.get(tenant, pin["key"], pin["version"])
    return (rec.profile, rec.version) if rec is not None and rec.profile.role == "leader" else None


# ---- the tenant's sandbox client and route ---------------------------------------------------------------
def ids(tenant: str) -> tuple[str, str]:
    h = hashlib.sha256(tenant.encode()).hexdigest()[:32]
    return f"client_eval_{h}", f"route_eval_{h}"


async def ensure(db, tenant: str) -> dict:
    """The tenant's sandbox route, made on first use. The ids are a function of the tenant, so two first uses at
    once meet on the primary key and the loser finds the winner's rows."""
    from ..workforce.schemas import RouteConfig

    client_id, route_id = ids(tenant)
    for _ in range(2):
        async with db.engine.connect() as conn:
            route = (await conn.execute(select(t.routes).where(t.routes.c.id == route_id))).mappings().first()
        if route is not None:
            return dict(route)
        config = {**RouteConfig().model_dump(), "wait_seconds": 0}
        config["policy"]["approval_ttl_seconds"] = 3600
        try:
            async with db.engine.begin() as conn:
                await conn.execute(insert(t.clients).values(
                    id=client_id, tenant=tenant, domain=EVAL_DOMAIN, environment=EVAL_ENV, name="evaluation sandbox",
                    status="active", capabilities=[], created_at=now()))
                await conn.execute(insert(t.routes).values(
                    id=route_id, client_id=client_id, external_management_ref=REF, status="active", revision=1,
                    leader_profile=EVAL_LEADER, config=config, manager_id=None, created_at=now()))
        except IntegrityError:
            continue
    raise RuntimeError("could not make the evaluation sandbox")


async def start(ctx, tenant: str, ref: str, text: str, pin: dict, budget_usd: float, budget_tokens: int):
    """Start a sandbox workflow with `text` as the resident's message: the same rows a partner's start_workflow
    writes (`commands._admit`), under the sandbox client, and the pin on its case. Returns what `accept` returns."""
    from ..workforce import commands
    from ..workforce.schemas import RequestIn

    route = await ensure(ctx.db, tenant)
    who = SimpleNamespace(client=SimpleNamespace(id=route["client_id"], tenant=tenant, domain=EVAL_DOMAIN),
                          covers=lambda route_id: True)
    body = RequestIn(schema_version="1", command_type="start_workflow", external_request_id=ref,
                     external_management_ref=REF, external_user_id="evaluation", external_ticket_id=ref,
                     external_conversation_id=ref, message={"type": "text", "text": text})
    async with ctx.db.engine.begin() as conn:
        accepted = await commands._admit(ctx, conn, who, body, commands.fingerprint(body), route, 0.0)
        case_id = (await conn.execute(select(t.workflows.c.case_id).where(
            t.workflows.c.id == accepted.workflow_id))).scalar_one()
        await ctx.rt.cases.update_case(case_id, conn=conn, budget_usd=budget_usd, budget_tokens=budget_tokens, meta={
            "workflow_id": accepted.workflow_id, "route_id": route["id"], "residence_id": None, "timezone": "UTC",
            "eval": pin})
    return accepted, case_id


async def stop(ctx, workflow_id: str, grace: float = 3.0) -> None:
    """End a sandbox workflow whatever it is doing: closed, its agents interrupted, nothing left for a sweep to run."""
    from ..workforce.close import shut
    from ..workforce.events import lock_conversation

    async with ctx.db.engine.begin() as conn:
        wf = (await conn.execute(select(t.workflows).where(t.workflows.c.id == workflow_id))).mappings().one()
        await lock_conversation(conn, wf["conversation_id"])
        wf = (await conn.execute(select(t.workflows).where(t.workflows.c.id == workflow_id))).mappings().one()
        if wf["state"] != "closed":
            await shut(ctx.rt, conn, wf, "evaluation_over")
    client = getattr(ctx.engine, "client", None)
    case = await ctx.rt.cases.get_case(wf["case_id"])
    if client is None or case is None:
        return
    sessions = await ctx.rt.cases.sessions_of_case(wf["case_id"])

    async def busy() -> list:
        return [s for s in sessions
                if await client.status(case["tenant"], s["agent_id"], s["session_id"]) not in ("idle", "gone")]

    end = time.monotonic() + grace  # a run that is just ending is left to end: cutting it mid-write helps nobody
    while await busy() and time.monotonic() < end:
        await asyncio.sleep(0.05)
    for s in await busy():
        try:
            await client.interrupt(case["tenant"], s["agent_id"], s["session_id"])
        except Exception:
            log.exception("could not interrupt sandbox session %s", s["session_id"])


# ---- what the agents of a sandbox get ---------------------------------------------------------------------
class FixtureTool(ToolBase):
    """A tool that answers what the evaluation case says it answers. It reaches nothing."""

    is_read_only = True
    is_concurrency_safe = True

    def __init__(self, name: str, answer: Any) -> None:
        super().__init__()
        self.name = name
        self.description = f"{name} (a recorded answer of the evaluation sandbox)."
        self.input_schema = {"type": "object", "properties": {}, "additionalProperties": True}
        self.answer = answer if isinstance(answer, str) else json.dumps(answer, ensure_ascii=False)

    async def check_permissions(self, *args: Any, **kwargs: Any) -> PermissionDecision:
        return PermissionDecision(behavior=PermissionBehavior.ALLOW, message="fixture of an evaluation")

    async def call(self, **given: Any) -> ToolChunk:
        return ToolChunk(content=[TextBlock(text=self.answer)], state=ToolResultState.SUCCESS)


async def fixture_tools(rt, b) -> list:
    """`Runtime.tool_factories` entry: the fixtures of the case, for every agent of a sandbox; nothing elsewhere."""
    pin = pin_of(await rt.cases.get_case(b.case_id))
    return [FixtureTool(name, answer) for name, answer in ((pin or {}).get("fixtures") or {}).items()]


def only_fixtures(tools: list) -> list:
    """In a sandbox a fixture stands in for the real tool of its name (it must not be the one that is replaced)."""
    fixed = {x.name for x in tools if isinstance(x, FixtureTool)}
    return [x for x in tools if isinstance(x, FixtureTool) or x.name not in fixed]


class Trace(MiddlewareBase):
    """Writes every tool call of a sandbox agent into the case file (kind `trace`: who, which tool, with what, did it
    succeed), which is what the checks read. Refused calls are kept too: an agent that tried to state an invented
    figure did invent it, whether or not the guard stopped it."""

    def __init__(self, rt, b) -> None:
        self.rt, self.b = rt, b

    async def on_acting(self, agent, input_kwargs, next_handler):
        call = input_kwargs["tool_call"]
        async for item in next_handler(**input_kwargs):
            if isinstance(item, ToolResponse):
                try:
                    await self.rt.cases.add(self.b.case_id, "trace", self.b.agent_name, {
                        "tool": call.name[:80], "input": (call.input or "")[:4000], "role": self.b.role,
                        "ok": item.state == ToolResultState.SUCCESS})
                except Exception:  # the run goes on; the case fails on what is missing
                    log.exception("could not trace a tool call of sandbox case %s", self.b.case_id)
            yield item
