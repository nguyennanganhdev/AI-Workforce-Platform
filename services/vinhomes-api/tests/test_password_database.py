"""Opt-in HTTP checks against local password auth; temporary accounts are removed.

Run VINHOMES_PASSWORD_TEST=1 only on the locally bootstrapped deployment.
No test passwords are printed or retained as application fixtures.
"""
import asyncio
import os
from pathlib import Path
import secrets
from uuid import uuid4

import asyncpg
import httpx
import pytest

pytestmark = pytest.mark.skipif(os.getenv("VINHOMES_PASSWORD_TEST") != "1", reason="Local password deployment test is opt-in")
ROOT = Path(__file__).resolve().parents[1]


class PrivateURL(str):
    def __repr__(self):
        return "'<local database URL redacted>'"


@pytest.fixture
def clients():
    values = dict(line.split(": ",1) for line in (ROOT/".local-connected/initial-admin.txt").read_text().splitlines() if ": " in line)
    owner = PrivateURL(dict(line.split("=",1) for line in (ROOT/".local-connected/migration.env").read_text().splitlines() if "=" in line)["DATABASE_URL"])
    assert "@127.0.0.1:5544/vinhomes_connected" in owner
    admin = httpx.Client(base_url="http://127.0.0.1:3020/api/business",timeout=20)
    user = httpx.Client(base_url="http://127.0.0.1:3011/api/business",timeout=20)
    assert admin.get("/health").json()["authMode"] == "password"
    assert admin.post("/auth/login",json={"identifier":values["Login"],"password":values["Password"]}).status_code == 200
    assert admin.get("/auth/session").json()["administrator"] is True
    created=[]
    try:
        yield admin,user,created,owner
    finally:
        admin.post("/auth/logout")
        admin.close();user.close()
        async def clean():
            db=await asyncpg.connect(owner)
            try:
                async with db.transaction():
                    for uid in created:
                        await db.execute("delete from sessions where user_id=$1",uid)
                        await db.execute("delete from channel_memberships where user_id=$1",uid)
                        await db.execute("delete from scoped_user_roles where membership_id in(select id from tenant_memberships where user_id=$1)",uid)
                        await db.execute("delete from tenant_memberships where user_id=$1",uid)
                        await db.execute("delete from accounts where user_id=$1",uid)
                        await db.execute("delete from users where id=$1",uid)
            finally: await db.close()
        asyncio.run(clean())


def test_login_registration_rbac_revocation_and_hash_storage(clients):
    admin,user,created,owner=clients
    assert user.get("/auth/session").status_code == 401
    assert user.get("/operations/me",headers={"X-Demo-Actor":"admin"}).status_code == 401
    email=f"auth-check-{uuid4()}@example.invalid"
    password=secrets.token_urlsafe(20)
    assert user.post("/auth/register",json={"email":email,"name":"Temporary auth check","password":password,"role":"admin"}).status_code == 201
    result=user.post("/auth/login",json={"identifier":email,"password":password})
    assert result.status_code == 200
    uid=result.json()["user"]["id"];created.append(uid)
    assert user.get("/auth/session").json()["membershipStatus"] == "pending"
    assert user.get("/auth/session").json()["administrator"] is False
    assert "httponly" in result.headers["set-cookie"].lower()
    assert "samesite=lax" in result.headers["set-cookie"].lower()
    assert user.get("/auth/accounts").status_code == 403
    assert user.get("/operations/me").status_code == 403
    assert user.get("/resident/me").status_code == 403  # pending membership
    assert admin.patch(f"/auth/accounts/{uid}",json={"role":"customer","status":"active"}).status_code == 200
    assert user.get("/auth/session").status_code == 401  # grant changes revoke old sessions
    assert user.post("/auth/login",json={"identifier":email,"password":"wrong-password"}).status_code == 401
    assert user.post("/auth/login",json={"identifier":email,"password":password}).status_code == 200
    assert user.get("/auth/session").json()["membershipStatus"] == "active"
    assert user.get("/resident/me").json()["units"] == []
    assert user.get("/operations/me").status_code == 403
    assert admin.patch(f"/auth/accounts/{uid}",json={"role":"staff","status":"active"}).status_code == 200
    assert user.post("/auth/login",json={"identifier":email,"password":password}).status_code == 200
    assert user.get("/operations/me").json()["role"] == "staff"
    assert user.get("/auth/accounts").status_code == 403
    assert user.get("/tickets").json()["items"] == []
    async def inspect():
        db=await asyncpg.connect(owner)
        try:
            stored=await db.fetchval("select password from accounts where user_id=$1",uid)
            tokens=await db.fetch("select token from sessions where user_id=$1",uid)
            assert stored.startswith("scrypt-v1$") and password not in stored
            assert all(row["token"].startswith("vinhomes-v1:") and row["token"] != user.cookies.get("vinhomes_session") for row in tokens)
        finally:await db.close()
    asyncio.run(inspect())
    replacement=secrets.token_urlsafe(20)
    assert user.post("/auth/change-password",json={"current_password":password,"new_password":replacement}).status_code == 200
    assert user.get("/auth/session").status_code == 401
    assert user.post("/auth/login",json={"identifier":email,"password":password}).status_code == 401
    assert user.post("/auth/login",json={"identifier":email,"password":replacement}).status_code == 200
    assert admin.patch(f"/auth/accounts/{uid}",json={"role":"staff","status":"suspended"}).status_code == 200
    assert user.get("/operations/me").status_code == 401
    assert user.post("/auth/login",json={"identifier":email,"password":replacement}).status_code == 401
    assert admin.post("/auth/logout",headers={"Origin":"https://evil.example","Sec-Fetch-Site":"cross-site"}).status_code == 403


