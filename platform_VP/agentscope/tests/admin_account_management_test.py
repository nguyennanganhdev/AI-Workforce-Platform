"""The platform Admin manages customer accounts: list, lock/unlock, delete."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from agentscope.app.vin_platform import PlatformError
from vin_fixtures import authority  # noqa: F401


async def _session(authority, user_id):
    now = datetime.now(UTC)
    async with authority.engine.begin() as db:
        await db.execute(text("""INSERT INTO auth_sessions (id,user_id,tenant_id,family_id,refresh_token_hash,expires_at,created_at)
            VALUES (:id,:u,'vin',:id,'offline-hash',:exp,:now)"""),
            {"id": "s-" + user_id, "u": user_id, "exp": now + timedelta(days=1), "now": now})


async def _row(authority, user_id):
    async with authority.engine.connect() as db:
        user = (await db.execute(text("SELECT email, username, status FROM auth_users WHERE id=:u"), {"u": user_id})).mappings().one()
        revoked = (await db.execute(text("SELECT revoked_at FROM auth_sessions WHERE user_id=:u"), {"u": user_id})).scalar()
    return dict(user), revoked


@pytest.mark.asyncio
async def test_admin_lists_accounts_with_email_last_sign_in_and_search(authority):
    await _session(authority, "alice")
    admin = await authority.context("admin")
    page = await authority.administration.accounts(admin, q="ALICE")
    assert [item["email"] for item in page["items"]] == ["alice@fixture.invalid"]
    item = page["items"][0]
    assert item["last_login_at"] is not None and item["created_at"] is not None and item["month_tokens"] == 0
    other_tenant = {i["user_id"] for i in (await authority.administration.accounts(admin))["items"]}
    assert "other" not in other_tenant


@pytest.mark.asyncio
async def test_locking_ends_sessions_and_blocks_the_account_until_unlocked(authority):
    await _session(authority, "alice")
    admin = await authority.context("admin")
    await authority.administration.set_account_active(admin, "alice", False)
    user, revoked = await _row(authority, "alice")
    assert user["status"] == "suspended" and revoked is not None
    with pytest.raises(PlatformError, match="AUTH_REQUIRED"):
        await authority.quota.policy(await authority.context("alice"))
    await authority.administration.set_account_active(admin, "alice", True)
    assert (await _row(authority, "alice"))[0]["status"] == "active"


@pytest.mark.asyncio
async def test_delete_anonymises_hides_and_can_be_repeated(authority):
    await _session(authority, "bob")
    admin = await authority.context("admin")
    await authority.administration.delete_account(admin, "bob")
    user, revoked = await _row(authority, "bob")
    assert user == {"email": "deleted+bob@invalid", "username": "deleted-bob", "status": "deleted"}
    assert revoked is not None
    assert "bob" not in {i["user_id"] for i in (await authority.administration.accounts(admin))["items"]}
    await authority.administration.delete_account(admin, "bob")  # retry re-runs the purge only
    with pytest.raises(PlatformError, match="ACCOUNT_NOT_FOUND"):
        await authority.administration.set_account_active(admin, "bob", True)


@pytest.mark.asyncio
async def test_admin_cannot_lock_or_delete_itself_or_another_administrator(authority):
    admin = await authority.context("admin")
    for action in (lambda: authority.administration.set_account_active(admin, "admin", False),
                   lambda: authority.administration.delete_account(admin, "admin")):
        with pytest.raises(PlatformError, match="ACCOUNT_PROTECTED"):
            await action()
    with pytest.raises(PlatformError, match="ACCOUNT_NOT_FOUND"):
        await authority.administration.delete_account(admin, "other")  # another tenant
    with pytest.raises(PlatformError):
        await authority.administration.set_account_active(await authority.context("alice"), "bob", False)
