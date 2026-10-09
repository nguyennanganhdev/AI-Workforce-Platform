import asyncio
import io
import json
import secrets
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from croniter import croniter
from fastapi import Depends, FastAPI, HTTPException, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import Field, ValidationError
from sqlalchemy import delete, func, select, text

from . import db as database
from .automation import continue_workflow, next_cron, start_workflow
from .config import settings
from .context import lexical_search
from .db import (
    Artifact,
    Audit,
    Event,
    Job,
    Login,
    Membership,
    Record,
    Reservation,
    Revision,
    Session,
    User,
    Wallet,
    emit,
    now,
    transaction,
    uid,
)
from .domain import (
    accessible_knowledge,
    create_session,
    evidence_valid,
    freeze_agent,
    owned_session,
    public_record,
    require_capacity,
    resource,
    revision_json,
    session_json,
    submit_chat,
    validate_agent,
    workspace_gate,
)
from .knowledge import enqueue_index
from .schemas import (
    RESOURCE_SCHEMAS,
    Chat,
    CreateAgent,
    CreateSession,
    Credentials,
    DocumentSpec,
    MemorySpec,
    Strict,
)
from .security import (
    Principal,
    admin,
    audit,
    bootstrap,
    check_password,
    current_user,
    encrypt,
    hash_password,
    login_attempt,
    operator,
    token_digest,
    valid_origin,
    validate_endpoint,
)


@asynccontextmanager
async def lifespan(app):
    await database.initialize()
    await bootstrap()
    yield
    await database.engine.dispose()


app = FastAPI(
    title="VP Agent Platform",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)


@app.middleware("http")
async def request_guard(request: Request, call_next):
    if not valid_origin(request):
        return Response("Origin not allowed", status_code=403)
    length = request.headers.get("content-length")
    if length and int(length) > 5_000_000:
        return Response("Request too large", status_code=413)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(ValueError)
async def invalid_value(request, exc):
    # Internal values may contain provider secrets. Public validation is handled separately.
    return Response(
        json.dumps({"detail": "Dữ liệu không hợp lệ"}),
        status_code=422,
        media_type="application/json",
    )


@app.get("/api/health")
async def health():
    async with transaction() as db:
        await db.execute(text("SELECT 1"))
    return {"status": "ok", "service": "vp-platform", "version": "0.1.0"}


class SignIn(Strict):
    email: str = Field(max_length=254)
    password: str = Field(max_length=256)


@app.post("/api/auth/login")
async def login(body: SignIn, request: Request, response: Response):
    await login_attempt((request.client.host if request.client else "unknown") + body.email.lower())
    async with transaction() as db:
        user = await db.scalar(select(User).where(User.email == body.email.lower().strip()))
        # Equalize the expensive part on unknown accounts.
        stored = user.password if user else hash_password("not-a-real-account-password")
        valid = await asyncio.to_thread(check_password, body.password, stored)
        if not user or user.disabled or not valid:
            raise HTTPException(401, "Email hoặc mật khẩu không đúng")
        token = secrets.token_urlsafe(48)
        db.add(
            Login(
                digest=token_digest(token),
                user_id=user.id,
                expires=now() + settings.session_hours * 3600,
            )
        )
        response.set_cookie(
            "vp_session",
            token,
            httponly=True,
            secure=settings.cookie_secure,
            samesite="strict",
            max_age=settings.session_hours * 3600,
            path="/",
        )
        return {"user_id": user.id}


@app.post("/api/auth/logout")
async def logout(request: Request, response: Response):
    async with transaction() as db:
        await db.execute(
            delete(Login).where(Login.digest == token_digest(request.cookies.get("vp_session", "")))
        )
    response.delete_cookie("vp_session", path="/")
    return {"ok": True}


@app.get("/api/me")
async def me(p=Depends(current_user)):
    async with transaction() as db:
        user = await db.get(User, p.user_id)
        memberships = (
            await db.scalars(select(Membership).where(Membership.user_id == p.user_id))
        ).all()
        return {
            "id": p.user_id,
            "email": user.email,
            "workspace": p.workspace,
            "role": p.role,
            "workspaces": [{"id": m.workspace, "role": m.role} for m in memberships],
        }


class MemberInput(Strict):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=256)
    role: Literal["admin", "operator", "viewer"]


@app.get("/api/members")
async def members(p=Depends(admin)):
    async with transaction() as db:
        rows = (
            await db.execute(
                select(User, Membership)
                .join(Membership, User.id == Membership.user_id)
                .where(Membership.workspace == p.workspace)
            )
        ).all()
        return [
            {"id": u.id, "email": u.email, "role": m.role, "disabled": u.disabled} for u, m in rows
        ]


