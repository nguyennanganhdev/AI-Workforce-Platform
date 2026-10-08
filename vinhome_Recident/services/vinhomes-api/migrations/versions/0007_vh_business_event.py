"""Create the append-only Vinhomes business event stream.

Revision ID: 0007_vh_business_event
Revises: 0006_vh_work_order
Create Date: 2026-09-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_vh_business_event"
down_revision: Union[str, None] = "0006_vh_work_order"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vh_business_event",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("incident_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("subject_type", sa.String(), nullable=False),
        sa.Column("subject_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("actor_type", sa.String(), nullable=False),
        sa.Column("actor_id", sa.String(), nullable=False),
        sa.Column("actor_version", sa.BigInteger(), nullable=True),
        sa.Column(
            "data",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("correlation_id", sa.String(), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_vh_business_event"),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["vh_incident.id"],
            name="fk_vh_business_event_incident_id_vh_incident",
        ),
    )
    op.create_index(
        "ix_vh_business_event_incident_occurred_at",
        "vh_business_event",
        ["incident_id", sa.text("occurred_at DESC")],
    )

    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            CREATE FUNCTION vh_reject_business_event_mutation()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'vh_business_event is append-only'
                    USING ERRCODE = '55000';
            END;
            $$ LANGUAGE plpgsql
            """
        )
        op.execute(
            """
            CREATE TRIGGER trg_vh_business_event_append_only
            BEFORE UPDATE OR DELETE ON vh_business_event
            FOR EACH ROW EXECUTE FUNCTION vh_reject_business_event_mutation()
            """
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "DROP TRIGGER trg_vh_business_event_append_only ON vh_business_event"
        )
        op.execute("DROP FUNCTION vh_reject_business_event_mutation()")
    op.drop_index(
        "ix_vh_business_event_incident_occurred_at",
        table_name="vh_business_event",
    )
    op.drop_table("vh_business_event")
