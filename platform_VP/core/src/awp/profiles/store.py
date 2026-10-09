"""Versioned profiles: draft -> published -> retired. Publishing is explicit."""
from __future__ import annotations

import time
import uuid

from sqlalchemy import func, insert, select, update

from .. import db
from .models import AgentProfile, ProfileRecord


class ProfileError(ValueError):
    pass


def _rec(row) -> ProfileRecord:
    return ProfileRecord(
        id=row.id, tenant=row.tenant, key=row.key, version=row.version,
        status=row.status, profile=AgentProfile.model_validate(row.data),
        created_at=row.created_at)


class ProfileStore:
    def __init__(self, database: db.Database) -> None:
        self._db = database

    async def create_draft(self, tenant: str, profile: AgentProfile) -> ProfileRecord:
        async with self._db.engine.begin() as conn:
            other = (await conn.execute(select(db.profiles.c.tenant).where(
                db.profiles.c.key == profile.key, db.profiles.c.tenant != tenant,
                db.profiles.c.status != "retired").limit(1))).first()
            if other:
                raise ProfileError(f"profile key {profile.key!r} is used by another tenant")
            latest = (await conn.execute(select(func.max(db.profiles.c.version)).where(
                db.profiles.c.tenant == tenant, db.profiles.c.key == profile.key))).scalar()
            version = (latest or 0) + 1
            rid = "prof_" + uuid.uuid4().hex[:12]
            now = time.time()
            await conn.execute(insert(db.profiles).values(
                id=rid, tenant=tenant, key=profile.key, version=version,
                status="draft", data=profile.model_dump(mode="json"), created_at=now))
        return ProfileRecord(id=rid, tenant=tenant, key=profile.key, version=version,
                             status="draft", profile=profile, created_at=now)

    async def update_draft(self, tenant: str, key: str, version: int,
                           profile: AgentProfile) -> ProfileRecord:
        if profile.key != key:
            raise ProfileError("the key of a profile cannot change")
        async with self._db.engine.begin() as conn:
            res = await conn.execute(update(db.profiles).where(
                db.profiles.c.tenant == tenant, db.profiles.c.key == key,
                db.profiles.c.version == version, db.profiles.c.status == "draft",
            ).values(data=profile.model_dump(mode="json")))
            if res.rowcount == 0:
                raise ProfileError("only a draft can be edited; create a new draft instead")
        return await self.get(tenant, key, version)  # type: ignore[return-value]

    async def publish(self, tenant: str, key: str, version: int) -> ProfileRecord:
        async with self._db.engine.begin() as conn:
            row = (await conn.execute(select(db.profiles).where(
                db.profiles.c.tenant == tenant, db.profiles.c.key == key,
                db.profiles.c.version == version))).first()
            if row is None:
                raise ProfileError("no such profile version")
            if row.status == "retired":
                raise ProfileError("a retired version cannot be published again")
            await conn.execute(update(db.profiles).where(
                db.profiles.c.tenant == tenant, db.profiles.c.key == key,
                db.profiles.c.status == "published").values(status="retired"))
            await conn.execute(update(db.profiles).where(
                db.profiles.c.id == row.id).values(status="published"))
        return await self.get(tenant, key, version)  # type: ignore[return-value]

    async def retire(self, tenant: str, key: str) -> None:
        async with self._db.engine.begin() as conn:
            await conn.execute(update(db.profiles).where(
                db.profiles.c.tenant == tenant, db.profiles.c.key == key,
                db.profiles.c.status == "published").values(status="retired"))

    async def get(self, tenant: str, key: str, version: int) -> ProfileRecord | None:
        async with self._db.engine.connect() as conn:
            row = (await conn.execute(select(db.profiles).where(
                db.profiles.c.tenant == tenant, db.profiles.c.key == key,
                db.profiles.c.version == version))).first()
        return _rec(row) if row else None

    async def get_published(self, tenant: str, key: str) -> ProfileRecord | None:
        async with self._db.engine.connect() as conn:
            row = (await conn.execute(select(db.profiles).where(
                db.profiles.c.tenant == tenant, db.profiles.c.key == key,
                db.profiles.c.status == "published"))).first()
        return _rec(row) if row else None

    async def list(self, tenant: str, status: str | None = None) -> list[ProfileRecord]:
        q = select(db.profiles).where(db.profiles.c.tenant == tenant)
        if status:
            q = q.where(db.profiles.c.status == status)
        async with self._db.engine.connect() as conn:
            rows = await conn.execute(q.order_by(db.profiles.c.key, db.profiles.c.version))
            return [_rec(r) for r in rows]

    async def all_published(self) -> list[ProfileRecord]:
        async with self._db.engine.connect() as conn:
            rows = await conn.execute(select(db.profiles).where(
                db.profiles.c.status == "published"))
            return [_rec(r) for r in rows]