def test_admin_creates_management_and_logout_revokes_session(clients):
    admin,user,created,_=clients
    email=f"manager-check-{uuid4()}@example.invalid";password=secrets.token_urlsafe(20)
    result=admin.post("/auth/accounts",json={"email":email,"name":"Temporary manager check","password":password,"role":"management"})
    assert result.status_code == 201,result.text
    created.append(result.json()["id"])
    assert user.post("/auth/login",json={"identifier":email,"password":password}).status_code == 200
    assert user.get("/operations/me").json()["role"] == "management"
    assert user.get("/auth/accounts").status_code == 403
    token=user.cookies.get("vinhomes_session")
    assert user.post("/auth/logout").status_code == 200
    assert user.get("/auth/session",headers={"Cookie":f"vinhomes_session={token}"}).status_code == 401


def test_connected_catalogs_room_messages_and_private_photo_storage(clients):
    """Real UI endpoints, temporary account/room/file; never retain test business data."""
    from io import BytesIO
    from PIL import Image
    admin, user, created, owner = clients
    email = f"ui-check-{uuid4()}@example.invalid"
    password = secrets.token_urlsafe(20)
    response = admin.post("/auth/accounts", json={"email": email, "name": "Temporary UI check", "password": password, "role": "management"})
    assert response.status_code == 201
    uid = response.json()["id"]; created.append(uid)
    assert user.post("/auth/login", json={"identifier": email, "password": password}).status_code == 200
    for endpoint in ["/catalogs", "/dashboard", "/tickets", "/work-orders", "/my-work-orders"]:
        assert user.get(endpoint).status_code == 200, endpoint
    room_id = str(uuid4())
    workspace_id, management_id = uuid4(), uuid4()
    channel_id = None
    async def create_room():
        db = await asyncpg.connect(owner)
        try:
            tenant = await db.fetchval("select tenant_id from tenant_memberships where user_id=$1", uid)
            async with db.transaction():
                await db.execute("insert into management_units(id,tenant_id,code,name,status) values($1,$2,$3,'Temporary UI check','active')", management_id, tenant, str(management_id))
                await db.execute("insert into workspaces(id,tenant_id,management_unit_id,code,name,status) values($1,$2,$3,$4,'Temporary UI check','active')", workspace_id, tenant, management_id, str(workspace_id))
                await db.execute("insert into channels(id,name,description,tenant_id,kind,created_by,workspace_id) values($1,'Temporary UI check','',$2,'management',$3,$4)", room_id, tenant, uid, workspace_id)
                await db.execute("insert into channel_memberships(channel_id,user_id,tenant_id) values($1,$2,$3)", room_id, uid, tenant)
        finally:
            await db.close()
    try:
        asyncio.run(create_room())
        assert any(r["id"] == room_id for r in user.get("/rooms").json()["items"])
        assert user.get(f"/rooms/{room_id}/agents").json() == {"items": []}
        # A platform administrator reads every management room without being a member of it.
        assert admin.get(f"/rooms/{room_id}/agents").json() == {"items": []}
        body = {"text": "Stored room message", "client_message_id": str(uuid4())}
        sent = user.post(f"/rooms/{room_id}/messages", json=body)
        assert sent.status_code == 201, sent.text
        again = user.post(f"/rooms/{room_id}/messages", json=body)
        assert again.json()["id"] == sent.json()["id"]
        messages = user.get(f"/rooms/{room_id}/messages").json()["items"]
        assert len(messages) == 1 and messages[0]["body"]["text"] == body["text"]
        assert messages[0]["sender_name"] == "Temporary UI check"
        chat = user.post("/resident/chats", json={"title": "Temporary upload check"})
        assert chat.status_code == 201, chat.text
        channel_id = chat.json()["id"]
        data = BytesIO(); Image.new("RGB", (2, 2), "white").save(data, "PNG")
        headers = {"Content-Type": "application/octet-stream", "Idempotency-Key": str(uuid4())}
        photo = user.post(f"/resident/chats/{channel_id}/photos?filename=check.png&mimeType=image/png", content=data.getvalue(), headers=headers)
        assert photo.status_code == 201, photo.text
        file_id = photo.json()["id"]
        assert user.get(f"/resident/photos/{file_id}").content == data.getvalue()
        assert admin.get(f"/resident/photos/{file_id}").status_code == 404
        assert user.post(f"/tickets/{uuid4()}/files?filename=check.png&mimeType=image/png", content=data.getvalue(), headers=headers).status_code == 404
    finally:
        async def clean_room():
            db = await asyncpg.connect(owner)
            paths = []
            try:
                async with db.transaction():
                    if channel_id:
                        # Local test teardown only: accepted bytes are immutable in normal
                        # operation. This owner session removes this test's exact file IDs.
                        await db.execute("set local session_replication_role='replica'")
                        paths = await db.fetch("select o.object_key from file_objects o join files f on f.id=o.file_id where f.channel_id=$1 and f.uploaded_by=$2", channel_id, uid)
                        await db.execute("update files set accepted_object_id=null,status='staged' where channel_id=$1 and uploaded_by=$2", channel_id, uid)
                        await db.execute("delete from file_objects where file_id in (select id from files where channel_id=$1 and uploaded_by=$2)", channel_id, uid)
                        await db.execute("delete from files where channel_id=$1 and uploaded_by=$2", channel_id, uid)
                    for cid in [room_id, channel_id]:
                        if not cid: continue
                        await db.execute("delete from messages where channel_id=$1", cid)
                        await db.execute("delete from channel_memberships where channel_id=$1", cid)
                        await db.execute("delete from channels where id=$1 and created_by=$2", cid, uid)
                    await db.execute("delete from execution_principals where user_id=$1", uid)
                    await db.execute("delete from workspaces where id=$1", workspace_id)
                    await db.execute("delete from management_units where id=$1", management_id)
            finally:
                await db.close()
            file_root = (ROOT / ".local-v3-files").resolve()
            for item in paths:
                path = (file_root / item["object_key"]).resolve()
                assert path.is_relative_to(file_root)
                path.unlink(missing_ok=True)
        asyncio.run(clean_room())