@app.post("/api/members", status_code=201)
async def add_member(body: MemberInput, p=Depends(admin)):
    async with transaction() as db:
        user = await db.scalar(select(User).where(User.email == body.email.lower().strip()))
        if user:
            raise HTTPException(409, "Tài khoản đã tồn tại; quản lý membership qua ID")
        user = User(email=body.email.lower().strip(), password=hash_password(body.password))
        db.add(user)
        await db.flush()
        db.add(Membership(workspace=p.workspace, user_id=user.id, role=body.role))
        audit(db, p, "member.create", user.id, {"role": body.role})
        return {"id": user.id}


class MemberUpdate(Strict):
    role: Literal["admin", "operator", "viewer"]
    disabled: bool = False


@app.put("/api/members/{user_id}")
async def update_member(user_id: str, body: MemberUpdate, p=Depends(admin)):
    async with transaction() as db:
        await workspace_gate(db, p.workspace)
        member = await db.get(Membership, (p.workspace, user_id))
        user = await db.get(User, user_id)
        if not member or not user:
            raise HTTPException(404, "Không tìm thấy thành viên")
        if user_id == p.user_id and (body.role != "admin" or body.disabled):
            raise HTTPException(409, "Không tự hạ quyền/vô hiệu hoá quản trị viên đang dùng")
        member.role, user.disabled = body.role, body.disabled
        if body.disabled:
            await db.execute(delete(Login).where(Login.user_id == user_id))
        audit(db, p, "member.update", user_id, body.model_dump())
        return {"ok": True}


@app.get("/api/resources/{kind}")
async def list_resources(kind: str, p=Depends(current_user)):
    if kind not in {*RESOURCE_SCHEMAS, "credentials", "memory", "documents", "agents"}:
        raise HTTPException(404)
    async with transaction() as db:
        rows = (
            await db.scalars(
                select(Record)
                .where(Record.workspace == p.workspace, Record.kind == kind)
                .order_by(Record.created.desc())
            )
        ).all()
        result = []
        for row in rows:
            try:
                await resource(db, p, row.id)
                public = public_record(row)
                if kind == "documents":
                    public.pop("text", None)
                result.append(public)
            except HTTPException:
                pass
        return result


async def validate_resource(db, p, kind, body):
    schema = RESOURCE_SCHEMAS.get(kind)
    if not schema:
        raise HTTPException(404)
    try:
        spec = schema.model_validate(body).model_dump()
    except ValidationError as exc:
        raise HTTPException(422, exc.errors(include_input=False, include_context=False)) from None
    if kind in {"models", "embeddings", "mcp", "channels"} and p.role != "admin":
        raise HTTPException(403, "Kết nối/provider cần quyền quản trị")
    if spec.get("base_url") or kind == "mcp":
        await validate_endpoint(spec.get("base_url") or spec["url"])
    if spec.get("credential_id"):
        await resource(db, p, spec["credential_id"], "credentials")
    if (
        kind in {"models", "embeddings"}
        and spec["adapter"] != "ollama"
        and not spec["credential_id"]
    ):
        raise HTTPException(422, "Provider cần credential riêng")
    if kind == "models" and spec["context_tokens"] <= spec["max_output_tokens"]:
        raise HTTPException(422, "Context phải lớn hơn output limit")
    if kind == "knowledge" and spec["embedding_model_id"]:
        await resource(db, p, spec["embedding_model_id"], "embeddings")
    if kind in {"workflows", "channels"}:
        for aid in spec["agent_ids"]:
            await resource(db, p, aid, "agents")
    if kind == "schedules":
        await resource(db, p, spec["workflow_id"], "workflows")
        if not croniter.is_valid(spec["cron"]):
            raise HTTPException(422, "Cron không hợp lệ")
        ZoneInfo(spec["timezone"])
        spec["next_run"] = next_cron(spec)
    if kind == "channels":
        spec["token_hash"] = token_digest(spec.pop("token"))
    return spec


@app.post("/api/resources/{kind}", status_code=201)
async def add_resource(kind: str, body: dict, p=Depends(operator)):
    async with transaction() as db:
        spec = await validate_resource(db, p, kind, body)
        record = Record(id=uid(), workspace=p.workspace, owner=p.user_id, kind=kind, body=spec)
        db.add(record)
        await db.flush()
        audit(db, p, kind + ".create", record.id)
        return public_record(record)


