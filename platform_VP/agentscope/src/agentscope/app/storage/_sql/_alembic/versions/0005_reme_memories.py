# -*- coding: utf-8 -*-
"""PostgreSQL/pgvector storage for selected long-term memories.

Revision ID: 0005_reme_memories
Revises: 0004_sops
Create Date: 2026-10-09 00:00:00.000000

This table is intentionally PostgreSQL-only. Other supported SQLAlchemy
dialects keep working and simply skip this optional memory backend.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0005_reme_memories"
down_revision: Union[str, None] = "0004_sops"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the pgvector-backed long-term-memory table."""
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        """
        CREATE TABLE reme_memories (
            id UUID PRIMARY KEY,
            tenant_id VARCHAR(255) NOT NULL,
            user_id VARCHAR(255) NOT NULL,
            agent_id VARCHAR(255),
            source_session_id VARCHAR(255),
            content TEXT NOT NULL,
            memory_type VARCHAR(64) NOT NULL DEFAULT 'fact',
            importance REAL NOT NULL DEFAULT 0.5,
            confidence REAL NOT NULL DEFAULT 1.0,
            status VARCHAR(24) NOT NULL DEFAULT 'active',
            embedding vector(1536) NOT NULL,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            superseded_by UUID REFERENCES reme_memories(id),
            access_count INTEGER NOT NULL DEFAULT 0,
            last_accessed_at TIMESTAMPTZ,
            expires_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT ck_reme_memories_importance
                CHECK (importance >= 0 AND importance <= 1),
            CONSTRAINT ck_reme_memories_confidence
                CHECK (confidence >= 0 AND confidence <= 1),
            CONSTRAINT ck_reme_memories_status
                CHECK (status IN ('active', 'superseded', 'archived', 'deleted'))
        )
        """,
    )
    op.execute(
        """
        CREATE INDEX ix_reme_memories_owner
        ON reme_memories (tenant_id, user_id, agent_id, status)
        """,
    )
    op.execute(
        """
        CREATE INDEX ix_reme_memories_session
        ON reme_memories (tenant_id, source_session_id)
        """,
    )
    op.execute(
        """
        CREATE INDEX ix_reme_memories_metadata
        ON reme_memories USING gin (metadata)
        """,
    )
    op.execute(
        """
        CREATE INDEX ix_reme_memories_embedding_hnsw
        ON reme_memories USING hnsw (embedding vector_cosine_ops)
        WHERE status = 'active'
        """,
    )


def downgrade() -> None:
    """Drop the long-term-memory table, retaining the shared extension."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TABLE IF EXISTS reme_memories")

