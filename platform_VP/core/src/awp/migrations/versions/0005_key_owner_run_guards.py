"""One tenant per profile key, one running evaluation per version, and the cases a run ran.

`awp_profile_keys` gets the holder of every key there is: the tenant whose version is published, else one with a draft,
else one with retired versions only (the same order the old read-before-insert rule gave). Where two tenants already
hold the same key, the one that sorts first keeps it; the other's rows stay and can no longer be published.

A run that is `running` while a migration runs has no process (migrations run before the processes start): it ends as
an error, which also makes room for the index that allows one running run per version.

Revision ID: 0005_key_owner_run_guards
Revises: 0004_builder_evals_release
Create Date: 2026-10-11 23:30:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0005_key_owner_run_guards'
down_revision: Union[str, None] = '0004_builder_evals_release'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('awp_profile_keys',
    sa.Column('key', sa.String(length=80), nullable=False),
    sa.Column('tenant', sa.String(length=80), nullable=False),
    sa.PrimaryKeyConstraint('key')
    )
    for held in ("status = 'published'", "status <> 'retired'", "1 = 1"):
        op.execute(
            "insert into awp_profile_keys (key, tenant) select key, min(tenant) from awp_profiles "
            f"where {held} and key not in (select key from awp_profile_keys) group by key")

    op.execute("update awp_eval_runs set status = 'error', error = 'interrupted: the platform was upgraded' "
               "where status = 'running'")
    with op.batch_alter_table('awp_eval_runs') as batch:
        batch.add_column(sa.Column('cases_hash', sa.String(length=80), nullable=True))
    op.create_index('uq_eval_run_running', 'awp_eval_runs', ['tenant', 'key', 'version'], unique=True,
                    sqlite_where=sa.text("status = 'running'"), postgresql_where=sa.text("status = 'running'"))


def downgrade() -> None:
    op.drop_index('uq_eval_run_running', table_name='awp_eval_runs')
    with op.batch_alter_table('awp_eval_runs') as batch:
        batch.drop_column('cases_hash')
    op.drop_table('awp_profile_keys')
