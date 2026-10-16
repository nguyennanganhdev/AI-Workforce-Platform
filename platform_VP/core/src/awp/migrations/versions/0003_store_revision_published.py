"""A change counter on a route's MCP server (a discovery only writes when the row is still the one it read), and one
published version per profile key enforced by the database (two publishers at once cannot both win).

A key that already has several published versions keeps the newest; the older ones become retired, which is what
publishing the newest would have made them.

Revision ID: 0003_store_revision_published
Revises: 0002_tool_store_managers
Create Date: 2026-10-11 18:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0003_store_revision_published'
down_revision: Union[str, None] = '0002_tool_store_managers'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('wf_mcp_servers') as batch:
        batch.add_column(sa.Column('revision', sa.Integer(), nullable=False, server_default='0'))

    op.execute(
        "update awp_profiles set status = 'retired' where status = 'published' and exists ("
        "select 1 from awp_profiles newer where newer.tenant = awp_profiles.tenant and newer.key = awp_profiles.key "
        "and newer.status = 'published' and newer.version > awp_profiles.version)")
    op.create_index('uq_profile_published', 'awp_profiles', ['tenant', 'key'], unique=True,
                    sqlite_where=sa.text("status = 'published'"), postgresql_where=sa.text("status = 'published'"))


def downgrade() -> None:
    op.drop_index('uq_profile_published', table_name='awp_profiles')
    with op.batch_alter_table('wf_mcp_servers') as batch:
        batch.drop_column('revision')
