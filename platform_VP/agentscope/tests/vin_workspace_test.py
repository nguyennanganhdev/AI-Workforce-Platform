"""Server-resolved scope selection with session isolation and revision CAS."""

import pytest
from sqlalchemy import text

from vin_platform_authority_test import authority as authority  # noqa: F401
from agentscope.app.vin_platform import PlatformError
from agentscope.app.vin_platform._workspaces import state, switch


@pytest.mark.asyncio
async def test_customer_cannot_select_manager_or_other_customer_workspace(authority):
    context = await authority.context("alice", session_id="session-one")
    view = await state(authority, context, "session-one")
    assert [item.id for item in view["items"]] == ["personal:alice"]
    for target in ("personal:bob", "operations:vin:area", "administration:vin"):
        with pytest.raises(PlatformError, match="CAPABILITY_DENIED"):
            await switch(authority, context, "session-one", target, 0)
    selected = await switch(authority, context, "session-one", "personal:alice", 0)
    assert selected["workspace"]["revision"] == 1
    assert selected["view"]["billing_subject_id"] == "alice"
    assert (await state(authority, context, "session-two"))["revision"] == 0


@pytest.mark.asyncio
async def test_admin_personal_scope_transition_replay_and_stale_cas(authority):
    context = await authority.context("admin", session_id="session-one")
    assert context.workspace_id == "administration:vin"
    result = await switch(authority, context, "session-one", "personal:admin", 0)
    assert not result["view"]["capabilities"]["catalog.manage"]
    personal = await authority.context("admin", session_id="session-one")
    with pytest.raises(PlatformError, match="CAPABILITY_DENIED"):
        authority.admin(personal)
    replay = await switch(authority, personal, "session-one", "personal:admin", 0)
    assert replay["workspace"]["revision"] == 1
    with pytest.raises(PlatformError, match="REVISION_CONFLICT"):
        await switch(authority, personal, "session-one", "administration:vin", 0)
    await switch(authority, personal, "session-one", "administration:vin", 1)
    assert (await authority.context("admin", session_id="session-one")).workspace_id == "administration:vin"


@pytest.mark.asyncio
async def test_current_role_and_area_revoke_saved_operations_scope(authority):
    async with authority.engine.begin() as db:
        await db.execute(text("UPDATE auth_users SET role='AREA_MANAGER',domain_id='vh',area_id='area-one' WHERE id='bob'"))
    manager = await authority.context("bob", session_id="manager-session")
    assert manager.workspace_id == "operations:vh:area-one"
    assert (await authority.capabilities(manager))["capabilities"]["management.read"]
    await switch(authority, manager, "manager-session", manager.workspace_id, 0)
    async with authority.engine.begin() as db:
        await db.execute(text("UPDATE auth_users SET area_id='area-two' WHERE id='bob'"))
    with pytest.raises(PlatformError, match="AUTHORIZATION_REVOKED"):
        async with authority.engine.begin() as db:
            await authority.assert_active(db, manager)
    current = await authority.context("bob", session_id="manager-session")
    assert current.workspace_id == "personal:bob"
    assert not (await authority.capabilities(current))["capabilities"]["management.read"]
