"""The tool store (MCP servers that can be switched on, discovered tools with a stored schema), the consent waiver of an
action, and management accounts with their operator keys.

Rows that exist keep behaving as they did: their servers are enabled, their tools manual and active. Routes older than
managers keep a null manager_id (no manager key reaches them).

Revision ID: 0002_tool_store_managers
Revises: 0001_initial
Create Date: 2026-10-11 12:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0002_tool_store_managers'
down_revision: Union[str, None] = '0001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('wf_managers',
    sa.Column('id', sa.String(length=48), nullable=False),
    sa.Column('tenant', sa.String(length=80), nullable=False),
    sa.Column('client_id', sa.String(length=48), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('created_at', sa.Float(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_wf_managers_client_id'), 'wf_managers', ['client_id'], unique=False)
    op.create_index(op.f('ix_wf_managers_tenant'), 'wf_managers', ['tenant'], unique=False)

    op.create_table('wf_manager_keys',
    sa.Column('key_id', sa.String(length=64), nullable=False),
    sa.Column('manager_id', sa.String(length=48), nullable=False),
    sa.Column('secret_hash', sa.String(length=64), nullable=False),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('expires_at', sa.Float(), nullable=True),
    sa.Column('created_at', sa.Float(), nullable=False),
    sa.Column('revoked_at', sa.Float(), nullable=True),
    sa.PrimaryKeyConstraint('key_id')
    )
    op.create_index(op.f('ix_wf_manager_keys_manager_id'), 'wf_manager_keys', ['manager_id'], unique=False)

    with op.batch_alter_table('wf_routes') as batch:
        batch.add_column(sa.Column('manager_id', sa.String(length=48), nullable=True))
        batch.create_index(batch.f('ix_wf_routes_manager_id'), ['manager_id'], unique=False)

    with op.batch_alter_table('wf_mcp_servers') as batch:
        batch.add_column(sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()))
        batch.add_column(sa.Column('last_discovered_at', sa.Float(), nullable=True))
        batch.add_column(sa.Column('last_error', sa.String(length=300), nullable=True))

    with op.batch_alter_table('wf_tools') as batch:
        batch.add_column(sa.Column('source', sa.String(length=12), nullable=False, server_default='manual'))
        batch.add_column(sa.Column('status', sa.String(length=12), nullable=False, server_default='active'))
        batch.add_column(sa.Column('schema', sa.JSON(), nullable=True))
        batch.add_column(sa.Column('discovered_at', sa.Float(), nullable=True))
        batch.add_column(sa.Column('consent_waiver', sa.String(length=300), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('wf_tools') as batch:
        for name in ('consent_waiver', 'discovered_at', 'schema', 'status', 'source'):
            batch.drop_column(name)
    with op.batch_alter_table('wf_mcp_servers') as batch:
        for name in ('last_error', 'last_discovered_at', 'enabled'):
            batch.drop_column(name)
    with op.batch_alter_table('wf_routes') as batch:
        batch.drop_index(batch.f('ix_wf_routes_manager_id'))
        batch.drop_column('manager_id')
    op.drop_index(op.f('ix_wf_manager_keys_manager_id'), table_name='wf_manager_keys')
    op.drop_table('wf_manager_keys')
    op.drop_index(op.f('ix_wf_managers_tenant'), table_name='wf_managers')
    op.drop_index(op.f('ix_wf_managers_client_id'), table_name='wf_managers')
    op.drop_table('wf_managers')
