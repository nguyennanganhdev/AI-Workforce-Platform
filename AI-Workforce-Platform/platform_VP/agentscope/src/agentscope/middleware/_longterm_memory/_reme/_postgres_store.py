# -*- coding: utf-8 -*-
"""PostgreSQL/pgvector persistence for selected ReMe memory facts.

ReMe remains responsible for extracting useful facts from a conversation.
This store provides the durable, multi-tenant query layer for those selected
facts; it deliberately does not store or embed every chat message.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Sequence
from uuid import UUID, uuid4

_ACTIVE = "active"


def _vector_literal(values: Sequence[float]) -> str:
    """Serialize a vector for pgvector's text input format."""
    if not values:
        raise ValueError("embedding must not be empty")
    return "[" + ",".join(format(float(value), ".9g") for value in values) + "]"


@dataclass(slots=True)
class ReMeMemory:
    """A selected long-term memory stored in PostgreSQL."""

    tenant_id: str
    user_id: str
    content: str
    embedding: Sequence[float] = field(repr=False)
    domain_id: str | None = None
    area_id: str | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    source_candidate_id: str | None = None
    agent_id: str | None = None
    source_session_id: str | None = None
    memory_type: str = "fact"
    importance: float = 0.5
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)
    expires_at: datetime | None = None
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        """Validate values before they reach SQL constraints."""
        if not self.tenant_id or not self.user_id:
            raise ValueError("tenant_id and user_id are required")
        if not self.content.strip():
            raise ValueError("content must not be empty")
        if not all(
            (
                self.domain_id,
                self.area_id,
                self.approved_by,
                self.approved_at,
                self.source_candidate_id,
            ),
        ):
            raise ValueError(
                "active memory requires domain, area, reviewer, approval "
                "time, and source candidate",
            )
        if not 0 <= self.importance <= 1:
            raise ValueError("importance must be between 0 and 1")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")


@dataclass(slots=True, frozen=True)
class ReMeMemorySearchResult:
    """Memory returned by semantic search."""

    id: UUID
    content: str
    memory_type: str
    importance: float
    confidence: float
    metadata: dict[str, Any]
    similarity: float
    source_session_id: str | None
    created_at: datetime
    updated_at: datetime


