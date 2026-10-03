"""Create the Vinhomes ActionApproval table.

Revision ID: 0005_vh_action_approval
Revises: 0004_vh_action_request
Create Date: 2026-09-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_vh_action_approval"
down_revision: Union[str, None] = "0004_vh_action_request"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vh_action_approval",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("action_request_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("action_payload_hash", sa.String(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "APPROVED",
                "REJECTED",
                "EXPIRED",
                name="ck_vh_action_approval_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("requested_by_id", sa.String(), nullable=False),
        sa.Column("reviewer_id", sa.String(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("version", sa.BigInteger(), server_default=sa.text("1"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_vh_action_approval"),
        sa.ForeignKeyConstraint(
            ["action_request_id"],
            ["vh_action_request.id"],
            name="fk_vh_action_approval_action_request_id_vh_action_request",
        ),
    )
    op.create_index(
        "ix_vh_action_approval_status_expires_at",
        "vh_action_approval",
        ["status", "expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_vh_action_approval_status_expires_at", table_name="vh_action_approval"
    )
    op.drop_table("vh_action_approval")
