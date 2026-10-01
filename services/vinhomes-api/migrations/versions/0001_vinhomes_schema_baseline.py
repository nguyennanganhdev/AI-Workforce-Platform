"""Establish the initial Vinhomes migration revision.

Revision ID: 0001_vinhomes_schema_baseline
Revises:
Create Date: 2026-09-28
"""

from typing import Sequence, Union

revision: str = "0001_vinhomes_schema_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No domain tables are created until their owning module is implemented."""


def downgrade() -> None:
    """Return to the empty schema baseline."""
