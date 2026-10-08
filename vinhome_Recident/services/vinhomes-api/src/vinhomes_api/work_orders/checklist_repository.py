"""Tenant-scoped reads for versioned checklist definitions."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.checklist import Checklist, ChecklistVersion


class ChecklistRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_version_for_tenant(
        self, *, tenant_id: UUID, checklist_version_id: UUID
    ) -> tuple[Checklist, ChecklistVersion] | None:
        row = await self.session.execute(
            select(Checklist, ChecklistVersion)
            .join(ChecklistVersion, ChecklistVersion.checklist_id == Checklist.id)
            .where(
                Checklist.tenant_id == tenant_id,
                ChecklistVersion.id == checklist_version_id,
            )
        )
        result = row.one_or_none()
        if result is None:
            return None
        return result[0], result[1]
