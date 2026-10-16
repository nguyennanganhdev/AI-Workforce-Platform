"""Versioned profiles: draft -> published -> retired. Publishing is explicit, and every change of a key leaves a
line in its history (`awp_profile_events`), written in the same transaction."""
from __future__ import annotations

import time
import uuid

from sqlalchemy import func, insert, select, update
from sqlalchemy.exc import IntegrityError

from .. import db
from .models import AgentProfile, ProfileRecord

RESERVED = "awp_"  # keys of the platform's own profiles (the leader of an evaluation): no tenant can make one


class ProfileError(ValueError):
    pass


class ProfileDenied(ProfileError):
    """The caller may not do this to the profile, whatever state it is in (403, where a ProfileError is a 409)."""


def _rec(row) -> ProfileRecord:
    return ProfileRecord(
        id=row.id, tenant=row.tenant, key=row.key, version=row.version,
        status=row.status, profile=AgentProfile.model_validate(row.data),
        created_at=row.created_at, published_at=row.published_at, published_by=row.published_by)


async def record(conn, tenant: str, key: str, version: int | None, kind: str, actor: str = "",
                 detail: dict | None = None) -> None:
    """One line of a key's history, in the transaction of the change it tells of."""
    await conn.execute(insert(db.profile_events).values(
        tenant=tenant, key=key, version=version, kind=kind, actor=actor[:80], detail=detail or {},
        created_at=time.time()))


