"""Workforce immutable agent releases and deployment heads.

Revision ID: 0011_workforce_releases
Revises: 0010_workforce_runtime
Create Date: 2026-10-12 00:00:00.000000

The definitions are frozen here instead of importing runtime metadata.  This
keeps an already released migration deterministic when Lifecycle evolves.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_workforce_releases"
down_revision: str | None = "0010_workforce_runtime"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


metadata = sa.MetaData()


def _scope() -> list[sa.Column]:
    return [
        sa.Column(name, sa.String(length=200), primary_key=True)
        for name in (
            "tenant_id",
            "domain_id",
            "area_id",
            "manager_account_id",
        )
    ]


sa.Table(
    "wf_release_candidates",
    metadata,
    *_scope(),
    sa.Column("draft_id", sa.String(length=200), primary_key=True),
    sa.Column("agent_id", sa.String(length=200), nullable=False),
    sa.Column("revision", sa.Integer(), nullable=False),
    sa.Column("frozen", sa.JSON(), nullable=False),
    sa.Column("content_hash", sa.String(length=64), nullable=False),
)

sa.Table(
    "wf_published_versions",
    metadata,
    *_scope(),
    sa.Column("version_id", sa.String(length=200), primary_key=True),
    sa.Column("agent_id", sa.String(length=200), nullable=False),
    sa.Column("payload", sa.JSON(), nullable=False),
    sa.Column("content_hash", sa.String(length=64), nullable=False),
)

sa.Table(
    "wf_agent_deployments",
    metadata,
    *_scope(),
    sa.Column("deployment_id", sa.String(length=200), primary_key=True),
    sa.Column("active_version_id", sa.String(length=200), nullable=True),
    sa.Column("revision", sa.Integer(), nullable=False),
    sa.Column("archived", sa.Boolean(), nullable=False),
    sa.Column("enabled", sa.Boolean(), nullable=False),
)

sa.Table(
    "wf_release_commands",
    metadata,
    *_scope(),
    sa.Column("command_id", sa.String(length=200), primary_key=True),
    sa.Column("request_hash", sa.String(length=64), nullable=False),
    sa.Column("result", sa.JSON(), nullable=True),
)


def upgrade() -> None:
    """Create the additive release tables without runtime ``create_all``."""
    bind = op.get_bind()
    for table in metadata.sorted_tables:
        table.create(bind=bind)


def downgrade() -> None:
    """Drop only D4 release tables; never use this with retained pins."""
    bind = op.get_bind()
    for table in reversed(metadata.sorted_tables):
        table.drop(bind=bind)
