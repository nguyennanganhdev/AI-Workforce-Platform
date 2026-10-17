# -*- coding: utf-8 -*-
"""Local accounts and rotating refresh-token sessions.

Revision ID: 0007_auth
Revises: 0006_image_assets
Create Date: 2026-10-09 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0007_auth"
down_revision: Union[str, None] = "0006_image_assets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create account and refresh-session tables."""
    op.create_table(
        "auth_users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "email", name="uq_auth_users_email"),
        sa.UniqueConstraint(
            "tenant_id",
            "username",
            name="uq_auth_users_username",
        ),
    )
    op.create_index(
        "ix_auth_users_tenant_status",
        "auth_users",
        ["tenant_id", "status"],
    )
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("family_id", sa.String(length=36), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_reason", sa.String(length=64)),
        sa.Column("replaced_by", sa.String(length=36)),
        sa.Column("user_agent", sa.String(length=512)),
        sa.Column("ip_address", sa.String(length=64)),
        sa.ForeignKeyConstraint(["user_id"], ["auth_users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["replaced_by"], ["auth_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("refresh_token_hash"),
    )
    op.create_index(
        "ix_auth_sessions_user",
        "auth_sessions",
        ["tenant_id", "user_id"],
    )
    op.create_index(
        "ix_auth_sessions_family",
        "auth_sessions",
        ["family_id", "revoked_at"],
    )
    op.create_index(
        "ix_auth_sessions_expiry",
        "auth_sessions",
        ["expires_at"],
    )


def downgrade() -> None:
    """Drop authentication data."""
    op.drop_index("ix_auth_sessions_expiry", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_family", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_user", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_index("ix_auth_users_tenant_status", table_name="auth_users")
    op.drop_table("auth_users")

