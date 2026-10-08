"""Add explicitly demo-only TECHNICAL and SECURITY Task domains.

Revision ID: 0015_technical_task_domain
Revises: 0014_vh_outbox_message
Create Date: 2026-09-30
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0015_technical_task_domain"
down_revision: Union[str, None] = "0014_vh_outbox_message"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("vh_task") as batch_op:
        batch_op.drop_constraint("ck_vh_task_domain_type", type_="check")
        batch_op.create_check_constraint(
            "ck_vh_task_domain_type",
            "domain_type IN ('SANITATION', 'LANDSCAPE', 'TECHNICAL', 'SECURITY')",
        )


def downgrade() -> None:
    with op.batch_alter_table("vh_task") as batch_op:
        batch_op.drop_constraint("ck_vh_task_domain_type", type_="check")
        batch_op.create_check_constraint(
            "ck_vh_task_domain_type",
            "domain_type IN ('SANITATION', 'LANDSCAPE')",
        )
