import json
import re

from sqlalchemy import select

from .db import Artifact, Record, Session, now
from .domain import evidence_valid


def terms(text: str) -> set[str]:
    return set(re.findall(r"[\wÀ-ỹ]{2,}", text.lower()))


def sanitize_state(value):
    """Keep operational state, omit private reasoning text from persisted snapshots."""
    if isinstance(value, list):
        return [
            sanitize_state(x)
            for x in value
            if not isinstance(x, dict) or x.get("type") != "thinking"
        ]
    if isinstance(value, dict):
        return {
            k: sanitize_state(v)
            for k, v in value.items()
            if k not in {"api_key", "secret", "thinking", "encrypted_secret"}
        }
    return value


async def lexical_search(
    db, workspace: str, owner: str, knowledge_ids: list[str], query: str, limit=6
) -> list[dict]:
    candidates = (
        await db.scalars(
            select(Record).where(
                Record.workspace == workspace,
                Record.kind == "chunks",
            )
        )
    ).all()
    wanted = terms(query)
    scored = []
    for chunk in candidates:
        if chunk.body["knowledge_id"] not in knowledge_ids:
            continue
        kb = await db.get(Record, chunk.body["knowledge_id"])
        doc = await db.get(Record, chunk.body["document_id"])
        if not kb or (kb.body["visibility"] == "private" and kb.owner != owner):
            continue
        if not doc or doc.body.get("revoked"):
            continue
        if doc.body.get("expires") and doc.body["expires"] <= now():
            continue
        score = len(wanted & terms(chunk.body["text"]))
        if score:
            scored.append((score, chunk))
    scored.sort(key=lambda item: (-item[0], item[1].id))
    return [{"chunk_id": chunk.id, **chunk.body} for _, chunk in scored[:limit]]


async def attach_evidence(db, session: Session, agent_id: str, chunks: list[dict]) -> list[dict]:
    result = []
    for chunk in chunks:
        # Stable per-session document chunk, retries don't multiply evidence.
        import hashlib

        eid = hashlib.sha256((session.id + chunk["chunk_id"]).encode()).hexdigest()[:36]
        evidence = await db.get(Artifact, eid)
        if not evidence:
            evidence = Artifact(
                id=eid,
                workspace=session.workspace,
                session_id=session.id,
                kind="evidence",
                agent_id=agent_id,
                turn=session.turn,
                body={
                    "document_id": chunk["document_id"],
                    "knowledge_id": chunk["knowledge_id"],
                    "chunk_id": chunk["chunk_id"],
                    "source": chunk["source"],
                    "text": chunk["text"],
                    "verified": True,
                    "verification": "document_provenance_only",
                    "expires": chunk.get("expires"),
                },
            )
            db.add(evidence)
        result.append({"id": eid, **evidence.body})
    return result


async def build_context(db, session: Session, job, spec: dict) -> tuple[dict, list[str]]:
    artifacts = (
        await db.scalars(
            select(Artifact)
            .where(
                Artifact.session_id == session.id,
            )
            .order_by(Artifact.created, Artifact.id)
        )
    ).all()
    inbox = [
        a
        for a in artifacts
        if a.kind == "message"
        and a.turn == session.turn
        and a.body["recipient"] in {job.body["agent_id"], "*"}
    ]
    results = [a for a in artifacts if a.kind == "result" and a.turn == session.turn]
    tasks = [a for a in artifacts if a.kind == "task" and a.turn == session.turn]
    current_goal = session.board.get("goal", "")
    chunks = await lexical_search(
        db, session.workspace, session.owner, spec["knowledge_ids"], current_goal
    )
    evidence = await attach_evidence(db, session, job.body["agent_id"], chunks)
    present = {item["id"] for item in evidence}
    for artifact in artifacts:
        if artifact.kind != "evidence" or artifact.id in present:
            continue
        if (
            artifact.body.get("knowledge_id")
            and artifact.body["knowledge_id"] not in spec["knowledge_ids"]
        ):
            continue
        if await evidence_valid(db, session, artifact.id):
            evidence.append({"id": artifact.id, **artifact.body})
            present.add(artifact.id)
    evidence = evidence[-12:]
    memories = []
    if spec["memory_policy"] == "verified_private":
        rows = (
            await db.scalars(
                select(Record).where(
                    Record.workspace == session.workspace,
                    Record.kind == "memory",
                    Record.owner == session.owner,
                )
            )
        ).all()
        for row in rows:
            b = row.body
            if b["agent_id"] != job.body["agent_id"] or b["status"] != "verified":
                continue
            if b.get("expires") and b["expires"] <= now():
                continue
            origin = await db.get(Session, b["session_id"])
            if not origin or origin.owner != session.owner:
                continue
            if not all([await evidence_valid(db, origin, eid) for eid in b["evidence_ids"]]):
                continue
            memories.append({"id": row.id, "text": b["text"], "evidence_ids": b["evidence_ids"]})
    payload = {
        "basis_seq": session.seq,
        "turn": session.turn,
        "goal": current_goal,
        "phase": job.body["phase"],
        "round": job.body["round"],
        "you": next(
            member for member in session.team if member["agent_id"] == job.body["agent_id"]
        ),
        "team": session.team,
        "board": {**session.board, "tasks": [{"id": a.id, **a.body} for a in tasks]},
        "prior_turns": [
            {"turn": a.turn, "kind": a.kind, "body": a.body}
            for a in artifacts
            if a.kind in {"user_message", "final"} and a.turn < session.turn
        ][-6:],
        "results": [{"id": a.id, "agent_id": a.agent_id, **a.body} for a in results],
        "inbox": [{"id": a.id, **a.body} for a in inbox],
        "evidence": evidence,
        "memory": memories[:6],
        "budget": {"remaining_micros": session.budget - session.spent - session.reserved},
        "truncated": [],
    }
    # Never silently truncate the current request or lose a tool-call/result pair.
    # This selection contains only independent platform records; SDK context is task-local.
    limit = spec["context_chars"]
    for section in ["prior_turns", "memory", "results", "inbox", "evidence"]:
        while len(json.dumps(payload, ensure_ascii=False)) > limit and payload[section]:
            payload[section].pop(0)
            if section not in payload["truncated"]:
                payload["truncated"].append(section)
    if len(json.dumps(payload, ensure_ascii=False)) > limit:
        from .runtime import SafeRuntimeError

        raise SafeRuntimeError("context_limit")
    included = [item["id"] for item in payload["inbox"]]
    return payload, included
