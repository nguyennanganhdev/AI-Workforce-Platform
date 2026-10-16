"""Releasing an agent (M3): evaluate the exact version, then a PERSON publishes it; roll back; read the history.

The gate: a version goes live only when the latest evaluation run of that very version passed, on the content it
has now and with the cases it has now. An admin may override that with a reason, which is recorded (who, when, why).
A rollback publishes a version that was live before; it is not evaluated again, and it is recorded.

These endpoints are the only callers of `ProfileStore.publish`. No agent tool reaches them: an agent has no admin
key, and nothing in the agent-facing code (protocol/, middleware/, workforce/partner_tools.py, the builder) calls
publish.

Who may. The tenant's admin: everything. An operator of a management account (M6), for the profiles its own routes
use (`users_of`): read the cases, runs and history, and run an evaluation. For a profile that no other account's route
uses it may also edit the cases, publish (with a passing evaluation, never by override) and roll back; a profile
shared with another account is released by the admin. Another account's profile answers 404. A manager's rollback
only undoes a release: it replaces the live version by one that went live through the gate. Bringing back an agent
the admin retired, or a version that only an override let through, stays the admin's.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from .evals.store import CaseIn, EvalError, cases_digest, digest, run_out
from .profiles import ProfileDenied, ProfileError, ProfileRecord
from .runtime import Runtime
from .security import Principal
from .workforce import tables as wt
from .workforce.adminkit import tenant_clients


class PublishIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    override_reason: str | None = Field(default=None, max_length=300)


class RollbackIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    to_version: int = Field(ge=1)


class RunIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    wait_seconds: float = Field(default=0, ge=0, le=600)  # answer when the run ended, or after this long


async def users_of(rt: Runtime, tenant: str) -> dict[str, set]:
    """profile key -> the management accounts whose routes use it (None: a route with no account): as a leader, as a
    member of that leader's team in any version, or, when the leader names no team, as any specialist of the tenant
    (such a leader may bring every one of them in: middleware/room.py `creatable`). "Names no team" is read from the
    version a new workflow would get: the published one, else the newest."""
    async with rt.db.engine.connect() as conn:
        routes = (await conn.execute(select(wt.routes.c.leader_profile, wt.routes.c.manager_id).where(
            wt.routes.c.client_id.in_(tenant_clients(tenant))))).all()
    teams: dict[str, set[str]] = {}
    serving: dict[str, ProfileRecord] = {}
    specialists: set[str] = set()
    for rec in await rt.profiles.list(tenant):  # by key, then version
        teams.setdefault(rec.key, set()).update(rec.profile.team)
        if rec.profile.role == "specialist":
            specialists.add(rec.key)
        if rec.status == "published" or serving.get(rec.key) is None or serving[rec.key].status != "published":
            serving[rec.key] = rec
    out: dict[str, set] = {}
    for leader, manager in routes:
        view = serving.get(leader)
        everyone = specialists if view is not None and view.profile.role == "leader" and not view.profile.team else ()
        for key in {leader, *teams.get(leader, ()), *everyone}:
            out.setdefault(key, set()).add(manager)
    return out


async def gate(rt: Runtime, tenant: str, rec: ProfileRecord) -> dict | None:
    """Why this version may not go live yet (the body of the 409), or None when it may."""
    if not rt.settings.eval_gate:
        return None
    run = await rt.evals.store.latest(tenant, rec.key, rec.version)
    if run is None:
        why = "this version has not been evaluated"
    elif run["status"] == "running":
        why = "the evaluation of this version is still running"
    elif run["status"] != "passed":
        why = f"the latest evaluation of this version ended as {run['status']}"
    elif run["profile_hash"] != digest(rec.profile):
        why = "the draft was edited after it was evaluated"
    elif run["cases_hash"] != cases_digest(await rt.evals.cases(tenant, rec)):
        why = "the evaluation cases of this agent changed after it was evaluated"
    else:
        return None
    return {"code": "EVAL_REQUIRED", "message": why + ": run its evaluation, or publish with an override_reason",
            "latest_run": {k: run_out(run)[k] for k in ("run_id", "status", "score", "created_at")} if run else None}


def build_release(r: APIRouter, rt: Runtime, caller) -> None:
    async def may(request: Request, key: str, write: bool = False) -> Principal:
        """The caller, if it may read (or with `write` change and release) this profile key."""
        p: Principal = caller(request)
        if p.manager_id:
            users = (await users_of(rt, p.tenant)).get(key, set())
            if p.manager_id not in users:
                raise HTTPException(404, "no such profile")
            if write and users != {p.manager_id}:
                raise HTTPException(403, "another management account uses this profile too: the tenant's admin releases it")
        return p

    async def version_of(p: Principal, key: str, version: int) -> ProfileRecord:
        rec = await rt.profiles.get(p.tenant, key, version)
        if rec is None:
            raise HTTPException(404, "no such profile version")
        return rec

    def refuse(e: EvalError):
        raise HTTPException(e.status, str(e))

    # ---- evaluation cases ------------------------------------------------------
    @r.get("/profiles/{key}/eval-cases")
    async def list_cases(key: str, request: Request):
        """The platform's cases for the newest version of the key (read-only), then the tenant's own."""
        p = await may(request, key)
        newest = await rt.profiles.latest(p.tenant, key)
        if newest is None:
            raise HTTPException(404, "no such profile")
        return {"cases": await rt.evals.cases(p.tenant, newest)}

    @r.post("/profiles/{key}/eval-cases", status_code=201)
    async def add_case(key: str, body: CaseIn, request: Request):
        p = await may(request, key, write=True)
        if await rt.profiles.latest(p.tenant, key) is None:
            raise HTTPException(404, "no such profile")
        try:
            return await rt.evals.store.add_case(p.tenant, key, body)
        except EvalError as e:
            refuse(e)

    @r.put("/profiles/{key}/eval-cases/{case_id}")
    async def set_case(key: str, case_id: str, body: CaseIn, request: Request):
        p = await may(request, key, write=True)
        try:
            return await rt.evals.store.set_case(p.tenant, key, case_id, body)
        except EvalError as e:
            refuse(e)

    @r.delete("/profiles/{key}/eval-cases/{case_id}")
    async def drop_case(key: str, case_id: str, request: Request):
        p = await may(request, key, write=True)
        try:
            await rt.evals.store.drop_case(p.tenant, key, case_id)
        except EvalError as e:
            refuse(e)
        return {"deleted": case_id}

    # ---- evaluation runs ---------------------------------------------------------
    @r.post("/profiles/{key}/versions/{version}/evals")
    async def run_eval(key: str, version: int, request: Request, body: RunIn | None = None):
        """Start a run of this exact version: 202 while it runs, 200 with the result once it ended."""
        p = await may(request, key)
        rec = await version_of(p, key, version)
        if rec.status == "retired":
            raise HTTPException(409, "a retired version is not evaluated; roll back to it, or make a new draft")
        try:
            run = await rt.evals.start(p.tenant, rec, p.actor)
        except EvalError as e:
            refuse(e)
        if body is not None and body.wait_seconds:
            run = await rt.evals.wait(p.tenant, run["id"], body.wait_seconds) or run
        return JSONResponse(run_out(run), status_code=202 if run["status"] == "running" else 200)

    @r.get("/profiles/{key}/versions/{version}/evals")
    async def list_evals(key: str, version: int, request: Request):
        p = await may(request, key)
        await version_of(p, key, version)
        await rt.evals.store.reap()
        return {"runs": [run_out(x) for x in await rt.evals.store.runs(p.tenant, key, version)]}

    # ---- publish, roll back, history ------------------------------------------------
    async def team_check(p: Principal, rec: ProfileRecord) -> list[str]:
        """A leader that names nobody real would be offered specialists it can never create (M4)."""
        if rec.profile.role != "leader":
            return []
        missing, unpublished = await rt.profiles.team_gaps(p.tenant, rec.profile)
        if missing:
            raise HTTPException(422, f"team members that are not specialist profiles of this tenant: {missing}")
        return [f"team member {k!r} has no published version yet: the leader cannot bring it in until it has"
                for k in unpublished]

    async def go_live(p: Principal, rec: ProfileRecord, **how: Any) -> dict:
        warnings = await team_check(p, rec)
        try:
            out = await rt.profiles.publish(p.tenant, rec.key, rec.version, checked=rec.profile, by=p.actor, **how)
        except ProfileDenied as e:
            raise HTTPException(403, str(e))
        except ProfileError as e:
            raise HTTPException(409, str(e))
        await rt.sync_templates()
        return {**out.model_dump(), "warnings": warnings}

    @r.post("/profiles/{key}/versions/{version}/publish")
    async def publish_profile(key: str, version: int, request: Request, body: PublishIn | None = None):
        p = await may(request, key, write=True)
        rec = await version_of(p, key, version)
        reason = (body.override_reason or "").strip() if body else ""
        if reason and p.manager_id:
            raise HTTPException(403, "only the tenant's admin can publish without a passing evaluation")
        if rec.status == "draft" and not reason:
            await team_check(p, rec)  # what is wrong with the profile itself comes before what is missing around it
            refused = await gate(rt, p.tenant, rec)
            if refused is not None:
                raise HTTPException(409, refused)
        return await go_live(p, rec, override_reason=reason or None)

    @r.post("/profiles/{key}/rollback")
    async def rollback_profile(key: str, body: RollbackIn, request: Request):
        """Make an earlier, once published version the live one again. Running workflows keep the leader they started
        with; whoever is created after this (a new workflow's leader, a specialist brought in) is the version rolled
        back to."""
        p = await may(request, key, write=True)
        rec = await version_of(p, key, body.to_version)
        if p.manager_id and any(e["kind"] == "override" and e["version"] == rec.version
                                for e in await rt.profiles.history(p.tenant, key)):
            raise HTTPException(403, "this version went live by the admin's override, not through its evaluation: "
                                     "the admin rolls back to it")
        # the store refuses a draft or the live one, and for a manager a key with nothing live
        return await go_live(p, rec, rollback=True, replace_only=bool(p.manager_id))

    @r.get("/profiles/{key}/history")
    async def history(key: str, request: Request):
        p = await may(request, key)
        events = await rt.profiles.history(p.tenant, key)
        if not events and await rt.profiles.latest(p.tenant, key) is None:
            raise HTTPException(404, "no such profile")
        return {"key": key, "events": events}
