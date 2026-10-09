"""One sign-in page for everyone: the session says which app each person goes on to (apps/resident-web, /login)."""
import secrets

from test_account_administration import door, sign_in
from test_resident_contract import TENANT, sql
from test_resident_contract import database as database  # noqa: F401 -- pytest fixture export
from vinhomes_api.password_auth import password_hash


def test_the_session_tells_which_app_each_kind_of_person_goes_on_to(database):
    admin_password = secrets.token_urlsafe(16)
    admin = sql(database, "select u.id,u.email from users u join platform_admins p on p.user_id=u.id limit 1")[0]
    sql(database, """insert into accounts(id,account_id,provider_id,user_id,password) values(gen_random_uuid()::text,$1,'vinhomes-password-v1',$1,$2)
        on conflict do nothing""", admin["id"], password_hash(admin_password))
    sql(database, "update tenant_memberships set status='active' where user_id=$1 and tenant_id=$2", admin["id"], TENANT)
    password = secrets.token_urlsafe(16)
    emails = {role: f"{role}-{secrets.token_hex(4)}@example.com" for role in ("customer", "staff", "management")}
    with door(database) as c:
        assert sign_in(c, admin["email"], admin_password) == 200
        for role, email in emails.items():
            made = c.post("/auth/accounts", json={"name": f"Người {role}", "email": email, "password": password, "role": role})
            assert made.status_code == 201, made.text
        session = c.get("/auth/session").json()
        assert session["operationsRole"] == "admin" and "operations" in session["audiences"]               # 1: an administrator

    expected = {"customer": (None, ["resident"]), "staff": ("staff", ["operations"]), "management": ("management", ["operations"])}
    for role, email in emails.items():
        with door(database) as c:
            assert sign_in(c, email, password) == 200                                                        # 2: the same door for everyone
            session = c.get("/auth/session").json()
            assert (session["operationsRole"], session["audiences"]) == expected[role], role
            if role != "customer":   # the same cookie opens the staff app: no front door stands in the way
                me = c.get("/operations/me")
                assert me.status_code == 200 and me.json()["role"] == role, me.text

    # 3: someone who is both a resident and staff is offered both
    both = sql(database, "select id from users where email=$1", emails["staff"])[0]["id"]
    sql(database, """insert into scoped_user_roles(id,tenant_id,membership_id,scope_id,role_code,granted_by,valid_from)
        select gen_random_uuid(),r.tenant_id,r.membership_id,r.scope_id,'customer',r.granted_by,r.valid_from
        from scoped_user_roles r join tenant_memberships m on m.id=r.membership_id and m.tenant_id=r.tenant_id
        where m.user_id=$1 and r.role_code='staff' limit 1""", both)
    with door(database) as c:
        assert sign_in(c, emails["staff"], password) == 200
        session = c.get("/auth/session").json()
        assert (session["operationsRole"], session["audiences"]) == ("staff", ["resident", "operations"])

    # 4: a person who has just registered has no role yet and belongs to the resident app
    fresh, secret = f"new-{secrets.token_hex(4)}@example.com", secrets.token_urlsafe(16)
    with door(database) as c:
        assert c.post("/auth/register", json={"name": "Người mới", "email": fresh, "password": secret}).status_code == 201
        assert sign_in(c, fresh, secret) == 200
        session = c.get("/auth/session").json()
        assert (session["membershipStatus"], session["operationsRole"], session["audiences"]) == ("pending", None, ["resident"])
