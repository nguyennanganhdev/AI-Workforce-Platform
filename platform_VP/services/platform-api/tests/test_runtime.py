import asyncio
import json

import pytest
from agentscope.credential import OllamaCredential
from agentscope.message import ToolCallBlock
from agentscope.model import ChatModelBase, ChatResponse, ChatUsage
from fastapi import HTTPException
from sqlalchemy import func, select

from vp import runtime
from vp.db import Artifact, Job, Session, transaction
from vp.domain import create_session, submit_chat
from vp.knowledge import execute_index
from vp.queue import claim, worker_loop


class FixtureModel(ChatModelBase):
    """Exercises the actual AgentScope loop/tool/schema, substitutes only provider I/O."""

    def __init__(self, result=None):
        from agentscope.formatter import OpenAIChatFormatter

        super().__init__(
            credential=OllamaCredential(),
            model="fixture",
            parameters=self.Parameters(),
            stream=False,
            max_retries=0,
            context_size=128000,
        )
        self.result = result
        self.formatter = OpenAIChatFormatter()

    async def _call_api(self, model_name, messages, tools, tool_choice=None, **kwargs):
        await asyncio.sleep(0.01)
        result = self.result or {
            "status": "needs_input",
            "answer": "Cần tài liệu có nguồn để kiểm chứng.",
            "unknowns": ["Chưa có tài liệu"],
            "next_action": "Cung cấp tài liệu",
        }
        return ChatResponse(
            content=[
                ToolCallBlock(
                    id="call-fixture", name="GenerateStructuredOutput", input=json.dumps(result)
                )
            ],
            is_last=True,
            usage=ChatUsage(input_tokens=100, output_tokens=100, time=0.01),
        )


async def test_actual_agentscope_single_agent_and_snapshot(principal, registry, monkeypatch):
    monkeypatch.setattr(runtime, "create_model", lambda *args: FixtureModel())
    async with transaction() as db:
        session = await create_session(db, principal, "Actual SDK", registry, 500000)
        sid = session.id
        await submit_chat(db, principal, sid, "Tôi cần kiểm chứng", "sdk-request")
    job = await claim("sdk")
    await runtime.execute_agent(job)
    async with transaction() as db:
        session = await db.get(Session, sid)
        assert session.status == "needs_input"
        snapshots = (await db.scalars(select(Artifact).where(Artifact.kind == "context"))).all()
        assert snapshots[0].body["accepted"] and snapshots[0].body["state"]
        assert "thinking" not in json.dumps(snapshots[0].body["state"])


async def test_twenty_concurrent_sessions_fenced_queue(
    principal, registry, monkeypatch, isolated_database
):
    if isolated_database.dialect.name != "postgresql":
        pytest.skip("PostgreSQL row-lock/load acceptance; run with VP_TEST_DATABASE_URL")
    monkeypatch.setattr(
        runtime,
        "create_model",
        lambda *args: FixtureModel(
            {
                "status": "needs_review",
                "answer": "Phân tích xong, cần kiểm chứng nguồn độc lập.",
            }
        ),
    )
    ids = []
    for index in range(20):
        async with transaction() as db:
            session = await create_session(db, principal, f"Concurrent {index}", registry, 500000)
            ids.append(session.id)
            await submit_chat(
                db,
                principal,
                session.id,
                "Kiểm tra session riêng " + str(index),
                f"request-{index:08}",
            )
    with pytest.raises(HTTPException, match="429"):
        async with transaction() as db:
            overflow = await create_session(db, principal, "Overflow", registry, 500000)
            await submit_chat(db, principal, overflow.id, "Overflow", "overflow-request")
    stop = asyncio.Event()
    workers = [asyncio.create_task(worker_loop(i, stop, runtime.execute_agent)) for i in range(8)]
    try:
        async with asyncio.timeout(40):
            while True:
                async with transaction() as db:
                    active = await db.scalar(
                        select(func.count()).select_from(Session).where(Session.status == "running")
                    )
                if active == 0:
                    break
                await asyncio.sleep(0.1)
    finally:
        stop.set()
        await asyncio.gather(*workers)
    async with transaction() as db:
        sessions = (await db.scalars(select(Session))).all()
        assert len(sessions) == 20 and all(s.status == "needs_review" for s in sessions)
        contexts = (await db.scalars(select(Artifact).where(Artifact.kind == "context"))).all()
        assert len(contexts) == 60
        for c in contexts:
            session = next(s for s in sessions if s.id == c.session_id)
            assert c.body["selected"]["goal"] == session.board["goal"]
        jobs = (await db.scalars(select(Job))).all()
        assert len(jobs) == 60 and all(j.status == "done" and j.generation == 1 for j in jobs)


async def test_document_index_and_revocation(client, principal):
    kb = (
        await client.post(
            "/api/resources/knowledge", json={"name": "Policy", "visibility": "workspace"}
        )
    ).json()
    document = (
        await client.post(
            "/api/knowledge/" + kb["id"] + "/documents",
            json={"title": "Policy", "source": "fixture:v1", "text": "Chi phí hợp lệ là 100 đồng."},
        )
    ).json()
    job = await claim("index", "index")
    await execute_index(job)
    response = await client.get("/api/knowledge/" + kb["id"] + "/search?q=chi phí")
    assert len(response.json()) == 1 and "100" in response.text
    await client.delete("/api/documents/" + document["id"])
    assert (await client.get("/api/knowledge/" + kb["id"] + "/search?q=chi phí")).json() == []


async def test_multiagent_chain_bounded_and_evidence(principal, registry, monkeypatch):
    # Valid provenance still needs independent final verification, never consensus-only acceptance.
    async with transaction() as db:
        session = await create_session(db, principal, "Team", registry, 500000)
        sid = session.id
        await submit_chat(db, principal, sid, "Verify 100", "team-request")
        db.add(
            Artifact(
                id="evidence",
                workspace="default",
                session_id=sid,
                kind="evidence",
                body={"text": "Value 100", "verified": True, "source": "fixture"},
            )
        )
    result = {
        "status": "complete",
        "answer": "Value is 100",
        "claims": [{"text": "Value is 100", "quote": "Value 100", "evidence_ids": ["evidence"]}],
        "disagreement": "Review the source independently",
    }
    monkeypatch.setattr(runtime, "create_model", lambda *args: FixtureModel(result))
    count = 0
    while job := await claim("team"):
        await runtime.execute_agent(job)
        count += 1
        assert count <= 6
    async with transaction() as db:
        session = await db.get(Session, sid)
        assert session.status == "idle" and count == 5  # plan, work, debate x2, verify
        assert (
            await db.scalar(
                select(func.count()).select_from(Artifact).where(Artifact.kind == "final")
            )
            == 1
        )


async def test_provider_constructors_do_not_ignore_output_limit():
    from vp.providers import close_model, create_model
    from vp.security import encrypt

    for adapter in ["openai", "openai-responses", "anthropic", "dashscope", "gemini", "ollama"]:
        model = create_model(
            {
                "adapter": adapter,
                "model": "fixture",
                "context_tokens": 64000,
                "max_output_tokens": 333,
                "base_url": "",
            },
            encrypt("fixture-key"),
        )
        assert model.parameters.max_tokens == 333
        assert model.max_retries == 0 and not model.stream
        if adapter in {"openai", "openai-responses", "anthropic", "dashscope"}:
            assert model.client.max_retries == 0
        await close_model(model)
