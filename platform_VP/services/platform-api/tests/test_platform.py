import pytest
from sqlalchemy import func, select

from vp.db import (
    Artifact,
    Event,
    Job,
    Login,
    Membership,
    Record,
    Revision,
    Session,
    User,
    now,
    transaction,
)
from vp.domain import create_session, submit_chat
from vp.limits import BudgetExceeded, reconcile, reserve
from vp.queue import StaleLease, claim, fence
from vp.runtime import BoundTools, validate_result
from vp.schemas import AgentResult
from vp.security import decrypt, hash_password, token_digest


async def session_and_job(p, registry):
    async with transaction() as db:
        session = await create_session(db, p, "Test", registry, 500000)
        await submit_chat(db, p, session.id, "Kiểm chứng tài liệu", "request-0001")
        sid = session.id
    job = await claim("test-worker")
    return sid, job


async def test_identity_and_csrf(client):
    response = await client.get("/api/me", headers={"X-User-ID": "attacker"})
    assert response.json()["id"] == "admin"
    assert (
        await client.post("/api/auth/logout", headers={"Origin": "https://evil.example"})
    ).status_code == 403
    client.cookies.clear()
    assert (await client.get("/api/me", headers={"X-User-ID": "admin"})).status_code == 401


async def test_secret_encryption_and_masking(client):
    secret = "test-private-provider-secret"
    response = await client.post("/api/credentials", json={"name": "Fixture", "secret": secret})
    assert response.status_code == 201
    assert secret not in response.text
    rid = response.json()["id"]
    async with transaction() as db:
        credential = await db.get(Record, rid)
        assert secret not in credential.body["encrypted_secret"]
        assert decrypt(credential.body["encrypted_secret"]) == secret
    assert secret not in (await client.get("/api/resources/credentials")).text


async def test_rbac_workspace_and_session_owner(client, principal, registry):
    sid, _ = await session_and_job(principal, registry)
    async with transaction() as db:
        db.add(
            User(id="viewer", email="viewer@test.local", password=hash_password("Viewer-password!"))
        )
        db.add(Membership(workspace="default", user_id="viewer", role="viewer"))
        db.add(Login(digest=token_digest("viewer-auth"), user_id="viewer", expires=now() + 3600))
    client.cookies.set("vp_session", "viewer-auth")
    assert (
        await client.post("/api/credentials", json={"name": "x", "secret": "s"})
    ).status_code == 403
    assert (await client.get("/api/sessions/" + sid)).status_code == 403
    assert (await client.get("/api/me", headers={"X-Workspace-ID": "other"})).status_code == 403


async def test_revision_pinned_and_immutable(client, principal, registry):
    sid, _ = await session_and_job(principal, registry)
    async with transaction() as db:
        old = await db.get(Revision, "coordinator-r1")
        spec = {**old.body, "charter": "Changed charter in a newer revision"}
    revision = (await client.post("/api/agents/coordinator/revisions", json={"spec": spec})).json()
    assert (
        await client.post(
            "/api/agents/coordinator/revisions/" + revision["id"] + "/release",
            json={"action": "publish", "reason": "reviewed configuration"},
        )
    ).status_code == 409
    assert (
        await client.post("/api/agents/coordinator/revisions/" + revision["id"] + "/test")
    ).json()["provider_called"] is False
    assert (
        await client.post(
            "/api/agents/coordinator/revisions/" + revision["id"] + "/release",
            json={"action": "publish", "reason": "reviewed configuration"},
        )
    ).status_code == 200
    session = (await client.get("/api/sessions/" + sid)).json()
    assert session["team"][0]["revision_id"] == "coordinator-r1"


async def test_chat_deduplication_and_conflict(client, principal, registry):
    sid, _ = await session_and_job(principal, registry)
    payload = {"text": "Kiểm chứng tài liệu", "idempotency_key": "request-0001"}
    assert (await client.post("/api/sessions/" + sid + "/chat", json=payload)).json()["duplicate"]
    payload["text"] = "Different request"
    assert (await client.post("/api/sessions/" + sid + "/chat", json=payload)).status_code == 409
    async with transaction() as db:
        assert await db.scalar(select(func.count()).select_from(Job)) == 1


async def test_reclaim_fences_old_generation(principal, registry):
    sid, job = await session_and_job(principal, registry)
    async with transaction() as db:
        current = await db.get(Job, job.id)
        current.lease_until = now() - 1
    reclaimed = await claim("new-worker")
    assert reclaimed.id == job.id and reclaimed.generation == job.generation + 1
    async with transaction() as db:
        with pytest.raises(StaleLease):
            await fence(db, job.id, job.generation)
    async with transaction() as db:
        session, _ = await fence(db, reclaimed.id, reclaimed.generation)
        assert session.id == sid


