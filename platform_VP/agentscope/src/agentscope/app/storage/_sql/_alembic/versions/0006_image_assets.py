# -*- coding: utf-8 -*-
"""Image asset metadata stored separately from S3 object bytes.

Revision ID: 0006_image_assets
Revises: 0005_reme_memories
Create Date: 2026-10-09 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006_image_assets"
down_revision: Union[str, None] = "0005_reme_memories"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create portable image metadata; object bytes remain in S3."""
    op.create_table(
        "image_assets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("object_uri", sa.Text(), nullable=False),
        sa.Column("original_filename", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=64), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_uri"),
    )
    op.create_index(
        "ix_image_assets_owner_status",
        "image_assets",
        ["tenant_id", "user_id", "status"],
    )
    op.create_index(
        "ix_image_assets_owner_sha256",
        "image_assets",
        ["tenant_id", "user_id", "sha256"],
    )


def downgrade() -> None:
    """Drop image metadata without deleting external objects."""
    op.drop_index("ix_image_assets_owner_sha256", table_name="image_assets")
    op.drop_index("ix_image_assets_owner_status", table_name="image_assets")
    op.drop_table("image_assets")

