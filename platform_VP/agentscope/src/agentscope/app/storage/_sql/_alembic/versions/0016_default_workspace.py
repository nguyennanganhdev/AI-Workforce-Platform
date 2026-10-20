"""Seed the neutral scope every self-registered customer account receives.

Revision ID: 0016_default_workspace
Revises: 0015_shared_context_backfill
Create Date: 2026-10-20 00:00:00.000000
"""

from __future__ import annotations

import os
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016_default_workspace"
down_revision: str | None = "0015_shared_context_backfill"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Must match AuthService.DEFAULT_DOMAIN_ID / DEFAULT_AREA_ID.
_DOMAIN_ID = "default"
_AREA_ID = "default"


def upgrade() -> None:
    """Insert the default domain/area once, for the deployment's tenant."""
    tenant_id = os.getenv("AUTH_DEFAULT_TENANT_ID", "default").strip() or "default"
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            INSERT INTO business_domains (id, tenant_id, name, status)
            VALUES (:id, :tenant_id, 'Default workspace (self sign-up)', 'active')
            ON CONFLICT DO NOTHING
            """,
        ),
        {"id": _DOMAIN_ID, "tenant_id": tenant_id},
    )
    bind.execute(
        sa.text(
            """
            INSERT INTO areas (id, domain_id, name, status)
            VALUES (:id, :domain_id, 'Default workspace (self sign-up)', 'active')
            ON CONFLICT DO NOTHING
            """,
        ),
        {"id": _AREA_ID, "domain_id": _DOMAIN_ID},
    )


def downgrade() -> None:
    """Keep the rows: accounts and memberships reference them."""