class PostgresReMeMemoryStore:
    """Async query service for the ``reme_memories`` pgvector table.

    The supplied SQLAlchemy ``AsyncEngine`` remains owned by the caller.
    Every read and mutation requires tenant, domain, and area scope. Active
    rows must originate from an explicitly reviewed candidate.
    """

    def __init__(self, engine: Any, *, dimensions: int = 1536) -> None:
        if dimensions != 1536:
            raise ValueError(
                "The packaged migration uses vector(1536); create a custom "
                "migration before using a different embedding dimension.",
            )
        self._engine = engine

    async def add(self, memory: ReMeMemory) -> UUID:
        """Insert one already-selected and embedded memory."""
        from sqlalchemy import text

        statement = text(
            """
            INSERT INTO reme_memories (
                id, tenant_id, user_id, domain_id, area_id, agent_id,
                source_session_id,
                content, memory_type, importance, confidence, embedding,
                metadata, expires_at, approved_by, approved_at,
                source_candidate_id
            ) VALUES (
                :id, :tenant_id, :user_id, :domain_id, :area_id,
                :agent_id, :source_session_id,
                :content, :memory_type, :importance, :confidence,
                CAST(:embedding AS vector), CAST(:metadata AS jsonb),
                :expires_at, :approved_by, :approved_at,
                :source_candidate_id
            )
            """,
        )
        async with self._engine.begin() as connection:
            await connection.execute(
                statement,
                {
                    "id": memory.id,
                    "tenant_id": memory.tenant_id,
                    "user_id": memory.user_id,
                    "domain_id": memory.domain_id,
                    "area_id": memory.area_id,
                    "agent_id": memory.agent_id,
                    "source_session_id": memory.source_session_id,
                    "content": memory.content.strip(),
                    "memory_type": memory.memory_type,
                    "importance": memory.importance,
                    "confidence": memory.confidence,
                    "embedding": _vector_literal(memory.embedding),
                    "metadata": json.dumps(memory.metadata),
                    "expires_at": memory.expires_at,
                    "approved_by": memory.approved_by,
                    "approved_at": memory.approved_at,
                    "source_candidate_id": memory.source_candidate_id,
                },
            )
        return memory.id

    async def search(
        self,
        *,
        tenant_id: str,
        domain_id: str,
        area_id: str,
        query_embedding: Sequence[float],
        agent_id: str | None = None,
        limit: int = 5,
        min_similarity: float = 0.0,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[ReMeMemorySearchResult]:
        """Return active, non-expired memories ordered by cosine similarity."""
        from sqlalchemy import text

        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        statement = text(
            """
            WITH ranked AS (
                SELECT id, content, memory_type, importance, confidence,
                       metadata, source_session_id, created_at, updated_at,
                       1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
                FROM reme_memories
                WHERE tenant_id = :tenant_id
                  AND domain_id = :domain_id
                  AND area_id = :area_id
                  AND status = 'active'
                  AND approved_by IS NOT NULL
                  AND approved_at IS NOT NULL
                  AND (expires_at IS NULL OR expires_at > now())
                  AND (:agent_id IS NULL OR agent_id IS NULL OR agent_id = :agent_id)
                  AND metadata @> CAST(:metadata_filter AS jsonb)
            )
            SELECT * FROM ranked
            WHERE similarity >= :min_similarity
            ORDER BY similarity DESC, importance DESC, updated_at DESC
            LIMIT :limit
            """,
        )
        params = {
            "tenant_id": tenant_id,
            "domain_id": domain_id,
            "area_id": area_id,
            "agent_id": agent_id,
            "embedding": _vector_literal(query_embedding),
            "metadata_filter": json.dumps(metadata_filter or {}),
            "min_similarity": min_similarity,
            "limit": limit,
        }
        async with self._engine.connect() as connection:
            rows = (await connection.execute(statement, params)).mappings().all()
        return [
            ReMeMemorySearchResult(
                id=row["id"],
                content=row["content"],
                memory_type=row["memory_type"],
                importance=row["importance"],
                confidence=row["confidence"],
                metadata=row["metadata"],
                similarity=float(row["similarity"]),
                source_session_id=row["source_session_id"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    async def add_or_merge(
        self,
        memory: ReMeMemory,
        *,
        duplicate_similarity: float = 0.92,
    ) -> tuple[UUID, bool]:
        """Insert a new memory or refresh the nearest duplicate.

        Returns ``(memory_id, created)``. A duplicate keeps its existing ID,
        replaces content/embedding with the newest formulation, merges JSON
        metadata, and retains the highest importance and confidence.
        """
        from sqlalchemy import text

        matches = await self.search(
            tenant_id=memory.tenant_id,
            domain_id=str(memory.domain_id),
            area_id=str(memory.area_id),
            agent_id=memory.agent_id,
            query_embedding=memory.embedding,
            limit=1,
            min_similarity=duplicate_similarity,
        )
        if not matches:
            return await self.add(memory), True

        existing_id = matches[0].id
        statement = text(
            """
            UPDATE reme_memories
            SET content = :content,
                embedding = CAST(:embedding AS vector),
                importance = GREATEST(importance, :importance),
                confidence = GREATEST(confidence, :confidence),
                metadata = metadata || CAST(:metadata AS jsonb),
                source_session_id = COALESCE(:source_session_id, source_session_id),
                expires_at = COALESCE(:expires_at, expires_at),
                updated_at = now()
            WHERE id = :id AND tenant_id = :tenant_id AND user_id = :user_id
              AND domain_id = :domain_id AND area_id = :area_id
            """,
        )
        async with self._engine.begin() as connection:
            await connection.execute(
                statement,
                {
                    "id": existing_id,
                    "tenant_id": memory.tenant_id,
                    "user_id": memory.user_id,
                    "domain_id": memory.domain_id,
                    "area_id": memory.area_id,
                    "content": memory.content.strip(),
                    "embedding": _vector_literal(memory.embedding),
                    "importance": memory.importance,
                    "confidence": memory.confidence,
                    "metadata": json.dumps(memory.metadata),
                    "source_session_id": memory.source_session_id,
                    "expires_at": memory.expires_at,
                },
            )
        return existing_id, False

    async def supersede(
        self,
        *,
        tenant_id: str,
        domain_id: str,
        area_id: str,
        old_memory_id: UUID,
        replacement: ReMeMemory,
    ) -> UUID:
        """Atomically insert a replacement and mark the old memory obsolete."""
        from sqlalchemy import text

        if (
            replacement.tenant_id != tenant_id
            or replacement.domain_id != domain_id
            or replacement.area_id != area_id
        ):
            raise ValueError("replacement owner does not match requested scope")
        async with self._engine.begin() as connection:
            locked = await connection.scalar(
                text(
                    """
                    SELECT id FROM reme_memories
                    WHERE id = :id AND tenant_id = :tenant_id
                      AND domain_id = :domain_id AND area_id = :area_id
                      AND status = 'active'
                    FOR UPDATE
                    """,
                ),
                {
                    "id": old_memory_id,
                    "tenant_id": tenant_id,
                    "domain_id": domain_id,
                    "area_id": area_id,
                },
            )
            if locked is None:
                raise KeyError(str(old_memory_id))
            await connection.execute(
                text(
                    """
                    INSERT INTO reme_memories (
                        id, tenant_id, user_id, domain_id, area_id, agent_id,
                        source_session_id,
                        content, memory_type, importance, confidence, embedding,
                        metadata, expires_at, approved_by, approved_at,
                        source_candidate_id
                    ) VALUES (
                        :id, :tenant_id, :user_id, :domain_id, :area_id,
                        :agent_id, :source_session_id,
                        :content, :memory_type, :importance, :confidence,
                        CAST(:embedding AS vector), CAST(:metadata AS jsonb),
                        :expires_at, :approved_by, :approved_at,
                        :source_candidate_id
                    )
                    """,
                ),
                {
                    "id": replacement.id,
                    "tenant_id": tenant_id,
                    "user_id": replacement.user_id,
                    "domain_id": domain_id,
                    "area_id": area_id,
                    "agent_id": replacement.agent_id,
                    "source_session_id": replacement.source_session_id,
                    "content": replacement.content.strip(),
                    "memory_type": replacement.memory_type,
                    "importance": replacement.importance,
                    "confidence": replacement.confidence,
                    "embedding": _vector_literal(replacement.embedding),
                    "metadata": json.dumps(replacement.metadata),
                    "expires_at": replacement.expires_at,
                    "approved_by": replacement.approved_by,
                    "approved_at": replacement.approved_at,
                    "source_candidate_id": replacement.source_candidate_id,
                },
            )
            await connection.execute(
                text(
                    """
                    UPDATE reme_memories
                    SET status = 'superseded', superseded_by = :replacement_id,
                        updated_at = now()
                    WHERE id = :old_id AND tenant_id = :tenant_id
                      AND domain_id = :domain_id AND area_id = :area_id
                    """,
                ),
                {
                    "replacement_id": replacement.id,
                    "old_id": old_memory_id,
                    "tenant_id": tenant_id,
                    "domain_id": domain_id,
                    "area_id": area_id,
                },
            )
        return replacement.id

    async def archive_stale(
        self,
        *,
        tenant_id: str,
        domain_id: str,
        area_id: str,
        older_than: datetime,
        max_importance: float = 0.4,
    ) -> int:
        """Archive low-value memories not accessed since a cutoff."""
        from sqlalchemy import text

        statement = text(
            """
            UPDATE reme_memories
            SET status = 'archived', updated_at = now()
            WHERE tenant_id = :tenant_id
              AND domain_id = :domain_id AND area_id = :area_id
              AND status = 'active' AND importance <= :max_importance
              AND COALESCE(last_accessed_at, created_at) < :older_than
            """,
        )
        async with self._engine.begin() as connection:
            result = await connection.execute(
                statement,
                {
                    "tenant_id": tenant_id,
                    "domain_id": domain_id,
                    "area_id": area_id,
                    "older_than": older_than,
                    "max_importance": max_importance,
                },
            )
        return int(result.rowcount or 0)

    async def mark_accessed(
        self,
        *,
        tenant_id: str,
        domain_id: str,
        area_id: str,
        memory_ids: Sequence[UUID],
    ) -> None:
        """Update retrieval telemetry without weakening owner isolation."""
        from sqlalchemy import bindparam, text

        if not memory_ids:
            return
        statement = text(
            """
            UPDATE reme_memories
            SET access_count = access_count + 1,
                last_accessed_at = now(), updated_at = now()
            WHERE tenant_id = :tenant_id
              AND domain_id = :domain_id AND area_id = :area_id
              AND id IN :memory_ids
            """,
        ).bindparams(bindparam("memory_ids", expanding=True))
        async with self._engine.begin() as connection:
            await connection.execute(
                statement,
                {
                    "tenant_id": tenant_id,
                    "domain_id": domain_id,
                    "area_id": area_id,
                    "memory_ids": list(memory_ids),
                },
            )
