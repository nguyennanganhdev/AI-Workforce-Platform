"""Backfill CAS revisions and baseline snapshots for existing contexts.

Revision ID: 0015_shared_context_backfill
Revises: 0014_durable_team_handoffs
Create Date: 2026-10-13 00:00:01.000000
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_shared_context_backfill"
down_revision: str | None = "0014_durable_team_handoffs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _payload(value: object) -> dict:
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict):
        raise ValueError("team shared-context payload must be a JSON object")
    return value


def upgrade() -> None:
    contexts = sa.table(
        "team_shared_contexts",
        sa.column("id", sa.String(255)),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
        sa.column("payload", sa.JSON()),
        sa.column("user_id", sa.String(255)),
        sa.column("team_id", sa.String(255)),
        sa.column("state_revision", sa.Integer()),
    )
    snapshots = sa.table(
        "team_shared_context_snapshots",
        sa.column("id", sa.String(255)),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
        sa.column("payload", sa.JSON()),
        sa.column("user_id", sa.String(255)),
        sa.column("team_id", sa.String(255)),
        sa.column("state_revision", sa.Integer()),
    )
    bind = op.get_bind()
    rows = bind.execute(sa.select(contexts)).mappings().all()
    for row in rows:
        payload = _payload(row["payload"])
        state = payload.get("state")
        state_revision = state.get("revision", 0) if isinstance(state, dict) else 0
        if not isinstance(state_revision, int) or state_revision < 0:
            raise ValueError("team shared-context revision must be a non-negative int")
        if row["state_revision"] != state_revision:
            bind.execute(
                sa.update(contexts)
                .where(contexts.c.id == row["id"])
                .values(state_revision=state_revision),
            )
        if state_revision == 0:
            continue
        snapshot_id = hashlib.sha256(
            f"{row['team_id']}\0{state_revision}".encode(),
        ).hexdigest()
        exists = bind.scalar(
            sa.select(snapshots.c.id).where(snapshots.c.id == snapshot_id),
        )
        if exists is None:
            bind.execute(
                sa.insert(snapshots).values(
                    id=snapshot_id,
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    payload=payload,
                    user_id=row["user_id"],
                    team_id=row["team_id"],
                    state_revision=state_revision,
                ),
            )


def downgrade() -> None:
    # This is a data repair.  Reverting it would deliberately corrupt the CAS
    # column and discard a valid audit snapshot, so schema downgrade is a no-op.
    return
