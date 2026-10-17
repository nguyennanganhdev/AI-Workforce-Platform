"""SQL repository for assets; every mutation joins the canonical UOW."""

from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import insert, select, update

from ._tables import assets


class SqlAssetRepository:
    def __init__(self, uows: Any) -> None:
        self._uows = uows

    @asynccontextmanager
    async def transaction(self):
        async with self._uows() as uow:
            yield uow
            await uow.commit()

    async def insert(self, record: dict[str, Any], uow: Any) -> None:
        await uow.execute(insert(assets).values(**record))

    async def get(
        self, asset_id: str, uow: Any, *, lock: bool = False
    ) -> dict[str, Any] | None:
        query = select(assets).where(assets.c.id == asset_id)
        if lock:
            query = query.with_for_update()
        row = (await uow.execute(query)).mappings().first()
        return dict(row) if row is not None else None

    async def update(self, asset_id: str, values: dict[str, Any], uow: Any) -> bool:
        result = await uow.execute(
            update(assets).where(assets.c.id == asset_id).values(**values)
        )
        return result.rowcount == 1


__all__ = ["SqlAssetRepository"]
