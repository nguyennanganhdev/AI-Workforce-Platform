"""Durable document chunks and explicit, version-isolated vector spaces."""

import asyncio
import math
import uuid

from qdrant_client import AsyncQdrantClient, models

from .config import settings
from .db import Job, Record, Session, emit, transaction, uid
from .domain import stable_hash
from .limits import reconcile, reserve
from .providers import close_model
from .queue import fence_for_execution as fence
from .security import decrypt


def chunk_text(text: str, size=1800, overlap=200):
    return [text[start : start + size] for start in range(0, len(text), size - overlap)]


def space_name(workspace, spec):
    return (
        "vp_"
        + stable_hash(
            [
                workspace,
                spec["adapter"],
                spec["base_url"],
                spec["model"],
                spec["dimensions"],
                spec["id"],
                spec["version"],
            ]
        )[:24]
    )


async def embed(job, spec, secret, texts):
    from agentscope.credential import OllamaCredential, OpenAICredential
    from agentscope.embedding import OllamaEmbeddingModel, OpenAIEmbeddingModel

    # One bounded batch, SDK retries and its underlying client retries disabled.
    bound = sum(len(text.encode()) for text in texts)
    price = {
        **spec,
        "context_tokens": bound,
        "max_output_tokens": 0,
        "output_micros_per_million": 0,
        "rpm": 60,
        "tpm": 1000000,
    }
    async with transaction() as db:
        session, current = await fence(db, job.id, job.generation)
        reservation = await reserve(db, session, current, price)
        reservation_id = reservation.id
    if spec["adapter"] == "openai":
        model = OpenAIEmbeddingModel(
            credential=OpenAICredential(
                api_key=decrypt(secret) if secret else "local", base_url=spec["base_url"] or None
            ),
            model=spec["model"],
            dimensions=spec["dimensions"],
            max_retries=0,
        )
        old_client = model.client
        model.client = old_client.with_options(max_retries=0, timeout=60)
        await old_client.close()
    else:
        model = OllamaEmbeddingModel(
            credential=OllamaCredential(host=spec["base_url"] or None),
            model=spec["model"],
            dimensions=spec["dimensions"],
            max_retries=0,
        )
    usage = None
    try:
        async with asyncio.timeout(90):
            response = await model(texts)
        if response.usage and response.usage.tokens is not None:
            usage = {"input_tokens": response.usage.tokens, "output_tokens": 0, "kind": "embedding"}
        vectors = response.embeddings
        if any(
            len(vector) != spec["dimensions"] or any(not math.isfinite(x) for x in vector)
            for vector in vectors
        ) or len(vectors) != len(texts):
            raise ValueError("Embedding dimension or numeric mismatch")
        return vectors
    finally:
        await close_model(model)
        async with transaction() as db:
            await reconcile(db, reservation_id, price, usage)


async def enqueue_index(db, p, kb, document):
    session = Session(
        id=uid(),
        workspace=p.workspace,
        owner=p.user_id,
        title="Index: " + document.body["title"],
        team=[],
        status="indexing",
        turn=1,
        budget=settings.session_budget_micros,
        board={"document_id": document.id},
    )
    db.add(session)
    await db.flush()
    job = Job(
        id=uid(),
        workspace=p.workspace,
        session_id=session.id,
        kind="index",
        dedupe="index:" + document.id + ":" + str(document.version),
        body={"turn": 1, "document_id": document.id, "knowledge_id": kb.id},
    )
    db.add(job)
    document.body = {**document.body, "index_status": "queued", "index_session_id": session.id}
    return session.id


async def execute_index(job):
    async with transaction() as db:
        session, current = await fence(db, job.id, job.generation)
        document = await db.get(Record, job.body["document_id"])
        kb = await db.get(Record, job.body["knowledge_id"])
        if not document or document.body.get("revoked") or not kb:
            current.status = "done"
            session.status = "idle"
            return
        chunks = chunk_text(document.body["text"])
        chunk_ids = []
        for i, text in enumerate(chunks):
            cid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{document.id}:{i}"))
            chunk_ids.append(cid)
            if not await db.get(Record, cid):
                db.add(
                    Record(
                        id=cid,
                        workspace=session.workspace,
                        owner=document.owner,
                        kind="chunks",
                        body={
                            "knowledge_id": kb.id,
                            "document_id": document.id,
                            "text": text,
                            "source": document.body["source"],
                            "expires": document.body.get("expires"),
                            "offset": i * 1600,
                        },
                    )
                )
        embedding_id = kb.body.get("embedding_model_id")
        embedding = await db.get(Record, embedding_id) if embedding_id else None
        spec = (
            {"id": embedding.id, "version": embedding.version, **embedding.body}
            if embedding
            else None
        )
        credential = (
            await db.get(Record, spec["credential_id"]) if spec and spec["credential_id"] else None
        )
        secret = credential.body["encrypted_secret"] if credential else ""
    space = ""
    if spec:
        if not settings.qdrant_url:
            from .runtime import SafeRuntimeError

            raise SafeRuntimeError("vector_store_not_configured")
        space = space_name(job.workspace, spec)
        client = AsyncQdrantClient(url=settings.qdrant_url, timeout=30)
        try:
            if not await client.collection_exists(space):
                try:
                    await client.create_collection(
                        space,
                        vectors_config=models.VectorParams(
                            size=spec["dimensions"], distance=models.Distance.COSINE
                        ),
                    )
                except Exception:
                    if not await client.collection_exists(space):
                        raise
            for start in range(0, len(chunks), 16):
                vectors = await embed(job, spec, secret, chunks[start : start + 16])
                # Upserts are idempotent; DB post-validation still governs retrieval ACLs.
                await client.upsert(
                    space,
                    points=[
                        models.PointStruct(
                            id=cid,
                            vector=vector,
                            payload={
                                "workspace": job.workspace,
                                "knowledge_id": job.body["knowledge_id"],
                                "document_id": job.body["document_id"],
                            },
                        )
                        for cid, vector in zip(chunk_ids[start : start + 16], vectors)
                    ],
                )
        finally:
            await client.close()
    async with transaction() as db:
        session, current = await fence(db, job.id, job.generation)
        document = await db.get(Record, job.body["document_id"])
        document.body = {
            **document.body,
            "index_status": "ready",
            "chunk_count": len(chunks),
            "vector_space": space,
            "embedding_spec": spec,
        }
        current.status = "done"
        session.status = "idle"
        await emit(
            db,
            session,
            "knowledge.indexed",
            {"document_id": document.id, "chunks": len(chunks), "vector_space": space},
        )


async def vector_search(job, spec, query, knowledge_ids):
    async with transaction() as db:
        credential = await db.get(Record, spec["credential_id"]) if spec["credential_id"] else None
        secret = credential.body["encrypted_secret"] if credential else ""
    vectors = await embed(job, spec, secret, [query[:2000]])
    client = AsyncQdrantClient(url=settings.qdrant_url, timeout=30)
    try:
        response = await client.query_points(
            space_name(job.workspace, spec),
            query=vectors[0],
            limit=6,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="workspace", match=models.MatchValue(value=job.workspace)
                    ),
                    models.FieldCondition(
                        key="knowledge_id", match=models.MatchAny(any=knowledge_ids)
                    ),
                ]
            ),
        )
        return [str(point.id) for point in response.points]
    finally:
        await client.close()
