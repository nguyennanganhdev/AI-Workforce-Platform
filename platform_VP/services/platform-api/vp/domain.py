"""Workspace ACLs and execution state transitions shared by HTTP and workers."""

import hashlib
import json

from fastapi import HTTPException
from sqlalchemy import func, select

from .config import settings
from .db import Artifact, Job, Record, Revision, Session, emit, now, uid
from .security import Principal, audit


def public_record(record: Record) -> dict:
    body = {k: v for k, v in record.body.items() if k not in {"encrypted_secret", "token_hash"}}
    if record.kind in {"credentials", "channels"}:
        body["configured"] = bool(
            record.body.get("encrypted_secret") or record.body.get("token_hash")
        )
    return {
        "id": record.id,
        "kind": record.kind,
        "owner": record.owner,
        "version": record.version,
        "created": record.created,
        "updated": record.updated,
        **body,
    }


def revision_json(revision: Revision) -> dict:
    return {
        "id": revision.id,
        "agent_id": revision.agent_id,
        "number": revision.number,
        "status": revision.status,
        "created": revision.created,
        "spec": revision.body,
    }


def session_json(session: Session) -> dict:
    return {
        key: getattr(session, key)
        for key in (
            "id",
            "workspace",
            "owner",
            "title",
            "status",
            "team",
            "board",
            "seq",
            "turn",
            "budget",
            "spent",
            "reserved",
            "created",
            "updated",
        )
    }


async def resource(db, p: Principal, rid: str, kind: str | None = None, edit=False) -> Record:
    record = await db.get(Record, rid)
    if record is None or record.workspace != p.workspace or (kind and record.kind != kind):
        raise HTTPException(404, "Không tìm thấy tài nguyên")
    private = record.kind in {"memory", "documents", "chunks"} or (
        record.kind == "knowledge" and record.body.get("visibility") == "private"
    )
    # Administrator can govern private data; other users cannot acquire it by ID.
    if (edit or private) and record.owner != p.user_id and p.role != "admin":
        raise HTTPException(403, "Tài nguyên thuộc người dùng khác")
    return record


async def accessible_knowledge(db, p: Principal, kid: str) -> Record:
    return await resource(db, p, kid, "knowledge")


async def owned_session(db, p: Principal, sid: str, lock=False) -> Session:
    query = select(Session).where(Session.id == sid)
    if lock:
        query = query.with_for_update()
    session = await db.scalar(query)
    if session is None or session.workspace != p.workspace:
        raise HTTPException(404, "Không tìm thấy session")
    if session.owner != p.user_id and p.role != "admin":
        raise HTTPException(403, "Session thuộc người dùng khác")
    return session


async def workspace_gate(db, workspace: str):
    from .limits import insert_for

    key = hashlib.sha256(("workspace:" + workspace).encode()).hexdigest()[:36]
    await db.execute(
        insert_for(db, Record)
        .values(
            id=key,
            workspace=workspace,
            kind="workspace",
            owner="system",
            version=1,
            body={},
            created=now(),
            updated=now(),
        )
        .on_conflict_do_nothing()
    )
    return await db.scalar(select(Record).where(Record.id == key).with_for_update())


async def require_capacity(db, workspace):
    active = await db.scalar(
        select(func.count())
        .select_from(Session)
        .where(
            Session.workspace == workspace,
            Session.status == "running",
        )
    )
    if active >= settings.max_sessions:
        raise HTTPException(429, "Đã đạt giới hạn session hoạt động")


async def authorize_execution(db, session):
    from .db import Membership, User
    from .runtime import SafeRuntimeError

    user = await db.get(User, session.owner)
    member = await db.get(Membership, (session.workspace, session.owner))
    if not user or user.disabled or not member or member.role not in {"admin", "operator"}:
        raise SafeRuntimeError("owner_access_revoked")


async def validate_agent(db, p: Principal, spec: dict):
    primary = await resource(db, p, spec["model_id"], "models")
    for mid in [spec["model_id"], *spec["fallback_model_ids"]]:
        model = await resource(db, p, mid, "models")
        if not model.body["enabled"] or not {"tools", "json"}.issubset(model.body["capabilities"]):
            raise HTTPException(422, "Model cần bật và hỗ trợ tools + JSON")
        if not set(primary.body["capabilities"]).issubset(model.body["capabilities"]):
            raise HTTPException(422, "Fallback thiếu capability của model chính")
    for kid in spec["knowledge_ids"]:
        await accessible_knowledge(db, p, kid)
    for key, kind in [("mcp_ids", "mcp"), ("skill_ids", "skills")]:
        for rid in spec[key]:
            await resource(db, p, rid, kind)


async def freeze_agent(db, spec):
    models = {}
    for mid in [spec["model_id"], *spec["fallback_model_ids"]]:
        row = await db.get(Record, mid)
        models[mid] = {"id": mid, "version": row.version, **row.body}
    skills = []
    for rid in spec["skill_ids"]:
        row = await db.get(Record, rid)
        skills.append({"id": rid, "version": row.version, **row.body})
    return {**spec, "model_snapshots": models, "skill_snapshots": skills}