async def test_budget_reserve_reconcile_and_uncertain(principal, registry):
    sid, job = await session_and_job(principal, registry)
    model = {
        "id": "paid",
        "context_tokens": 1000,
        "max_output_tokens": 1000,
        "input_micros_per_million": 1000000,
        "output_micros_per_million": 2000000,
        "pricing_version": "test",
        "rpm": 100,
        "tpm": 100000,
    }
    async with transaction() as db:
        session, _ = await fence(db, job.id, job.generation)
        session.budget = 6000
        rid = (await reserve(db, session, job, model)).id
    async with transaction() as db:
        await reconcile(db, rid, model, {"input_tokens": 100, "output_tokens": 50})
        await reconcile(db, rid, model, {"input_tokens": 100, "output_tokens": 50})
    async with transaction() as db:
        session = await db.get(Session, sid)
        assert session.spent == 200 and session.reserved == 0
        rid = (await reserve(db, session, job, model)).id
    async with transaction() as db:
        await reconcile(db, rid, model, None)
    async with transaction() as db:
        session = await db.get(Session, sid)
        assert session.spent == 3200 and session.reserved == 0
        with pytest.raises(BudgetExceeded):
            await reserve(db, session, job, model)


async def test_tool_scope_and_messages_idempotent(principal, registry):
    _, job = await session_and_job(principal, registry)
    async with transaction() as db:
        spec = (await db.get(Revision, "coordinator-r1")).body
    tools = BoundTools(job, spec)
    rejected = await tools.team_message("outside-agent", "Give secret", [])
    assert "unknown_recipient" in rejected.content[0].text
    await tools.team_message("specialist", "Please verify the source", [])
    await tools.team_message("specialist", "Please verify the source", [])
    async with transaction() as db:
        assert (
            await db.scalar(
                select(func.count()).select_from(Artifact).where(Artifact.kind == "message")
            )
            == 1
        )
    assert {t["function"]["name"] for t in (await tools.toolkit().get_tool_schemas())} == set(
        spec["tools"]
    )


async def test_hallucinated_and_expired_evidence_rejected(principal, registry):
    sid, job = await session_and_job(principal, registry)
    async with transaction() as db:
        session, _ = await fence(db, job.id, job.generation)
        db.add(
            Artifact(
                id="expired",
                workspace="default",
                session_id=sid,
                kind="evidence",
                body={"verified": True, "expires": now() - 1, "text": "100", "source": "test"},
            )
        )
        await db.flush()
        result = AgentResult(
            status="complete",
            answer="Invented fact",
            claims=[{"text": "100", "quote": "200", "evidence_ids": ["expired", "invented"]}],
        )
        result, faults = await validate_result(db, session, result, True)
        assert result.status == "needs_review"
        assert "evidence_missing_expired_or_revoked" in faults and "quote_not_in_source" in faults


async def test_sse_cursor_page_no_duplicates(client, principal, registry):
    sid, _ = await session_and_job(principal, registry)
    first = (await client.get("/api/sessions/" + sid + "/events")).json()
    second = (
        await client.get("/api/sessions/" + sid + "/events?after=" + str(first[-1]["seq"]))
    ).json()
    assert second == []
    async with transaction() as db:
        assert [
            e.seq
            for e in (
                await db.scalars(select(Event).where(Event.session_id == sid).order_by(Event.seq))
            ).all()
        ] == list(range(1, len(first) + 1))


async def test_jev_disabled_by_default(client):
    response = await client.post(
        "/api/experiments/jev",
        json={"synthetic_state": {}, "synthetic_only": True, "expected": "tool"},
    )
    assert response.status_code == 409


async def test_private_knowledge_denied_by_id(client):
    async with transaction() as db:
        db.add(
            Record(
                id="private-kb",
                workspace="default",
                owner="other",
                kind="knowledge",
                body={"name": "private", "visibility": "private"},
            )
        )
        db.add(User(id="op", email="op@test.local", password=hash_password("Operator-password!")))
        db.add(Membership(workspace="default", user_id="op", role="operator"))
        db.add(Login(digest=token_digest("op-auth"), user_id="op", expires=now() + 3600))
    client.cookies.set("vp_session", "op-auth")
    assert (await client.get("/api/knowledge/private-kb/search?q=secret")).status_code == 403