def test_admin_puts_a_management_account_in_one_unit_and_takes_it_out(clients):
    """A unit-scoped manager works in that unit's room; without the unit the room is closed again."""
    admin,user,created,_=clients
    units=admin.get("/auth/management-units")
    assert units.status_code == 200 and units.json()["items"],units.text
    unit=units.json()["items"][0]["id"]
    assert user.get("/auth/management-units").status_code == 401
    email=f"unit-manager-{uuid4()}@example.invalid";password=secrets.token_urlsafe(20)
    made=admin.post("/auth/accounts",json={"email":email,"name":"Temporary unit manager","password":password,
                                          "role":"management","management_unit_id":unit})
    assert made.status_code == 201,made.text
    uid=made.json()["id"];created.append(uid)
    listed=next(a for a in admin.get("/auth/accounts").json()["items"] if a["id"] == uid)
    assert (listed["role"],listed["management_unit_id"]) == ("management",unit)
    assert user.post("/auth/login",json={"identifier":email,"password":password}).status_code == 200
    assert user.get("/operations/me").json()["role"] == "management"
    rooms=user.get("/rooms").json()["items"]
    assert rooms, "the unit's management room is listed for its manager"
    room=rooms[0]["id"]
    assert user.get(f"/rooms/{room}/agent-management").status_code == 200
    assert user.get(f"/rooms/{room}/teams").status_code == 200
    # A unit only makes sense for management, and it must exist.
    assert admin.patch(f"/auth/accounts/{uid}",json={"role":"staff","status":"active","management_unit_id":unit}).status_code == 422
    assert admin.patch(f"/auth/accounts/{uid}",json={"role":"management","status":"active","management_unit_id":str(uuid4())}).status_code == 404
    # Made a technician: the room and its agents are no longer theirs.
    assert admin.patch(f"/auth/accounts/{uid}",json={"role":"staff","status":"active"}).status_code == 200
    assert user.post("/auth/login",json={"identifier":email,"password":password}).status_code == 200
    assert user.get("/rooms").json()["items"] == []
    assert user.get(f"/rooms/{room}/agent-management").status_code in (403,404)

