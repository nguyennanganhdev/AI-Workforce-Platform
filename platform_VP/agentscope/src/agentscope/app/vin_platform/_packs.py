"""Library packs (PM 19/10): a pack group holds catalog grants; joining it installs the pack."""

import re
from uuid import uuid4

from sqlalchemy import insert, select, update

from . import _tables as t
from ._contracts import Pack, PackView, PlatformError, ResourceGrant

PACK_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
PERMISSIONS = ["view", "bind", "execute"]


def pack_group(pack_id: str) -> str:
    return "pack:" + pack_id


async def save_pack(service, context, pack_id: str, pack: Pack, *, expected_revision: int | None = None) -> int:
    """Create or replace a pack and grant its catalog resources to the pack group."""
    service.admin(context)
    if not PACK_ID.match(pack_id):
        raise PlatformError("INVALID_PACK_ID", 422)
    async with service.engine.begin() as db:
        await service.assert_active(db, context, require_eligible=False)
        for catalog_id in pack.catalog_ids:
            found = (await db.execute(select(t.catalog.c.id).where(
                t.catalog.c.tenant_id == context.tenant_id, t.catalog.c.id == catalog_id))).scalar_one_or_none()
            if found is None:
                raise PlatformError("RESOURCE_NOT_FOUND", 404, catalog_id=catalog_id)
        row = (await db.execute(select(t.packs).where(t.packs.c.tenant_id == context.tenant_id,
            t.packs.c.id == pack_id).with_for_update())).mappings().first()
        # The admin who saves the pack owns its sample agents.
        data = {**pack.model_dump(exclude={"active"}), "owner_id": context.initiator_user_id}
        if row is None:
            if expected_revision not in (None, 0):
                raise PlatformError("REVISION_CONFLICT", 409)
            revision = 1
            await db.execute(insert(t.packs).values(tenant_id=context.tenant_id, id=pack_id, data=data,
                active=pack.active, revision=revision))
        else:
            if expected_revision is not None and expected_revision != row["revision"]:
                raise PlatformError("REVISION_CONFLICT", 409)
            revision = row["revision"] + 1
            await db.execute(update(t.packs).where(t.packs.c.tenant_id == context.tenant_id,
                t.packs.c.id == pack_id).values(data=data, active=pack.active, revision=revision))
        granted = set((await db.execute(select(t.grants.c.catalog_id).where(
            t.grants.c.tenant_id == context.tenant_id, t.grants.c.subject_kind == "group",
            t.grants.c.subject_id == pack_group(pack_id), t.grants.c.active.is_(True)))).scalars().all())
        await service.audit(db, context, "pack.saved", pack_id, revision=revision)
    for catalog_id in pack.catalog_ids:
        if catalog_id not in granted:
            await service.grant(context, ResourceGrant(catalog_id=catalog_id, subject_kind="group",
                subject_id=pack_group(pack_id), permissions=PERMISSIONS))
    return revision


async def list_packs(service, context, *, include_inactive: bool = False) -> list[PackView]:
    async with service.engine.begin() as db:
        await service.assert_active(db, context, require_eligible=False)
        query = select(t.packs).where(t.packs.c.tenant_id == context.tenant_id)
        if not include_inactive:
            query = query.where(t.packs.c.active.is_(True))
        rows = (await db.execute(query.order_by(t.packs.c.id))).mappings().all()
        groups = set(await service.groups(db, context.tenant_id, context.initiator_user_id))
    return [PackView(id=row["id"], revision=row["revision"], active=row["active"],
        installed=pack_group(row["id"]) in groups,
        **{k: v for k, v in row["data"].items() if k in Pack.model_fields and k != "active"}) for row in rows]


async def get_pack(service, context, pack_id: str) -> tuple[PackView, str]:
    """An active pack and the owner of its sample agents."""
    async with service.engine.begin() as db:
        row = (await db.execute(select(t.packs).where(t.packs.c.tenant_id == context.tenant_id,
            t.packs.c.id == pack_id, t.packs.c.active.is_(True)))).mappings().first()
    if row is None:
        raise PlatformError("PACK_NOT_FOUND", 404)
    view = PackView(id=row["id"], revision=row["revision"], active=True,
        **{k: v for k, v in row["data"].items() if k in Pack.model_fields and k != "active"})
    return view, row["data"].get("owner_id", "")


async def set_installed(service, context, pack_id: str, installed: bool) -> None:
    """Join or leave the pack group for the caller only; idempotent."""
    await get_pack(service, context, pack_id)
    async with service.engine.begin() as db:
        await service.assert_active(db, context, require_eligible=installed)
        where = (t.memberships.c.tenant_id == context.tenant_id,
                 t.memberships.c.user_id == context.initiator_user_id,
                 t.memberships.c.group_id == pack_group(pack_id), t.memberships.c.active.is_(True))
        current = (await db.execute(select(t.memberships.c.id).where(*where))).scalars().all()
        if installed and not current:
            await db.execute(insert(t.memberships).values(id=uuid4().hex, tenant_id=context.tenant_id,
                user_id=context.initiator_user_id, group_id=pack_group(pack_id), active=True))
        if not installed and current:
            await db.execute(update(t.memberships).where(*where).values(active=False,
                revision=t.memberships.c.revision + 1))
        await service.audit(db, context, "pack.installed" if installed else "pack.removed", pack_id)
