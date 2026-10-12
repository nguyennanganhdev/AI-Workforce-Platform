"""The process that sends an operation (several processes on one database, slice P5b).

`wf_operations.node` is the process that marked the operation `sent` and holds the live call. While that process says
it lives (its `node:<id>` row in `wf_leases`), no other process takes the operation for the leftover of a crash. Rows
written before this revision have no node and are treated as before.

Revision ID: 0006_operation_node
Revises: 0005_key_owner_run_guards
Create Date: 2026-10-12 12:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0006_operation_node'
down_revision: Union[str, None] = '0005_key_owner_run_guards'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('wf_operations') as batch:
        batch.add_column(sa.Column('node', sa.String(length=40), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('wf_operations') as batch:
        batch.drop_column('node')
