"""Session-bound scope selection; never changes resource owner or billing user."""

from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select, text, update

from . import _tables as t
from ._contracts import PlatformError, WorkspaceView


def options(row):
    result = [WorkspaceView(id="personal:" + row["id"], kind="personal", label="Cá nhân")]
    if row["role"] == "AREA_MANAGER" and row["domain_id"] and row["area_id"]:
        result.append(WorkspaceView(id="operations:" + row["domain_id"] + ":" + row["area_id"],
            kind="operations", label="Vận hành", domain_id=row["domain_id"], area_id=row["area_id"]))
    if row["role"] == "PLATFORM_ADMIN" or row["role"] == "DOMAIN_ADMIN" and row["domain_id"]:
        result.append(WorkspaceView(id="administration:" + row["tenant_id"] + (
            ":" + row["domain_id"] if row["role"] == "DOMAIN_ADMIN" else ""),
            kind="administration", label="Quản trị", domain_id=row["domain_id"]))
    return result


async def account(db, user_id):
    return (await db.execute(text("SELECT id,tenant_id,role,status,domain_id,area_id FROM auth_users WHERE id=:u"),
        {"u": user_id})).mappings().first()


def selection_id(context, session_id):
    if not session_id or session_id == "legacy":
        raise PlatformError("AUTH_REQUIRED", 401)
    return str(uuid5(NAMESPACE_URL, ":".join(("vin-workspace", context.tenant_id, context.initiator_user_id, session_id))))


async def selected(db, context, session_id):
    return (await db.execute(select(t.automation).where(t.automation.c.id == selection_id(context, session_id),
        t.automation.c.tenant_id == context.tenant_id, t.automation.c.user_id == context.initiator_user_id,
        t.automation.c.kind == "workspace-session"))).mappings().first()


async def state(authority, context, session_id):
    async with authority.engine.begin() as db:
        row = await account(db, context.initiator_user_id)
        await authority.assert_active(db, context, require_eligible=False)
        items = options(row)
        saved = await selected(db, context, session_id)
        ident = saved["data"]["workspace_id"] if saved else context.workspace_id
        if ident not in {item.id for item in items}:
            ident = items[0].id
        return {"contract_version": "vin-platform-1", "active_workspace_id": ident,
            "revision": saved["revision"] if saved else 0,
            "authorization_revision": context.authorization_revision, "items": items}


async def switch(authority, context, session_id, workspace_id, expected_revision):
    async with authority.engine.begin() as db:
        await authority.assert_active(db, context, require_eligible=False)
        row = await account(db, context.initiator_user_id)
        if workspace_id not in {item.id for item in options(row)}:
            raise PlatformError("CAPABILITY_DENIED", 403)
        saved = await selected(db, context, session_id)
        if saved and saved["revision"] == expected_revision + 1 and saved["data"]["workspace_id"] == workspace_id:
            pass  # Lost response: replay the exact transition receipt.
        elif saved:
            changed = await db.execute(update(t.automation).where(t.automation.c.id == saved["id"],
                t.automation.c.revision == expected_revision).values(data={"workspace_id": workspace_id},
                    revision=expected_revision + 1))
            if changed.rowcount != 1:
                raise PlatformError("REVISION_CONFLICT", 409)
        elif expected_revision != 0:
            raise PlatformError("REVISION_CONFLICT", 409)
        else:
            from ._quota import insert_once
            created = await insert_once(db, t.automation, {"id": selection_id(context, session_id),
                "tenant_id": context.tenant_id, "user_id": context.initiator_user_id,
                "kind": "workspace-session", "data": {"workspace_id": workspace_id}, "revision": 1})
            if not created:
                raise PlatformError("REVISION_CONFLICT", 409)
        await authority.audit(db, context, "workspace.selected", workspace_id)
    fresh = await authority.context(context.initiator_user_id, session_id=session_id)
    return {"workspace": await state(authority, fresh, session_id), "view": await authority.capabilities(fresh)}
