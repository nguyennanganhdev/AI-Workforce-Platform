"""HTTP surface of the platform core, under /platform/v1."""
from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException, Request

from .intake.models import CaseIntake, FollowUp
from .intake.service import IntakeError, IntakeService
from .profiles import AgentProfile, ProfileError
from .runtime import Runtime
from .security import Principal


def build_router(rt: Runtime, intake: IntakeService) -> APIRouter:
    r = APIRouter(prefix="/platform/v1")

    def who(request: Request) -> Principal:
        p = getattr(request.state, "principal", None)
        if p is None:
            raise HTTPException(401, "no principal")
        return p

    def admin(request: Request) -> Principal:
        p = who(request)
        if not p.admin:
            raise HTTPException(403, "admin key required")
        return p

    def connector(request: Request) -> Principal:
        p = who(request)
        if p.domain is None and not p.admin:
            raise HTTPException(403, "no domain")
        return p

    async def own_case(p: Principal, case_id: str) -> dict:
        case = await rt.cases.get_case(case_id)
        if case is None or case["tenant"] != p.tenant:
            raise HTTPException(404, "no such case")
        if p.domain and case["domain"] != p.domain:
            raise HTTPException(404, "no such case")
        return case

    @r.get("/health")
    async def health():
        return {"status": "ok"}

    # ---- intake -----------------------------------------------------------
    @r.post("/intake", status_code=202)
    async def post_intake(body: CaseIntake, request: Request):
        p = connector(request)
        domain = p.domain or request.headers.get("x-awp-domain", "")
        if not domain:
            raise HTTPException(422, "admin keys must send X-AWP-Domain")
        try:
            return await intake.submit(p.tenant, domain, body)
        except IntakeError as e:
            raise HTTPException(e.status, e.message)

    @r.post("/cases/by-ref/{external_ref}/messages", status_code=202)
    async def post_message(external_ref: str, body: FollowUp, request: Request):
        p = connector(request)
        domain = p.domain or request.headers.get("x-awp-domain", "")
        try:
            return await intake.follow_up(p.tenant, domain, external_ref, body)
        except IntakeError as e:
            raise HTTPException(e.status, e.message)

    # ---- cases --------------------------------------------------------------
    @r.get("/cases")
    async def list_cases(request: Request, status: str | None = None, limit: int = 50):
        p = who(request)
        rows = await rt.cases.list_cases(p.tenant, status, min(limit, 200))
        return {"cases": [{k: c[k] for k in ("id", "domain", "external_ref", "status", "created_at")}
                          for c in rows if not p.domain or c["domain"] == p.domain]}

    @r.get("/cases/{case_id}")
    async def get_case(case_id: str, request: Request):
        case = await own_case(who(request), case_id)
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
        p = admin(request)
        return {"profiles": [x.model_dump() for x in await rt.profiles.list(p.tenant, status)]}

    @r.post("/profiles", status_code=201)
    async def create_profile(body: AgentProfile, request: Request):
        p = admin(request)
        try:
            return (await rt.profiles.create_draft(p.tenant, body)).model_dump()
        except ProfileError as e:
            raise HTTPException(409, str(e))

    @r.put("/profiles/{key}/versions/{version}")
    async def edit_profile(key: str, version: int, body: AgentProfile, request: Request):
        p = admin(request)
        try:
            return (await rt.profiles.update_draft(p.tenant, key, version, body)).model_dump()
        except ProfileError as e:
            raise HTTPException(409, str(e))

    @r.post("/profiles/{key}/versions/{version}/publish")
    async def publish_profile(key: str, version: int, request: Request):
        p = admin(request)
        try:
            rec = await rt.profiles.publish(p.tenant, key, version)
        except ProfileError as e:
            raise HTTPException(409, str(e))
        await rt.sync_templates()
        return rec.model_dump()

    @r.post("/profiles/{key}/retire")
    async def retire_profile(key: str, request: Request):
        p = admin(request)
        await rt.profiles.retire(p.tenant, key)
        await rt.sync_templates()
        return {"retired": key}

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