class ResourceUpdate(Strict):
    version: int = Field(ge=1)
    spec: dict


@app.put("/api/resources/{kind}/{rid}")
async def update_resource(kind: str, rid: str, body: ResourceUpdate, p=Depends(operator)):
    async with transaction() as db:
        record = await resource(db, p, rid, kind, edit=True)
        await db.refresh(record, with_for_update=True)
        if record.version != body.version:
            raise HTTPException(409, "Tài nguyên đã thay đổi; tải lại trước khi lưu")
        spec = await validate_resource(db, p, kind, body.spec)
        # Models/embedding spaces are immutable identities; create another catalog entry.
        if kind in {"embeddings", "models"} and any(
            record.body[k] != spec[k] for k in ("adapter", "model", "base_url")
        ):
            raise HTTPException(409, "Tạo model mới khi đổi provider/model/endpoint")
        if kind == "embeddings" and record.body["dimensions"] != spec["dimensions"]:
            raise HTTPException(409, "Tạo embedding space mới khi đổi dimensions")
        record.body, record.version, record.updated = spec, record.version + 1, now()
        audit(db, p, kind + ".update", rid)
        return public_record(record)


@app.post("/api/credentials", status_code=201)
async def add_credential(body: Credentials, p=Depends(admin)):
    async with transaction() as db:
        record = Record(
            id=uid(),
            workspace=p.workspace,
            kind="credentials",
            owner=p.user_id,
            body={"name": body.name, "encrypted_secret": encrypt(body.secret)},
        )
        db.add(record)
        await db.flush()
        audit(db, p, "credential.create", record.id)
        return public_record(record)


@app.put("/api/credentials/{rid}")
async def rotate_credential(rid: str, body: Credentials, p=Depends(admin)):
    async with transaction() as db:
        record = await resource(db, p, rid, "credentials", edit=True)
        record.body = {"name": body.name, "encrypted_secret": encrypt(body.secret)}
        record.version += 1
        audit(db, p, "credential.rotate", rid)
        return public_record(record)


@app.post("/api/agents", status_code=201)
async def add_agent(body: CreateAgent, p=Depends(operator)):
    async with transaction() as db:
        spec = body.spec.model_dump()
        await validate_agent(db, p, spec)
        agent = Record(
            id=uid(),
            workspace=p.workspace,
            owner=p.user_id,
            kind="agents",
            body={"name": spec["name"], "published_revision": ""},
        )
        revision = Revision(
            id=uid(),
            workspace=p.workspace,
            agent_id=agent.id,
            number=1,
            body=await freeze_agent(db, spec),
        )
        db.add_all([agent, revision])
        await db.flush()
        audit(db, p, "agent.create", agent.id)
        return {"agent": public_record(agent), "revision": revision_json(revision)}


@app.get("/api/agents/{aid}/revisions")
async def revisions(aid: str, p=Depends(current_user)):
    async with transaction() as db:
        await resource(db, p, aid, "agents")
        rows = (
            await db.scalars(
                select(Revision).where(Revision.agent_id == aid).order_by(Revision.number.desc())
            )
        ).all()
        return [revision_json(row) for row in rows]


@app.post("/api/agents/{aid}/revisions", status_code=201)
async def new_revision(aid: str, body: CreateAgent, p=Depends(operator)):
    async with transaction() as db:
        agent = await resource(db, p, aid, "agents", edit=True)
        await db.refresh(agent, with_for_update=True)
        await validate_agent(db, p, body.spec.model_dump())
        number = (
            await db.scalar(select(func.max(Revision.number)).where(Revision.agent_id == aid))
        ) + 1
        revision = Revision(
            id=uid(),
            workspace=p.workspace,
            agent_id=aid,
            number=number,
            body=await freeze_agent(db, body.spec.model_dump()),
        )
        db.add(revision)
        await db.flush()
        audit(db, p, "revision.create", revision.id)
        return revision_json(revision)


@app.post("/api/agents/{aid}/revisions/{rid}/test")
async def test_revision(aid: str, rid: str, p=Depends(operator)):
    async with transaction() as db:
        await resource(db, p, aid, "agents", edit=True)
        revision = await db.get(Revision, rid)
        if not revision or revision.agent_id != aid:
            raise HTTPException(404)
        await validate_agent(db, p, revision.body)
        audit(db, p, "revision.policy_test", rid, {"passed": True, "provider_called": False})
        return {
            "passed": True,
            "scope": "policy_only",
            "provider_called": False,
            "checks": ["schema", "model_capabilities", "knowledge_acl", "tool_allowlist"],
        }