async def create_session(
    db, p: Principal, title: str, agent_ids: list[str], budget: int
) -> Session:
    if len(set(agent_ids)) != len(agent_ids) or len(agent_ids) > settings.max_participants:
        raise HTTPException(422, "Team phải gồm các agent khác nhau, tối đa 3 thành viên")
    team = []
    for index, aid in enumerate(agent_ids):
        agent = await resource(db, p, aid, "agents")
        revision = await db.get(Revision, agent.body.get("published_revision", ""))
        if revision is None or revision.status != "published":
            raise HTTPException(422, "Agent chưa có revision được công bố")
        await validate_agent(db, p, revision.body)
        team.append(
            {
                "agent_id": aid,
                "revision_id": revision.id,
                "name": revision.body["name"],
                "role": "coordinator" if index == 0 else "specialist",
            }
        )
    session = Session(
        id=uid(),
        workspace=p.workspace,
        owner=p.user_id,
        title=title,
        team=team,
        budget=budget,
        board={"goal": "", "decisions": [], "unknowns": [], "tasks": []},
    )
    db.add(session)
    await db.flush()
    await emit(db, session, "session.created", {"team": team})
    audit(db, p, "session.create", session.id)
    return session


async def queue_agent(
    db, session: Session, agent_id: str, phase: str, round_no=0, trigger="", dependencies=None
) -> Job:
    key = f"{session.id}:{session.turn}:{agent_id}:{phase}:{round_no}:{trigger}"
    existing = await db.scalar(select(Job).where(Job.dedupe == key))
    if existing:
        return existing
    job = Job(
        id=uid(),
        workspace=session.workspace,
        session_id=session.id,
        dedupe=key,
        body={
            "agent_id": agent_id,
            "turn": session.turn,
            "phase": phase,
            "round": round_no,
            "basis_seq": session.seq,
            "dependencies": dependencies or [],
        },
    )
    db.add(job)
    db.add(
        Artifact(
            workspace=session.workspace,
            session_id=session.id,
            kind="task",
            id=job.id,
            agent_id=agent_id,
            turn=session.turn,
            body={
                "status": "queued",
                "phase": phase,
                "round": round_no,
                "depends_on": dependencies or [],
                "owner": agent_id,
            },
        )
    )
    await emit(
        db,
        session,
        "task.queued",
        {"task_id": job.id, "agent_id": agent_id, "phase": phase, "round": round_no},
    )
    return job


async def submit_chat(db, p: Principal, sid: str, text: str, key: str) -> dict:
    await workspace_gate(db, p.workspace)
    session = await owned_session(db, p, sid, lock=True)
    previous = await db.scalar(
        select(Artifact).where(
            Artifact.session_id == sid,
            Artifact.kind == "user_message",
            Artifact.id == hashlib.sha256((sid + key).encode()).hexdigest()[:36],
        )
    )
    if previous:
        if previous.body["text"] != text:
            raise HTTPException(409, "Idempotency key đã dùng cho nội dung khác")
        return {"accepted": True, "turn": previous.turn, "duplicate": True}
    if session.status in {"running", "awaiting_approval"}:
        raise HTTPException(409, "Session đang chạy hoặc chờ duyệt")
    active = await db.scalar(
        select(func.count())
        .select_from(Session)
        .where(
            Session.workspace == p.workspace,
            Session.status == "running",
        )
    )
    if active >= settings.max_sessions:
        raise HTTPException(429, "Đã đạt giới hạn 20 session hoạt động")
    if session.spent + session.reserved >= session.budget:
        raise HTTPException(409, "Ngân sách session đã hết")
    session.turn += 1
    session.status = "running"
    session.board = {**session.board, "goal": text, "unknowns": []}
    db.add(
        Artifact(
            id=hashlib.sha256((sid + key).encode()).hexdigest()[:36],
            workspace=p.workspace,
            session_id=sid,
            kind="user_message",
            turn=session.turn,
            body={"text": text, "sender": p.user_id},
        )
    )
    await emit(db, session, "chat.user", {"text": text, "turn": session.turn})
    await queue_agent(db, session, session.team[0]["agent_id"], "plan")
    audit(db, p, "chat.submit", sid)
    return {"accepted": True, "turn": session.turn, "duplicate": False}


async def evidence_valid(db, session: Session, evidence_id: str) -> bool:
    evidence = await db.get(Artifact, evidence_id)
    if evidence is None or evidence.session_id != session.id or evidence.kind != "evidence":
        return False
    if evidence.body.get("expires") and evidence.body["expires"] <= now():
        return False
    document_id = evidence.body.get("document_id")
    if document_id:
        document = await db.get(Record, document_id)
        if document is None or document.body.get("revoked"):
            return False
        if document.body.get("expires") and document.body["expires"] <= now():
            return False
        kb = await db.get(Record, document.body["knowledge_id"])
        if not kb or kb.workspace != session.workspace:
            return False
        if kb.body["visibility"] == "private" and kb.owner != session.owner:
            return False
    return evidence.body.get("verified", False)


def stable_hash(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
