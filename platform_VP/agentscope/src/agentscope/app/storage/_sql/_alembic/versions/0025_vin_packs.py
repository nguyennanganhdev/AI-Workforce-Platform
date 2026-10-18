"""Library packs: catalog resources granted to a pack group plus sample agents."""

from alembic import op
import sqlalchemy as sa

revision = "0025_vin_packs"
down_revision = "0024_vin_admin_revisions"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "vin_packs",
        sa.Column("tenant_id", sa.String(255), primary_key=True),
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
    )


def downgrade():
    op.drop_table("vin_packs")