class ReleaseInput(Strict):
    action: Literal["publish", "retire"] = "publish"
    reason: str = Field(min_length=5, max_length=2000)


@app.post("/api/agents/{aid}/revisions/{rid}/release")
async def release(aid: str, rid: str, body: ReleaseInput, p=Depends(admin)):
    async with transaction() as db:
        agent = await resource(db, p, aid, "agents", edit=True)
        await db.refresh(agent, with_for_update=True)
        revision = await db.get(Revision, rid)
        if not revision or revision.agent_id != aid:
            raise HTTPException(404)
        if body.action == "publish":
            await validate_agent(db, p, revision.body)
            checked = await db.scalar(
                select(Audit.id).where(
                    Audit.workspace == p.workspace,
                    Audit.target == rid,
                    Audit.action == "revision.policy_test",
                )
            )
            if not checked:
                raise HTTPException(
                    409, "Chạy policy test trước khi công bố; eval thực tế vẫn cần riêng"
                )
            agent.body = {"name": revision.body["name"], "published_revision": rid}
            revision.status = "published"
        else:
            revision.status = "retired"
            if agent.body.get("published_revision") == rid:
                agent.body = {**agent.body, "published_revision": ""}
        audit(db, p, "revision." + body.action, rid, {"reason": body.reason})
        return revision_json(revision)


@app.post("/api/sessions", status_code=201)
async def add_session(body: CreateSession, p=Depends(operator)):
    async with transaction() as db:
        session = await create_session(db, p, body.title, body.agent_ids, body.budget_micros)
        return session_json(session)


@app.get("/api/sessions")
async def sessions(p=Depends(current_user)):
    async with transaction() as db:
        query = select(Session).where(Session.workspace == p.workspace)
        if p.role != "admin":
            query = query.where(Session.owner == p.user_id)
        rows = (await db.scalars(query.order_by(Session.updated.desc()).limit(100))).all()
        return [session_json(row) for row in rows]


@app.get("/api/sessions/{sid}")
async def get_session(sid: str, p=Depends(current_user)):
    async with transaction() as db:
        return session_json(await owned_session(db, p, sid))


@app.post("/api/sessions/{sid}/chat", status_code=202)
async def chat(sid: str, body: Chat, p=Depends(operator)):
    async with transaction() as db:
        result = await submit_chat(db, p, sid, body.text, body.idempotency_key)
    from .signals import wake

    await wake()
    return result


@app.get("/api/sessions/{sid}/events")
async def event_page(sid: str, after: int = 0, p=Depends(current_user)):
    async with transaction() as db:
        await owned_session(db, p, sid)
        rows = (
            await db.scalars(
                select(Event)
                .where(Event.session_id == sid, Event.seq > after)
                .order_by(Event.seq)
                .limit(500)
            )
        ).all()
        return [{"seq": e.seq, "type": e.type, "body": e.body, "created": e.created} for e in rows]


