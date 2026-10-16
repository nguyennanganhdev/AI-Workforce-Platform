"""Building agents in a chat (builder sessions), evaluating a version before it is released (cases, runs), and the
record of a release: who published a version and when, and the history of a profile key.

A version that is published or retired today was published once: it gets the time it was made as the time it went
live, so a rollback to it is possible.

Revision ID: 0004_builder_evals_release
Revises: 0003_store_revision_published
Create Date: 2026-10-11 22:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0004_builder_evals_release'
down_revision: Union[str, None] = '0003_store_revision_published'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('awp_profiles') as batch:
        batch.add_column(sa.Column('published_at', sa.Float(), nullable=True))
        batch.add_column(sa.Column('published_by', sa.String(length=80), nullable=True))
    op.execute("update awp_profiles set published_at = created_at where status in ('published', 'retired')")

    op.create_table('awp_profile_events',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant', sa.String(length=80), nullable=False),
    sa.Column('key', sa.String(length=80), nullable=False),
    sa.Column('version', sa.Integer(), nullable=True),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('actor', sa.String(length=80), nullable=False),
    sa.Column('detail', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.Float(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_profile_event_key', 'awp_profile_events', ['tenant', 'key', 'id'], unique=False)

    op.create_table('awp_builder_sessions',
    sa.Column('id', sa.String(length=40), nullable=False),
    sa.Column('tenant', sa.String(length=80), nullable=False),
    sa.Column('messages', sa.JSON(), nullable=False),
    sa.Column('proposals', sa.JSON(), nullable=False),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.Column('created_by', sa.String(length=80), nullable=False),
    sa.Column('created_at', sa.Float(), nullable=False),
    sa.Column('updated_at', sa.Float(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_awp_builder_sessions_tenant'), 'awp_builder_sessions', ['tenant'], unique=False)

    op.create_table('awp_eval_cases',
    sa.Column('id', sa.String(length=40), nullable=False),
    sa.Column('tenant', sa.String(length=80), nullable=False),
    sa.Column('key', sa.String(length=80), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('input', sa.Text(), nullable=False),
    sa.Column('fixtures', sa.JSON(), nullable=False),
    sa.Column('checks', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.Float(), nullable=False),
    sa.Column('updated_at', sa.Float(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant', 'key', 'name', name='uq_eval_case_name')
    )

    op.create_table('awp_eval_runs',
    sa.Column('id', sa.String(length=40), nullable=False),
    sa.Column('tenant', sa.String(length=80), nullable=False),
    sa.Column('key', sa.String(length=80), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('profile_hash', sa.String(length=80), nullable=False),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('score', sa.Float(), nullable=True),
    sa.Column('results', sa.JSON(), nullable=False),
    sa.Column('cost_usd', sa.Float(), nullable=False),
    sa.Column('duration_s', sa.Float(), nullable=True),
    sa.Column('started_by', sa.String(length=80), nullable=False),
    sa.Column('error', sa.String(length=300), nullable=True),
    sa.Column('deadline', sa.Float(), nullable=False),
    sa.Column('created_at', sa.Float(), nullable=False),
    sa.Column('finished_at', sa.Float(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_eval_run_version', 'awp_eval_runs', ['tenant', 'key', 'version', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_eval_run_version', table_name='awp_eval_runs')
    op.drop_table('awp_eval_runs')
    op.drop_table('awp_eval_cases')
    op.drop_index(op.f('ix_awp_builder_sessions_tenant'), table_name='awp_builder_sessions')
    op.drop_table('awp_builder_sessions')
    op.drop_index('ix_profile_event_key', table_name='awp_profile_events')
    op.drop_table('awp_profile_events')
    with op.batch_alter_table('awp_profiles') as batch:
        batch.drop_column('published_by')
        batch.drop_column('published_at')
