"""Password reset, self-service password change and removal of an account with no history, on PostgreSQL."""
import secrets
from contextlib import contextmanager
from uuid import UUID

from fastapi.testclient import TestClient

from test_resident_contract import TENANT, sql
from test_resident_contract import database as database
from vinhomes_api.main import create_app
from vinhomes_api.password_auth import password_hash
from vinhomes_api.v3_config import V3Settings


@contextmanager
def door(database):
    settings = V3Settings("127.0.0.1", 8000, database["runtime"], TENANT, None, None, password_auth=True)
    with TestClient(create_app(settings), client=("127.0.0.1", 50000)) as c:
        yield c


def sign_in(c, identifier, password):
    return c.post("/auth/login", json={"identifier": identifier, "password": password}).status_code


def test_the_administrator_resets_a_password_and_removes_only_an_account_without_history(database):
    admin_password = secrets.token_urlsafe(16)
    admin = sql(database, "select u.id,u.email from users u join platform_admins p on p.user_id=u.id limit 1")[0]
    sql(database, """insert into accounts(id,account_id,provider_id,user_id,password) values(gen_random_uuid()::text,$1,'vinhomes-password-v1',$1,$2)
        on conflict do nothing""", admin["id"], password_hash(admin_password))
    sql(database, "update tenant_memberships set status='active' where user_id=$1 and tenant_id=$2", admin["id"], TENANT)
    first, reset, changed = (secrets.token_urlsafe(16) for _ in range(3))
    email = f"reset-{secrets.token_hex(4)}@example.com"
    with door(database) as c:
        assert sign_in(c, admin["email"], admin_password) == 200
        made = c.post("/auth/accounts", json={"name": "Người thử", "email": email, "password": first, "role": "customer"})
        assert made.status_code == 201, made.text
        person = made.json()["id"]
        assert c.post(f"/auth/accounts/{person}/password", json={"new_password": "short"}).status_code == 422
        assert c.post(f"/auth/accounts/{admin['id']}/password", json={"new_password": reset}).status_code == 409
        assert c.post(f"/auth/accounts/{person}/password", json={"new_password": reset}).status_code == 200
        assert sql(database, "select count(*) as n from audit_events where event_type='account.password_reset' and target_id=$1", person)[0]["n"] == 1
    with door(database) as c:
        assert sign_in(c, email, first) == 401
        assert sign_in(c, email, reset) == 200
        # The person then chooses their own password; every sign-in of theirs ends.
        assert c.post("/auth/change-password", json={"current_password": first, "new_password": changed}).status_code == 401
        assert c.post("/auth/change-password", json={"current_password": reset, "new_password": changed}).status_code == 200
        assert c.get("/auth/session").status_code == 401
        assert sign_in(c, email, changed) == 200
    with door(database) as c:
        assert sign_in(c, admin["email"], admin_password) == 200
        # A resident with requests keeps their history: the account is suspended, never removed.
        assert c.delete("/auth/accounts/local-v3-resident").status_code == 409
        assert sql(database, "select count(*) as n from users where id='local-v3-resident'")[0]["n"] == 1
        assert c.delete(f"/auth/accounts/{admin['id']}").status_code == 409
        assert c.delete(f"/auth/accounts/{person}").status_code == 200
        assert c.delete(f"/auth/accounts/{person}").status_code == 404
    assert not sql(database, "select id from users where id=$1", person)
    assert sql(database, "select payload->>'email' as email from audit_events where event_type='account.deleted' and target_id=$1", person) == [{"email": email}]