@app.get("/api/sessions/{sid}/stream")
async def stream(sid: str, request: Request, after: int = 0, p=Depends(current_user)):
    try:
        cursor = max(after, int(request.headers.get("last-event-id", "0")))
    except ValueError:
        raise HTTPException(422, "Cursor không hợp lệ") from None
    async with transaction() as db:
        await owned_session(db, p, sid)

    async def generate():
        nonlocal cursor
        while not await request.is_disconnected():
            # Recheck login/membership on every page; replay and live use the same durable log.
            try:
                principal = await current_user(request)
                page = await event_page(sid, cursor, principal)
            except HTTPException:
                return
            for event in page:
                cursor = event["seq"]
                yield f"id: {cursor}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
            if not page:
                yield ": heartbeat\n\n"
                await asyncio.sleep(0.75)

    return StreamingResponse(
        generate(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"}
    )


@app.get("/api/sessions/{sid}/artifacts")
async def artifacts(sid: str, kind: str = "", p=Depends(current_user)):
    async with transaction() as db:
        await owned_session(db, p, sid)
        query = select(Artifact).where(Artifact.session_id == sid)
        if kind:
            query = query.where(Artifact.kind == kind)
        rows = (await db.scalars(query.order_by(Artifact.created).limit(1000))).all()
        return [
            {
                "id": a.id,
                "kind": a.kind,
                "agent_id": a.agent_id,
                "turn": a.turn,
                "created": a.created,
                "body": {k: v for k, v in a.body.items() if k != "state"},
            }
            for a in rows
        ]


@app.post("/api/sessions/{sid}/cancel")
async def cancel_session(sid: str, p=Depends(operator)):
    async with transaction() as db:
        session = await owned_session(db, p, sid, lock=True)
        session.status = "cancelled"
        jobs = (
            await db.scalars(
                select(Job)
                .where(Job.session_id == sid, Job.status.in_(["running", "queued"]))
                .with_for_update()
            )
        ).all()
        for job in jobs:
            job.generation += 1
            job.status = "cancelled"
        await emit(db, session, "session.cancelled", {})
        audit(db, p, "session.cancel", sid)
        return session_json(session)


class BudgetInput(Strict):
    budget_micros: int = Field(ge=1, le=10000000000)


@app.put("/api/sessions/{sid}/budget")
async def session_budget(sid: str, body: BudgetInput, p=Depends(admin)):
    async with transaction() as db:
        session = await owned_session(db, p, sid, lock=True)
        if body.budget_micros < session.spent + session.reserved:
            raise HTTPException(409, "Ngân sách thấp hơn số đã dùng/đã giữ")
        session.budget = body.budget_micros
        audit(db, p, "session.budget", sid, body.model_dump())
        return session_json(session)


@app.post("/api/knowledge/{kid}/documents", status_code=201)
async def add_document(kid: str, body: DocumentSpec, p=Depends(operator)):
    async with transaction() as db:
        kb = await resource(db, p, kid, "knowledge", edit=True)
        document = Record(
            id=uid(),
            workspace=p.workspace,
            owner=p.user_id,
            kind="documents",
            body={**body.model_dump(), "knowledge_id": kid, "revoked": False},
        )
        db.add(document)
        await db.flush()
        sid = await enqueue_index(db, p, kb, document)
        audit(db, p, "document.create", document.id)
        return {"id": document.id, "index_session_id": sid, "status": "queued"}


@app.post("/api/knowledge/{kid}/upload", status_code=201)
async def upload_document(kid: str, file: UploadFile, p=Depends(operator)):
    raw = await file.read(4_000_001)
    if len(raw) > 4_000_000:
        raise HTTPException(413, "Tệp tối đa 4 MB")
    filename = file.filename or "document.txt"
    if filename.lower().endswith(".pdf"):
        from pypdf import PdfReader

        value = await asyncio.to_thread(
            lambda: "\n".join(
                page.extract_text() or "" for page in PdfReader(io.BytesIO(raw)).pages
            )
        )
    elif filename.lower().endswith((".md", ".txt", ".csv")):
        value = raw.decode("utf-8-sig")
    else:
        raise HTTPException(422, "Chấp nhận PDF, TXT, MD, CSV UTF-8")
    return await add_document(
        kid, DocumentSpec(title=filename[:200], text=value, source="upload:" + filename), p
    )


@app.delete("/api/documents/{rid}")
async def revoke_document(rid: str, p=Depends(operator)):
    async with transaction() as db:
        document = await resource(db, p, rid, "documents", edit=True)
        document.body = {**document.body, "revoked": True, "text": ""}
        rows = (
            await db.scalars(
                select(Record).where(Record.workspace == p.workspace, Record.kind == "chunks")
            )
        ).all()
        for row in rows:
            if row.body["document_id"] == rid:
                await db.delete(row)
        audit(db, p, "document.revoke", rid)
        return {"revoked": True, "note": "Audit/session evidence retained; source invalidated"}


@app.get("/api/knowledge/{kid}/search")
async def search_knowledge(kid: str, q: str, p=Depends(current_user)):
    async with transaction() as db:
        await accessible_knowledge(db, p, kid)
        return await lexical_search(db, p.workspace, p.user_id, [kid], q[:2000])


@app.post("/api/memory", status_code=201)
async def add_memory(body: MemorySpec, p=Depends(operator)):
    async with transaction() as db:
        session = await owned_session(db, p, body.session_id)
        if body.agent_id not in {m["agent_id"] for m in session.team}:
            raise HTTPException(422, "Agent không thuộc session nguồn")
        if not all([await evidence_valid(db, session, eid) for eid in body.evidence_ids]):
            raise HTTPException(422, "Memory cần bằng chứng có nguồn còn hiệu lực")
        record = Record(
            id=uid(),
            workspace=p.workspace,
            owner=session.owner,
            kind="memory",
            body={**body.model_dump(), "status": "candidate"},
        )
        db.add(record)
        await db.flush()
        audit(db, p, "memory.candidate", record.id)
        return public_record(record)


@app.post("/api/memory/{rid}/verify")
async def verify_memory(rid: str, p=Depends(admin)):
    async with transaction() as db:
        memory = await resource(db, p, rid, "memory", edit=True)
        session = await owned_session(db, p, memory.body["session_id"])
        if not all([await evidence_valid(db, session, eid) for eid in memory.body["evidence_ids"]]):
            raise HTTPException(422, "Bằng chứng memory đã mất hiệu lực")
        memory.body = {
            **memory.body,
            "status": "verified",
            "verified_by": p.user_id,
            "verified_at": now(),
        }
        audit(db, p, "memory.verify", rid)
        return public_record(memory)


@app.delete("/api/memory/{rid}")
async def delete_memory(rid: str, p=Depends(operator)):
    async with transaction() as db:
        memory = await resource(db, p, rid, "memory", edit=True)
        await db.delete(memory)
        audit(db, p, "memory.delete", rid)
        return {"deleted": True}


class ApprovalInput(Strict):
    approve: bool
    reason: str = Field(min_length=5, max_length=2000)


@app.post("/api/sessions/{sid}/approvals/{execution_id}")
async def approve_tool(sid: str, execution_id: str, body: ApprovalInput, p=Depends(admin)):
    async with transaction() as db:
        await workspace_gate(db, p.workspace)
        if body.approve:
            await require_capacity(db, p.workspace)
        session = await owned_session(db, p, sid, lock=True)
        execution = await db.get(Artifact, execution_id)
        if not execution or execution.session_id != sid or execution.kind != "tool_execution":
            raise HTTPException(404)
        if execution.body["status"] != "pending" or session.status != "awaiting_approval":
            raise HTTPException(409, "Yêu cầu đã xử lý hoặc session không chờ duyệt")
        execution.body = {
            **execution.body,
            "status": "approved" if body.approve else "rejected",
            "approved_by": p.user_id,
            "reason": body.reason,
        }
        if body.approve:
            session.status = "running"
            db.add(
                Job(
                    id=uid(),
                    workspace=p.workspace,
                    session_id=sid,
                    dedupe="approval:" + execution_id,
                    body={
                        "turn": session.turn,
                        "agent_id": execution.agent_id,
                        "phase": "external",
                        "round": 0,
                        "execution_id": execution_id,
                    },
                )
            )
        else:
            session.status = "needs_input"
        await emit(
            db,
            session,
            "approval.decided",
            {"execution_id": execution_id, "approved": body.approve},
        )
        audit(db, p, "tool.approval", execution_id, body.model_dump())
        return {"ok": True}


@app.post("/api/workflows/{rid}/run", status_code=202)
async def run_workflow(rid: str, p=Depends(operator)):
    async with transaction() as db:
        workflow = await resource(db, p, rid, "workflows")
        session = await start_workflow(db, p, workflow)
        return session_json(session)


@app.post("/api/sessions/{sid}/workflow-gate")
async def workflow_gate(sid: str, body: ApprovalInput, p=Depends(operator)):
    async with transaction() as db:
        await workspace_gate(db, p.workspace)
        if body.approve:
            await require_capacity(db, p.workspace)
        session = await owned_session(db, p, sid, lock=True)
        flow = session.board.get("workflow", {})
        if flow.get("status") != "awaiting_gate":
            raise HTTPException(409, "Workflow không chờ duyệt")
        if body.approve:
            await continue_workflow(db, session)
        else:
            session.status = "cancelled"
            session.board = {**session.board, "workflow": {**flow, "status": "rejected"}}
        audit(db, p, "workflow.gate", sid, body.model_dump())
        return session_json(session)


@app.post("/api/channels/{rid}/messages", status_code=202)
async def channel_message(rid: str, body: Chat, request: Request):
    # Explicit integration identity; token maps to a fixed owner/workspace/team.
    token = request.headers.get("authorization", "").removeprefix("Bearer ")
    async with transaction() as db:
        channel = await db.get(Record, rid)
        if (
            not channel
            or channel.kind != "channels"
            or not channel.body["enabled"]
            or not secrets.compare_digest(channel.body["token_hash"], token_digest(token))
        ):
            raise HTTPException(401, "Channel token không hợp lệ")
        user = await db.get(User, channel.owner)
        member = await db.get(Membership, (channel.workspace, channel.owner))
        if not user or user.disabled or not member or member.role == "viewer":
            raise HTTPException(403)
        p = Principal(user.id, channel.workspace, member.role)
        await workspace_gate(db, p.workspace)
        existing = await db.scalar(
            select(Record).where(
                Record.workspace == p.workspace,
                Record.kind == "channel_delivery",
                Record.id == token_digest(rid + body.idempotency_key)[:36],
            )
        )
        if existing:
            if existing.body.get("request_hash") != token_digest(body.text):
                raise HTTPException(409, "Idempotency key đã dùng cho nội dung khác")
            return {"session_id": existing.body["session_id"]}
        session = await create_session(
            db, p, channel.body["name"], channel.body["agent_ids"], settings.session_budget_micros
        )
        await submit_chat(db, p, session.id, body.text, body.idempotency_key)
        result = {"session_id": session.id}
        db.add(
            Record(
                id=token_digest(rid + body.idempotency_key)[:36],
                workspace=p.workspace,
                owner=p.user_id,
                kind="channel_delivery",
                body={**result, "request_hash": token_digest(body.text)},
            )
        )
        return result


@app.get("/api/operations")
async def operations(p=Depends(admin)):
    async with transaction() as db:
        jobs = (
            await db.scalars(
                select(Job)
                .where(Job.workspace == p.workspace)
                .order_by(Job.created.desc())
                .limit(200)
            )
        ).all()
        usage = (
            await db.scalars(
                select(Reservation)
                .where(Reservation.workspace == p.workspace)
                .order_by(Reservation.created.desc())
                .limit(200)
            )
        ).all()
        logs = (
            await db.scalars(
                select(Audit)
                .where(Audit.workspace == p.workspace)
                .order_by(Audit.created.desc())
                .limit(100)
            )
        ).all()
        month = datetime.now(UTC).strftime("%Y-%m")
        wallet = await db.get(Wallet, (p.workspace, month))
        return {
            "jobs": [
                {
                    k: getattr(j, k)
                    for k in (
                        "id",
                        "session_id",
                        "kind",
                        "status",
                        "attempts",
                        "generation",
                        "lease_until",
                        "error",
                    )
                }
                for j in jobs
            ],
            "usage": [
                {
                    k: getattr(r, k)
                    for k in ("id", "session_id", "amount", "charged", "status", "usage", "created")
                }
                for r in usage
            ],
            "audit": [
                {k: getattr(a, k) for k in ("id", "actor", "action", "target", "body", "created")}
                for a in logs
            ],
            "wallet": {
                "month": month,
                "budget": wallet.budget if wallet else settings.monthly_budget_micros,
                "spent": wallet.spent if wallet else 0,
                "reserved": wallet.reserved if wallet else 0,
            },
            "limits": {
                "sessions": settings.max_sessions,
                "workers": settings.workers,
                "participants": settings.max_participants,
                "debate_rounds": settings.max_debate_rounds,
                "jev_enabled": settings.jev_enabled,
            },
            "workers": [
                {
                    "id": row.id,
                    **row.body,
                    "last_seen": row.updated,
                    "healthy": row.updated > now() - 30,
                }
                for row in (await db.scalars(select(Record).where(Record.kind == "worker"))).all()
            ],
        }


@app.post("/api/operations/jobs/{job_id}/retry")
async def retry_job(job_id: str, p=Depends(admin)):
    from .domain import authorize_execution
    from .runtime import SafeRuntimeError

    async with transaction() as db:
        await workspace_gate(db, p.workspace)
        job = await db.get(Job, job_id)
        if not job or job.workspace != p.workspace:
            raise HTTPException(404)
        session = await owned_session(db, p, job.session_id, lock=True)
        await db.refresh(job, with_for_update=True)
        if (
            job.status != "failed"
            or job.kind != "agent"
            or job.body.get("phase") not in {"plan", "work", "debate", "verify"}
            or job.error not in {"provider_error", "agent_incomplete", "budget_exhausted"}
            or session.status not in {"needs_review", "budget_exhausted"}
            or job.body["turn"] != session.turn
        ):
            raise HTTPException(
                409, "Job không thể chạy lại an toàn; tạo lượt mới sau khi kiểm tra"
            )
        effects = (
            await db.scalars(
                select(Artifact).where(
                    Artifact.session_id == session.id,
                    Artifact.kind == "tool_execution",
                    Artifact.turn == session.turn,
                )
            )
        ).all()
        if any(not row.body.get("read_only") for row in effects):
            raise HTTPException(409, "Có tool cần đối soát; không tự chạy lại lượt có tác động")
        try:
            await authorize_execution(db, session)
        except SafeRuntimeError:
            raise HTTPException(409, "Chủ session không còn quyền thực thi") from None
        await require_capacity(db, p.workspace)
        session.status = "running"
        job.status, job.error, job.attempts, job.available = "queued", "", 0, now()
        await emit(db, session, "task.retry_requested", {"task_id": job.id})
        audit(db, p, "task.retry", job.id, {"prior_generation": job.generation})
        return {"ok": True}


@app.put("/api/operations/budget")
async def workspace_budget(body: BudgetInput, p=Depends(admin)):
    from .limits import insert_for

    month = datetime.now(UTC).strftime("%Y-%m")
    async with transaction() as db:
        await db.execute(
            insert_for(db, Wallet)
            .values(
                workspace=p.workspace, month=month, budget=body.budget_micros, spent=0, reserved=0
            )
            .on_conflict_do_nothing()
        )
        wallet = await db.scalar(
            select(Wallet)
            .where(Wallet.workspace == p.workspace, Wallet.month == month)
            .with_for_update()
        )
        if wallet.spent + wallet.reserved > body.budget_micros:
            raise HTTPException(409, "Thấp hơn chi phí đã dùng/giữ")
        wallet.budget = body.budget_micros
        audit(db, p, "workspace.budget", month, body.model_dump())
        return {"ok": True}


class EvaluationCase(Strict):
    prompt: str = Field(min_length=1, max_length=12000)
    expected_status: Literal["complete", "needs_input", "needs_review", "blocked"]
    must_contain: list[str] = Field(default_factory=list, max_length=20)
    must_not_contain: list[str] = Field(default_factory=list, max_length=20)
    require_sources: bool = True


class EvaluationInput(Strict):
    name: str = Field(min_length=1, max_length=100)
    agent_ids: list[str] = Field(min_length=1, max_length=3)
    cases: list[EvaluationCase] = Field(min_length=1, max_length=20)


@app.post("/api/evaluations", status_code=202)
async def run_evaluation(body: EvaluationInput, p=Depends(operator)):
    async with transaction() as db:
        await workspace_gate(db, p.workspace)
        run = Record(
            id=uid(),
            workspace=p.workspace,
            owner=p.user_id,
            kind="evaluations",
            body={**body.model_dump(), "status": "running", "results": {}},
        )
        db.add(run)
        await db.flush()
        ids = []
        for index, case in enumerate(body.cases):
            session = await create_session(
                db, p, body.name + f" #{index + 1}", body.agent_ids, settings.session_budget_micros
            )
            session.board = {**session.board, "evaluation": {"run_id": run.id, "case": index}}
            await submit_chat(db, p, session.id, case.prompt, "evaluation-start")
            ids.append(session.id)
        run.body = {**run.body, "session_ids": ids}
        audit(db, p, "evaluation.run", run.id, {"case_count": len(ids)})
        return public_record(run)


@app.get("/api/evaluations")
async def list_evaluations(p=Depends(current_user)):
    async with transaction() as db:
        query = select(Record).where(Record.workspace == p.workspace, Record.kind == "evaluations")
        if p.role != "admin":
            query = query.where(Record.owner == p.user_id)
        return [
            public_record(row)
            for row in (await db.scalars(query.order_by(Record.created.desc()))).all()
        ]


class JevInput(Strict):
    synthetic_state: dict
    synthetic_only: Literal[True]
    expected: Literal["tool", "clarify", "answer"]


@app.post("/api/experiments/jev", status_code=202)
async def jev_shadow(body: JevInput, p=Depends(admin)):
    if not settings.jev_enabled:
        raise HTTPException(409, "Jev tắt mặc định; bật rõ ràng trong cấu hình thử nghiệm")
    if len(json.dumps(body.synthetic_state)) > 8000:
        raise HTTPException(422, "Dữ liệu thử tối đa 8000 ký tự, chỉ dữ liệu giả/ẩn danh")
    async with transaction() as db:
        await workspace_gate(db, p.workspace)
        await require_capacity(db, p.workspace)
        session = Session(
            id=uid(),
            workspace=p.workspace,
            owner=p.user_id,
            title="Jev shadow",
            status="running",
            team=[],
            turn=1,
            budget=settings.session_budget_micros,
            board={"experiment": "jev-shadow"},
        )
        db.add(session)
        db.add(
            Job(
                id=uid(),
                workspace=p.workspace,
                session_id=session.id,
                dedupe="jev:" + session.id,
                body={"turn": 1, "phase": "jev_shadow", **body.model_dump()},
            )
        )
        audit(db, p, "jev.shadow", session.id)
        return session_json(session)
