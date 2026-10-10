"""Human workspace over the same durable Workforce engine as partner requests."""
import hashlib
import secrets
import time
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import insert, select, text, update

from ..db import case_sessions
from . import models as m
from . import schema as s
from .service import Fault, digest, row, uid


class WorkspaceSetup(BaseModel):
    model_config = ConfigDict(extra="forbid")
    leader_profile: str
    budget_micros: int = Field(default=500000, ge=1)
    budget_tokens: int = Field(default=100000, ge=1)


class WorkspaceMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=20000)


class WorkspaceClose(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(min_length=1, max_length=100)
    expected_revision: int = Field(ge=1)
    action: Literal["confirm", "stop"]


def client_id(tenant):
    return "console_" + hashlib.sha256(tenant.encode()).hexdigest()[:32]


def build_workspace(service):
    r = APIRouter(prefix="/workforce/v1/admin/workspace")
    rt = service.rt

    def principal(request):
        p = getattr(request.state, "principal", None)
        if not p or not p.admin:
            raise Fault(403, "ADMIN_REQUIRED")
        return p

    async def leader(tenant, key, ready=False):
        rec = await rt.profiles.get_published(tenant, key)
        if not rec or rec.profile.role != "leader":
            raise Fault(422, "LEADER_NOT_PUBLISHED")
        if ready:
            for profile_key in [key, *rec.profile.team]:
                profile = await rt.profiles.get_published(tenant, profile_key)
                if not profile or (profile_key != key and profile.profile.role != "specialist"):
                    raise Fault(422, "SPECIALIST_NOT_PUBLISHED")
                spec = rt.catalog.specs.get(profile.profile.model_id) if profile.profile.model_id else rt.catalog.pick(profile.profile.model_tier)
                if not spec or not spec.available(rt.catalog._env):
                    raise Fault(503, "MODEL_NOT_CONFIGURED", "Agent chưa có model khả dụng: " + profile_key)
                if not spec.priced:
                    raise Fault(503, "MODEL_PRICE_NOT_CONFIGURED", "Chưa cấu hình giá model: " + spec.id)
        return rec

    @r.get("/setup")
    async def setup(request: Request):
        p = principal(request)
        async with rt.db.engine.connect() as conn:
            client = await row(conn, s.clients, s.clients.c.id == client_id(p.tenant), s.clients.c.tenant == p.tenant)
        return {"configured": bool(client), "settings": client["settings"].get("workspace") if client else None}

    @r.put("/setup")
    async def save_setup(body: WorkspaceSetup, request: Request):
        p = principal(request)
        await leader(p.tenant, body.leader_profile)
        cid = client_id(p.tenant)
        async with service.tx() as conn:
            if conn.dialect.name == "postgresql":
                await conn.execute(text("SELECT pg_advisory_xact_lock(:key)"),
                    {"key": int(digest([p.tenant, "workspace-setup"])[:15], 16)})
            client = await row(conn, s.clients, s.clients.c.id == cid, lock=True)
            if client:
                if client["tenant"] != p.tenant or client["purpose"] != "customer":
                    raise Fault(409, "WORKSPACE_CLIENT_CONFLICT")
                await conn.execute(update(s.clients).where(s.clients.c.id == cid).values(settings={"workspace": body.model_dump()}))
            else:
                await conn.execute(insert(s.clients).values(id=cid, tenant=p.tenant, purpose="customer",
                    key_hash=digest(secrets.token_bytes(32)), status="active", expires=None,
                    operations=["submit_request", "reply", "read_result"], settings={"workspace": body.model_dump()}))
            await service.audit(conn, p.tenant, p.actor, "workspace.configure", cid, body.model_dump())
        return {"configured": True, "settings": body.model_dump()}

    @r.post("/sessions", status_code=202)
    async def start(body: WorkspaceMessage, request: Request):
        p = principal(request)
        cid = client_id(p.tenant)
        async with rt.db.engine.connect() as conn:
            client = await row(conn, s.clients, s.clients.c.id == cid, s.clients.c.tenant == p.tenant, s.clients.c.status == "active")
        if not client or not client["settings"].get("workspace"):
            raise Fault(409, "WORKSPACE_NOT_CONFIGURED")
        external_id = digest({"actor": p.actor, "request_id": body.request_id})
        async with rt.db.engine.connect() as conn:
            old = await row(conn, s.requests, s.requests.c.client_id == cid, s.requests.c.external_id == external_id)
        if old:
            if old["command"] != "start_workflow" or old["body"]["message"]["text"] != body.text:
                raise Fault(409, "IDEMPOTENCY_CONFLICT")
            _, result = await service.representation(client, old["id"], p.actor)
            return result
        config = client["settings"]["workspace"]
        rec = await leader(p.tenant, config["leader_profile"], ready=True)
        # New settings get a new route; existing workflows keep their revision.
        ref = "workspace-" + digest(config)[:24]
        async with service.tx() as conn:
            await row(conn, s.clients, s.clients.c.id == cid, lock=True)
            route = await row(conn, s.routes, s.routes.c.client_id == cid, s.routes.c.external_ref == ref)
            if not route:
                route_config = m.RouteCreate(client_id=cid, external_management_ref=ref, workspace="internal",
                    manager_ref="platform", leader_profile=rec.key, ticket_binding_mode="optional", require_residence=False,
                    read_only_auto_close=True, knowledge_base_ids=rec.profile.knowledge.knowledge_base_ids,
                    budget_micros=config["budget_micros"], budget_tokens=config["budget_tokens"]).model_dump()
                await conn.execute(insert(s.routes).values(id=uid(), client_id=cid, external_ref=ref,
                    status="active", revision=1, config=route_config))
        command = m.Command(command_type="start_workflow", external_request_id=external_id,
            external_management_ref=ref, external_user_id=p.actor, external_conversation_id=external_id,
            message=m.Message(text=body.text))
        rid = await service.submit(client, command)
        _, result = await service.representation(client, rid, p.actor)
        return result

    @r.post("/sessions/{workflow_id}/messages", status_code=202)
    async def reply(workflow_id: str, body: WorkspaceMessage, request: Request):
        p = principal(request)
        async with rt.db.engine.connect() as conn:
            client = await row(conn, s.clients, s.clients.c.id == client_id(p.tenant), s.clients.c.tenant == p.tenant,
                s.clients.c.status == "active")
            if not client:
                raise Fault(404, "NOT_FOUND")
            _wf, conv = await service.binding(conn, client, workflow_id, p.actor)
            route = await row(conn, s.routes, s.routes.c.id == conv["route_id"])
        command = m.Command(command_type="workflow_reply", workflow_id=workflow_id,
            external_request_id=digest({"actor": p.actor, "request_id": body.request_id}),
            external_management_ref=route["external_ref"], external_user_id=p.actor,
            external_conversation_id=conv["external_conversation_id"],
            message=m.Message(text=body.text))
        rid = await service.submit(client, command)
        _, result = await service.representation(client, rid, p.actor)
        return result

    @r.get("/sessions")
    async def sessions(request: Request):
        p = principal(request)
        async with rt.db.engine.connect() as conn:
            records = (await conn.execute(select(s.workflows, s.conversations.c.client_id).join(s.conversations,
                s.conversations.c.id == s.workflows.c.conversation_id).join(s.clients,
                s.clients.c.id == s.conversations.c.client_id).where(s.clients.c.tenant == p.tenant)
                .order_by(s.workflows.c.updated.desc()).limit(200))).mappings().all()
            starts = (await conn.execute(select(s.requests.c.workflow_id, s.requests.c.body).where(
                s.requests.c.workflow_id.in_([w["id"] for w in records]),
                s.requests.c.command == "start_workflow"))).mappings().all()
            inputs = {x["workflow_id"]: x["body"] for x in starts}
            result = []
            for w in records:
                result.append({"id": w["id"], "state": w["state"], "created": w["created"], "updated": w["updated"],
                    "title": inputs.get(w["id"], {}).get("message", {}).get("text", "Công việc")[:180],
                    "leader_profile": w["snapshot"]["leader_profile"], "case_id": w["case_id"],
                    "source": "internal" if w["client_id"] == client_id(p.tenant) else "partner",
                    "client_id": w["client_id"]})
        return {"items": result, "limit": 200}

    @r.post("/sessions/{workflow_id}/close")
    async def close(workflow_id: str, body: WorkspaceClose, request: Request):
        from .lifecycle import close as close_workflow
        p = principal(request)
        async with rt.db.engine.connect() as conn:
            client = await row(conn, s.clients, s.clients.c.id == client_id(p.tenant), s.clients.c.tenant == p.tenant,
                s.clients.c.status == "active")
            if not client:
                raise Fault(404, "NOT_FOUND")
            _wf, conv = await service.binding(conn, client, workflow_id, p.actor)
            if body.action == "confirm" and _wf["state"] not in ("awaiting_confirmation", "closed"):
                raise Fault(409, "WORKFLOW_NOT_READY_TO_CLOSE")
        command = m.Close(external_request_id=digest({"actor": p.actor, "request_id": body.request_id}),
            external_user_id=p.actor, external_conversation_id=conv["external_conversation_id"],
            expected_revision=body.expected_revision, stop_tracking_only=body.action == "stop",
            reason="workspace_user_requested_stop_tracking" if body.action == "stop" else "workspace_user_confirmed_completion")
        return await close_workflow(service, client, workflow_id, command)

    @r.get("/sessions/{workflow_id}")
    async def inspect(workflow_id: str, request: Request):
        p = principal(request)
        async with rt.db.engine.connect() as conn:
            wf = await row(conn, s.workflows, s.workflows.c.id == workflow_id)
            if not wf or wf["snapshot"]["tenant"] != p.tenant:
                raise Fault(404, "NOT_FOUND")
            conv = await row(conn, s.conversations, s.conversations.c.id == wf["conversation_id"])
            queries = {"team": select(case_sessions).where(case_sessions.c.case_id == wf["case_id"]),
                "memory": select(s.memory).where(s.memory.c.workflow_id == workflow_id),
                "events": select(s.events).where(s.events.c.workflow_id == workflow_id).order_by(s.events.c.sequence.desc()).limit(500),
                "requests": select(s.requests).where(s.requests.c.workflow_id == workflow_id).order_by(s.requests.c.created).limit(500),
                "operations": select(s.operations).where(s.operations.c.workflow_id == workflow_id).limit(500),
                "approvals": select(s.approvals).where(s.approvals.c.workflow_id == workflow_id).limit(500)}
            data = {k: [dict(x) for x in (await conn.execute(q)).mappings().all()] for k, q in queries.items()}
        data["events"].reverse()
        # Expose the shared work record, not hidden chain of thought or provider credentials.
        data["requests"] = [{k: x[k] for k in ("id", "status", "command", "body", "result", "error", "created")} for x in data["requests"]]
        data["operations"] = [{k: x[k] for k in ("id", "status", "external_job_id", "created")} for x in data["operations"]]
        data["items"] = [{"ref": x.ref, "kind": x.kind, "author": x.author, "addressee": x.addressee, "data": x.data, "created": x.created_at}
            for x in await rt.cases.items(wf["case_id"])] if wf["case_id"] else []
        data["cost"] = {"totals": await rt.cost.case_totals(wf["case_id"]),
            "by_agent": await rt.cost.breakdown(wf["case_id"], "agent_name")} if wf["case_id"] else None
        return {**data, "workflow": wf, "can_manage": conv["client_id"] == client_id(p.tenant) and conv["user_id"] == p.actor,
            "can_reply": conv["client_id"] == client_id(p.tenant) and conv["user_id"] == p.actor
            and wf["state"] in ("active", "accepted", "awaiting_user", "awaiting_confirmation"),
            "source": "internal" if conv["client_id"] == client_id(p.tenant) else "partner", "observed_at": time.time()}

    return r
