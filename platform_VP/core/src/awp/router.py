"""Admin HTTP surface of the platform core, under /platform/v1: profiles, the agent builder, models, cost, metrics
and the cases of the admin's tenant. Partners use /workforce/v1 (workforce/); the partner admin API is
workforce/admin.py; evaluating and releasing a profile is release.py.

Everything in this file is the tenant admin's. A manager's key (M6) reads one thing here: the profiles its own
routes use (what it may do with them is in release.py)."""
from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from .builder import MAX_TEXT, BuilderError
from .evals.sandbox import EVAL_DOMAIN
from .profiles import AgentProfile, ProfileError
from .release import build_release, users_of
from .runtime import Runtime
from .security import Principal


class MessageIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=MAX_TEXT)


class ApplyItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    index: int = Field(ge=0)
    override_reason: str | None = Field(default=None, max_length=300)  # create it although an existing agent overlaps


class ApplyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ApplyItem] | None = Field(default=None, max_length=20)  # every proposal when left out


def session_out(s: dict) -> dict:
    return {"session_id": s["id"], "messages": s["messages"], "proposals": s["proposals"],
            "created_at": s["created_at"], "updated_at": s["updated_at"]}


def build_router(rt: Runtime) -> APIRouter:
    r = APIRouter(prefix="/platform/v1")

    def caller(request: Request) -> Principal:
        p = getattr(request.state, "principal", None)
        if p is None:
            raise HTTPException(401, "no principal")
        return p

    def admin(request: Request) -> Principal:
        p = caller(request)
        if p.manager_id:
            raise HTTPException(403, "this needs the tenant's admin key")
        return p

    async def manager_keys(p: Principal) -> set[str]:
        """The profiles a manager's routes use: the same reading as for what it may evaluate and release."""
        return {key for key, users in (await users_of(rt, p.tenant)).items() if p.manager_id in users}

    async def own_case(p: Principal, case_id: str) -> dict:
        case = await rt.cases.get_case(case_id)
        if case is None or case["tenant"] != p.tenant:
            raise HTTPException(404, "no such case")
        return case

    @r.get("/health")
    async def health():
        return {"status": "ok"}

    # ---- cases --------------------------------------------------------------
    @r.get("/cases")
    async def list_cases(request: Request, status: str | None = None, limit: int = 50):
        p = admin(request)
        rows = await rt.cases.list_cases(p.tenant, status, min(limit, 200))
        return {"cases": [{k: c[k] for k in ("id", "domain", "external_ref", "status", "created_at")}
                          for c in rows if c["domain"] != EVAL_DOMAIN]}  # a sandbox case is read through its eval run

    @r.get("/cases/{case_id}")
    async def get_case(case_id: str, request: Request):
        case = await own_case(admin(request), case_id)
        return {"id": case["id"], "domain": case["domain"], "external_ref": case["external_ref"],
                "status": case["status"], "result": case["result"],
                "cost": await rt.cost.case_totals(case_id)}

    @r.get("/cases/{case_id}/items")
    async def case_items(case_id: str, request: Request, after: int = 0):
        await own_case(admin(request), case_id)
        items = await rt.cases.items(case_id, after_id=after)
        return {"items": [{"id": i.id, "ref": i.ref, "kind": i.kind, "author": i.author,
                           "addressee": i.addressee, "data": i.data} for i in items]}

    @r.get("/cases/{case_id}/cost")
    async def case_cost(case_id: str, request: Request):
        await own_case(admin(request), case_id)
        return {"totals": await rt.cost.case_totals(case_id),
                "by_agent": await rt.cost.breakdown(case_id, "agent_name"),
                "by_model": await rt.cost.breakdown(case_id, "model")}

    @r.get("/cost")
    async def tenant_cost(request: Request, since_hours: float = 24.0):
        p = admin(request)
        return {"models": await rt.cost.tenant_summary(p.tenant, time.time() - since_hours * 3600)}

    # ---- profiles ---------------------------------------------------------
    @r.get("/profiles")
    async def list_profiles(request: Request, status: str | None = None):
        p = caller(request)
        rows = await rt.profiles.list(p.tenant, status)
        if p.manager_id:
            keys = await manager_keys(p)
            rows = [x for x in rows if x.key in keys]
        return {"profiles": [x.model_dump() for x in rows]}

    @r.post("/profiles", status_code=201)
    async def create_profile(body: AgentProfile, request: Request):
        p = admin(request)
        try:
            return (await rt.profiles.create_draft(p.tenant, body, by=p.actor, detail={"source": "api"})).model_dump()
        except ProfileError as e:
            raise HTTPException(409, str(e))

    @r.put("/profiles/{key}/versions/{version}")
    async def edit_profile(key: str, version: int, body: AgentProfile, request: Request):
        p = admin(request)
        try:
            out = await rt.profiles.update_draft(p.tenant, key, version, body)
        except ProfileError as e:
            raise HTTPException(409, str(e))
        rt._profile_cache.pop((p.tenant, key, version), None)  # an evaluation runs the draft as it is now
        return out.model_dump()

    @r.post("/profiles/{key}/retire")
    async def retire_profile(key: str, request: Request):
        p = admin(request)
        await rt.profiles.retire(p.tenant, key, by=p.actor)
        await rt.sync_templates()
        return {"retired": key}

    build_release(r, rt, caller)  # evaluation cases and runs, publish (behind the eval gate), rollback, history

    # ---- the agent builder (M2): a chat that ends in drafts --------------------
    def refuse(e: BuilderError):
        raise HTTPException(e.status, str(e))

    @r.post("/builder/sessions", status_code=201)
    async def new_builder_session(request: Request):
        p = admin(request)
        return session_out(await rt.builder.create(p.tenant, p.actor))

    @r.get("/builder/sessions/{session_id}")
    async def read_builder_session(session_id: str, request: Request):
        p = admin(request)
        try:
            return session_out(await rt.builder.get(p.tenant, session_id))
        except BuilderError as e:
            refuse(e)

    @r.post("/builder/sessions/{session_id}/messages")
    async def builder_message(session_id: str, body: MessageIn, request: Request):
        """What the admin wants, in their words; the answer is the proposals now on the table."""
        p = admin(request)
        try:
            return session_out(await rt.builder.message(p.tenant, session_id, body.text))
        except BuilderError as e:
            refuse(e)

    @r.post("/builder/sessions/{session_id}/apply")
    async def builder_apply(session_id: str, request: Request, body: ApplyIn | None = None):
        """Make the proposals into drafts (never published). A `reuse` makes nothing and names the agent to use."""
        p = admin(request)
        items = [i.model_dump() for i in body.items] if body is not None and body.items is not None else None
        try:
            return await rt.builder.apply(p.tenant, session_id, p.actor, items)
        except BuilderError as e:
            refuse(e)

    # ---- models and Jev ---------------------------------------------------
    @r.get("/models")
    async def models(request: Request):
        admin(request)
        return {"models": [{"id": s.id, "provider": s.provider, "model": s.model, "tier": s.tier,
                            "available": s.available(), "priced": s.priced}
                           for s in rt.catalog.specs.values()]}

    @r.get("/metrics")
    async def metrics(request: Request):
        admin(request)
        m = dict(rt.metrics)
        m["tool_schema_saving"] = (1 - m["tool_chars_sent"] / m["tool_chars_offered"]
                                   if m["tool_chars_offered"] else None)
        return m

    @r.get("/jev")
    async def jev(request: Request):
        admin(request)
        stats = getattr(rt.judge, "stats", None)
        return {"enabled": rt.judge is not None, "stats": stats.as_dict() if stats else None}

    return r

