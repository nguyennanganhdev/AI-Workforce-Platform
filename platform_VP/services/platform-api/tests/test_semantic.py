import json

from agentscope.embedding import EmbeddingResponse, EmbeddingUsage, OllamaEmbeddingModel
from qdrant_client import AsyncQdrantClient
from sqlalchemy import select

from vp import knowledge, runtime
from vp.config import settings
from vp.context import lexical_search
from vp.db import Record, Reservation, Revision, transaction
from vp.domain import create_session, submit_chat
from vp.queue import claim


async def test_semantic_index_query_and_revocation_with_sdk(
    client, principal, registry, monkeypatch, tmp_path
):
    # Real SDK batching/response handling and real persistent Qdrant local engine.
    # Only embedding provider I/O is replaced; text intentionally has no keyword match.
    requests = []

    async def embed_api(self, inputs, **kwargs):
        requests.extend(inputs)
        return EmbeddingResponse(
            embeddings=[[1.0, 0.0] for _ in inputs], usage=EmbeddingUsage(tokens=100, time=0.01)
        )

    monkeypatch.setattr(OllamaEmbeddingModel, "_call_api", embed_api)
    monkeypatch.setattr(settings, "qdrant_url", "http://fixture")
    monkeypatch.setattr(
        knowledge,
        "AsyncQdrantClient",
        lambda **kwargs: AsyncQdrantClient(path=str(tmp_path / "vectors")),
    )
    embedding = (
        await client.post(
            "/api/resources/embeddings",
            json={
                "name": "Fixture embedding",
                "adapter": "ollama",
                "model": "fixture",
                "dimensions": 2,
                "input_micros_per_million": 1000000,
                "pricing_version": "fixture",
            },
        )
    ).json()
    kb = (
        await client.post(
            "/api/resources/knowledge",
            json={
                "name": "Semantic",
                "embedding_model_id": embedding["id"],
                "visibility": "workspace",
            },
        )
    ).json()
    doc = (
        await client.post(
            f"/api/knowledge/{kb['id']}/documents",
            json={
                "title": "Policy",
                "text": "Allowed reimbursement is one hundred.",
                "source": "fixture:policy",
            },
        )
    ).json()
    job = await claim("index", "index")
    await knowledge.execute_index(job)
    async with transaction() as db:
        session = await create_session(db, principal, "Semantic query", registry, 500000)
        await submit_chat(db, principal, session.id, "Find policy", "semantic-request")
        spec = {**(await db.get(Revision, "coordinator-r1")).body, "knowledge_ids": [kb["id"]]}
        assert not await lexical_search(db, "default", "admin", [kb["id"]], "expenses")
    job = await claim("query")
    result = await runtime.BoundTools(job, spec).knowledge_search("expenses")
    body = json.loads(result.content[0].text)
    assert body["retrieval"] == "hybrid" and body["evidence"][0]["source"] == "fixture:policy"
    assert len(requests) == 2
    async with transaction() as db:
        rows = (await db.scalars(select(Reservation))).all()
        assert len(rows) == 2 and all(row.status == "usage_reported" for row in rows)
        document = await db.get(Record, doc["id"])
        assert document.body["vector_space"].startswith("vp_")
    await client.delete("/api/documents/" + doc["id"])
    result = await runtime.BoundTools(job, spec).knowledge_search("expenses")
    assert json.loads(result.content[0].text)["missing"]
    assert len(requests) == 2  # Revoked document causes no further query embedding call.