class ProfileStore:
    def __init__(self, database: db.Database) -> None:
        self._db = database

    async def create_draft(self, tenant: str, profile: AgentProfile, *, by: str = "", detail: dict | None = None,
                           conn=None) -> ProfileRecord:
        """The next version of the key. Two tenants, or two drafts, that take a NEW key at the same moment meet on a
        unique key (there is no row yet that could be locked): the loser tries again and finds what the winner made.

        `conn`: the caller's transaction (the builder's apply), in which the draft stands or falls with everything
        else; an IntegrityError is then the caller's to handle."""
        if profile.key.startswith(RESERVED):
            raise ProfileError(f"profile keys that start with {RESERVED!r} belong to the platform")
        if conn is not None:
            return await self._draft(conn, tenant, profile, by, detail)
        for _ in range(12):
            try:
                async with self._db.engine.begin() as own:
                    return await self._draft(own, tenant, profile, by, detail)
            except IntegrityError:
                continue
        raise ProfileError("too many drafts of this key are being made at once; try again")

    async def _own(self, conn, tenant: str, key: str) -> None:
        """Make `tenant` the holder of `key`, or refuse. A key belongs to one tenant at a time (the live templates are
        keyed by the key alone): another tenant takes it only when nothing of the holder's is a draft or published.
        Every writer of a key locks its row first, so the holder cannot change between this check and the write."""
        k = db.profile_keys.c
        if conn.dialect.name == "postgresql":
            await conn.execute(select(k.key).where(k.key == key).with_for_update())
        else:  # SQLite: the first write takes the file's write lock
            await conn.execute(update(db.profile_keys).where(k.key == key).values(tenant=k.tenant))
        holder = (await conn.execute(select(k.tenant).where(k.key == key))).scalar()
        if holder == tenant:
            return
        other = (await conn.execute(select(db.profiles.c.tenant).where(
            db.profiles.c.key == key, db.profiles.c.tenant != tenant, db.profiles.c.status != "retired").limit(1))).first()
        if other:
            raise ProfileError(f"profile key {key!r} is used by another tenant")
        if holder is None:
            await conn.execute(insert(db.profile_keys).values(key=key, tenant=tenant))
        else:
            await conn.execute(update(db.profile_keys).where(k.key == key).values(tenant=tenant))

    async def _draft(self, conn, tenant: str, profile: AgentProfile, by: str, detail: dict | None) -> ProfileRecord:
        await self._own(conn, tenant, profile.key)
        latest = (await conn.execute(select(func.max(db.profiles.c.version)).where(
            db.profiles.c.tenant == tenant, db.profiles.c.key == profile.key))).scalar()
        version = (latest or 0) + 1
        rid = "prof_" + uuid.uuid4().hex[:12]
        now = time.time()
        await conn.execute(insert(db.profiles).values(
            id=rid, tenant=tenant, key=profile.key, version=version,
            status="draft", data=profile.model_dump(mode="json"), created_at=now))
        await record(conn, tenant, profile.key, version, "create", by, detail)
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

    async def publish(self, tenant: str, key: str, version: int, checked: AgentProfile | None = None, *,
                      by: str = "", override_reason: str | None = None, rollback: bool = False,
                      replace_only: bool = False) -> ProfileRecord:
        """One publisher of a key at a time: the key's rows are locked before any is read, so a second publisher sees
        what the first did (the unique index `uq_profile_published` is the net under that). `checked`: the profile
        the caller validated; a draft edited since is not published on the strength of that check.

        This is the bare act. Whether a version MAY go live (it passed its evaluation, or a person overrode that
        with a reason) is decided in `awp.release`, its only caller outside tests. `rollback` publishes a retired
        version again, which a plain publish refuses; it too is refused once another tenant holds the key.
        `replace_only`: only in place of a version that is live now (`ProfileDenied` when the key was retired)."""
        mine = (db.profiles.c.tenant == tenant, db.profiles.c.key == key)
        try:
            async with self._db.engine.begin() as conn:
                if conn.dialect.name == "postgresql":
                    await conn.execute(select(db.profiles.c.id).where(*mine).order_by(db.profiles.c.version).with_for_update())
                else:  # SQLite: the first write takes the file's write lock
                    await conn.execute(update(db.profiles).where(*mine).values(status=db.profiles.c.status))
                row = (await conn.execute(select(db.profiles).where(*mine, db.profiles.c.version == version))).first()
                if row is None:
                    raise ProfileError("no such profile version")
                await self._own(conn, tenant, key)
                if rollback and row.status != "retired":
                    raise ProfileError("only a version that was published before and is retired now can be rolled back to")
                if row.status == "retired" and not rollback:
                    raise ProfileError("a retired version cannot be published again; roll back to it instead")
                if checked is not None and AgentProfile.model_validate(row.data) != checked:
                    raise ProfileError("the draft was edited while it was being checked; publish it again")
                if row.status == "published":
                    return _rec(row)  # live already: nothing changes and the history gets no new line
                was = (await conn.execute(select(db.profiles.c.version).where(
                    *mine, db.profiles.c.status == "published"))).scalar()
                if replace_only and was is None:
                    raise ProfileDenied("no version of this agent is live: bringing a retired agent back is the admin's")
                await conn.execute(update(db.profiles).where(*mine, db.profiles.c.status == "published",
                                                             db.profiles.c.id != row.id).values(status="retired"))
                await conn.execute(update(db.profiles).where(db.profiles.c.id == row.id).values(
                    status="published", published_at=time.time(), published_by=by[:80]))
                if override_reason:
                    await record(conn, tenant, key, version, "override", by, {"reason": override_reason})
                await record(conn, tenant, key, version, "rollback" if rollback else "publish", by, {"from_version": was})
        except IntegrityError:
            raise ProfileError("another version of this key was published at the same moment; try again")
        return await self.get(tenant, key, version)  # type: ignore[return-value]

    async def retire(self, tenant: str, key: str, by: str = "") -> None:
        async with self._db.engine.begin() as conn:
            was = (await conn.execute(select(db.profiles.c.version).where(
                db.profiles.c.tenant == tenant, db.profiles.c.key == key, db.profiles.c.status == "published"))).scalar()
            if was is None:
                return
            await conn.execute(update(db.profiles).where(
                db.profiles.c.tenant == tenant, db.profiles.c.key == key,
                db.profiles.c.status == "published").values(status="retired"))
            await record(conn, tenant, key, was, "retire", by)

    async def history(self, tenant: str, key: str) -> list[dict]:
        """What happened to the key, oldest first."""
        e = db.profile_events.c
        async with self._db.engine.connect() as conn:
            rows = (await conn.execute(select(db.profile_events).where(e.tenant == tenant, e.key == key)
                                       .order_by(e.id))).mappings().all()
        return [{"kind": r["kind"], "version": r["version"], "actor": r["actor"], "detail": r["detail"],
                 "at": r["created_at"]} for r in rows]

    async def note(self, tenant: str, key: str, version: int, kind: str, by: str, detail: dict) -> None:
        """A line of history for something that changed no profile row (an evaluation ended)."""
        async with self._db.engine.begin() as conn:
            await record(conn, tenant, key, version, kind, by, detail)

    async def get(self, tenant: str, key: str, version: int) -> ProfileRecord | None:
        async with self._db.engine.connect() as conn:
            row = (await conn.execute(select(db.profiles).where(
                db.profiles.c.tenant == tenant, db.profiles.c.key == key,
                db.profiles.c.version == version))).first()
        return _rec(row) if row else None

    async def latest(self, tenant: str, key: str) -> ProfileRecord | None:
        """The newest version of a key, whatever its status."""
        async with self._db.engine.connect() as conn:
            row = (await conn.execute(select(db.profiles).where(
                db.profiles.c.tenant == tenant, db.profiles.c.key == key)
                .order_by(db.profiles.c.version.desc()).limit(1))).first()
        return _rec(row) if row else None

    async def team_gaps(self, tenant: str, profile: AgentProfile) -> tuple[list[str], list[str]]:
        """A leader's team against the tenant's profiles: (keys that are no specialist of this tenant, specialists
        with no published version). The first make a leader that names people who do not exist; the second it
        cannot bring in yet."""
        missing, unpublished = [], []
        for key in profile.team:
            newest = await self.latest(tenant, key)
            if newest is None or newest.profile.role != "specialist":
                missing.append(key)
            elif await self.get_published(tenant, key) is None:
                unpublished.append(key)
        return missing, unpublished

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
