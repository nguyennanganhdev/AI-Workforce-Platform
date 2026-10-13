"""Image assets (spec A3, slice P5c): who an uploaded image belongs to.

`wf_assets` has been in the schema since the first revision and nothing ever wrote to it. An asset now belongs to an
audience from its upload on: `external_user_id` and `external_conversation_id` (the partner's ids the upload named),
both required. The table is made again in its new shape instead of altered: it holds no row, and a NOT NULL column
cannot be added to a table without inventing a value for rows that would have none.

Revision ID: 0007_assets
Revises: 0006_operation_node
Create Date: 2026-10-12 18:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0007_assets'
down_revision: Union[str, None] = '0006_operation_node'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table('wf_assets')
    op.create_table('wf_assets',
    sa.Column('id', sa.String(length=48), nullable=False),
    sa.Column('client_id', sa.String(length=48), nullable=False),
    sa.Column('external_user_id', sa.String(length=200), nullable=False),
    sa.Column('external_conversation_id', sa.String(length=200), nullable=False),
    sa.Column('conversation_id', sa.String(length=48), nullable=True),
    sa.Column('object_key', sa.Text(), nullable=False),
    sa.Column('content_type', sa.String(length=64), nullable=False),
    sa.Column('size', sa.Integer(), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.Float(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_wf_assets_client_id'), 'wf_assets', ['client_id'], unique=False)
    op.create_index(op.f('ix_wf_assets_conversation_id'), 'wf_assets', ['conversation_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_wf_assets_conversation_id'), table_name='wf_assets')
    op.drop_index(op.f('ix_wf_assets_client_id'), table_name='wf_assets')
    op.drop_table('wf_assets')
    op.create_table('wf_assets',
    sa.Column('id', sa.String(length=48), nullable=False),
    sa.Column('client_id', sa.String(length=48), nullable=False),
    sa.Column('conversation_id', sa.String(length=48), nullable=True),
    sa.Column('object_key', sa.Text(), nullable=False),
    sa.Column('content_type', sa.String(length=64), nullable=False),
    sa.Column('size', sa.Integer(), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.Float(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
